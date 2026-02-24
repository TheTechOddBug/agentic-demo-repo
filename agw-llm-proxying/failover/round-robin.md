export ANTHROPIC_API_KEY=
export OPENAI_API_KEY=

```
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: anthropic-secret
  namespace: agentgateway-system
  labels:
    app: agentgateway-rr
type: Opaque
stringData:
  Authorization: $ANTHROPIC_API_KEY
EOF
```

```
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: openai-secret
  namespace: agentgateway-system
  labels:
    app: agentgateway-rr
type: Opaque
stringData:
  Authorization: $OPENAI_API_KEY
EOF
```

```
kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  labels:
    app: agentgateway-route
  name: agentgateway-rr
  namespace: agentgateway-system
spec:
  type: AI
  ai:
    priorityGroups:
    - providers:
      - name: claude-haiku
        anthropic:
          model: "claude-3-5-haiku-latest"
          authToken:
            kind: SecretRef
            secretRef:
              name: anthropic-secret
      - name: gpt-turbo
        openai:
          model: "gpt-3.5-turbo"
          authToken:
            kind: SecretRef
            secretRef:
              name: openai-secret
      - name: claude-opus
        anthropic:
          model: "claude-opus-4-1"
          authToken:
            kind: SecretRef
            secretRef:
              name: anthropic-secret
EOF
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
        value: /anthropic
    filters:
    - type: URLRewrite
      urlRewrite:
        path:
          type: ReplaceFullPath
          replaceFullPath: /v1/chat/completions
    backendRefs:
    - name: agentgateway-rr
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```