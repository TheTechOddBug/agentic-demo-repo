```
export ANTHROPIC_API_KEY=
```

```
kubectl apply -f- <<EOF
kind: Gateway
apiVersion: gateway.networking.k8s.io/v1
metadata:
  name: agentgateway-route
  namespace: agentgateway-system
  labels:
    app: agentgateway
spec:
  gatewayClassName: enterprise-agentgateway
  infrastructure:
    parametersRef:
      name: tracing
      group: enterpriseagentgateway.solo.io
      kind: EnterpriseAgentgatewayParameters
  listeners:
  - protocol: HTTP
    port: 8080
    name: http
    allowedRoutes:
      namespaces:
        from: All
EOF
```

```
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: anthropic-secret
  namespace: agentgateway-system
  labels:
    app: agentgateway-route
type: Opaque
stringData:
  Authorization: $ANTHROPIC_API_KEY
EOF
```

```
kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  labels:
    app: agentgateway-route
  name: anthropic
  namespace: agentgateway-system
spec:
  ai:
    provider:
        anthropic:
          model: "claude-opus-4-6"
  policies:
    ai:
      routes:
        '/v1/messages': Messages
        '*': Passthrough
    auth:
      secretRef:
        name: anthropic-secret
EOF
```

OR without a Model:
```
kubectl apply -f - <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  labels:
    app: agentgateway-route
  name: anthropic
  namespace: agentgateway-system
spec:
  ai:
    provider:
      anthropic: {}
  policies:
    auth:
      secretRef:
        name: anthropic-secret
    ai:
      routes:
        '/v1/messages': Messages
        '*': Passthrough
EOF
```

```
kubectl get agentgatewaybackend -n agentgateway-system
```

```
kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: claude
  namespace: agentgateway-system
  labels:
    app: agentgateway-route
spec:
  parentRefs:
    - name: agentgateway-route
      namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /
    backendRefs:
    - name: anthropic
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

```
export INGRESS_GW_ADDRESS=$(kubectl get svc -n agentgateway-system agentgateway-route -o jsonpath="{.status.loadBalancer.ingress[0]['hostname','ip']}")
echo $INGRESS_GW_ADDRESS
```

```
ANTHROPIC_BASE_URL="http://127.0.0.1:8080" claude -p "What is a credit card"
```

OR
```
ANTHROPIC_BASE_URL="http://$INGRESS_GW_ADDRESS$:8080" claude -p "What is a credit card"
```

You will get a successful response

## Prompt Guard

1. Re-apply the agentgatewaybackend except this time, you'll see the `promptGuard` parameter.

```
kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  labels:
    app: agentgateway-route
  name: anthropic
  namespace: agentgateway-system
spec:
  ai:
    provider:
        anthropic:
          model: "claude-opus-4-6"
  policies:
    ai:
      routes:
        '/v1/messages': Messages
        '*': Passthrough
      promptGuard:
        request:
        - response:
            message: "Rejected due to inappropriate content"
          regex:
            action: Reject
            matches:
            - "credit card"
    auth:
      secretRef:
        name: anthropic-secret
EOF
```

OR without a Model:
```
kubectl apply -f - <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  labels:
    app: agentgateway-route
  name: anthropic
  namespace: agentgateway-system
spec:
  ai:
    provider:
      anthropic: {}
  policies:
    auth:
      secretRef:
        name: anthropic-secret
    ai:
      routes:
        '/v1/messages': Messages
        '*': Passthrough
      promptGuard:
        request:
        - response:
            message: "Rejected due to inappropriate content"
          regex:
            action: Reject
            matches:
            - "credit card"
EOF
```

2. Run the check again:

```
ANTHROPIC_BASE_URL="http://$INGRESS_GW_ADDRESS:8080" claude -p "What is a credit card"
```


**Known Issue On Claudes End**

There is an issue where if you're in prompt mode (without using `-p "What is a credit card"` and instead just use `ANTHROPIC_BASE_URL="http://$INGRESS_GW_ADDRESS:8080" claude`, the 403 will keep popping up. We looked into this and that's on Claudes end. We can't invalidate the session once its started. Claude shouldn't re-send the 403 (might be a good bug ticket to put in with them), but we have no way to control that. The only way to clear that is with a new session/prompt.

WORKS:
`ANTHROPIC_BASE_URL="http://$INGRESS_GW_ADDRESS:8080" claude -p "What is a credit card"`

Doesn't work:
`ANTHROPIC_BASE_URL="http://$INGRESS_GW_ADDRESS:8080" claude`