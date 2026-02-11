# Agentgateway Enterprise Demo

This guide walks through a comprehensive enterprise agentgateway demo covering core gateway features, authentication, observability, performance testing, and kagent extensibility.

---

## Prereqs

### Enterprise Agentgateway Installation

```
export AGENTGATEWAY_LICENSE_KEY=
```

```
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.4.0/standard-install.yaml
```

```
helm upgrade -i agentgateway-crds oci://us-docker.pkg.dev/solo-public/enterprise-agentgateway/charts/enterprise-agentgateway-crds \
  --create-namespace \
  --namespace agentgateway-system \
  --version 2.1.0-rc.2
```

```
helm upgrade -i agentgateway oci://us-docker.pkg.dev/solo-public/enterprise-agentgateway/charts/enterprise-agentgateway \
  -n agentgateway-system \
  --version 2.1.0-rc.2 \
  --set agentgateway.enabled=true \
  --set extAuthServer.enabled=true \
  --set tokenExchange.enabled=true \
  --set licensing.licenseKey=${AGENTGATEWAY_LICENSE_KEY}
```

```
kubectl get pods -n agentgateway-system
```

### MCP Server Deployment

```
kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcp-math-script
  namespace: default
data:
  server.py: |
    import uvicorn
    from mcp.server.fastmcp import FastMCP
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    mcp = FastMCP("Math-Service")

    @mcp.tool()
    def add(a: int, b: int) -> int:
        return a + b

    @mcp.tool()
    def multiply(a: int, b: int) -> int:
        return a * b

    async def handle_mcp(request: Request):
        try:
            data = await request.json()
            method = data.get("method")
            msg_id = data.get("id")
            result = None
            
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "Math-Service", "version": "1.0"}
                }
            
            elif method == "notifications/initialized":
                return JSONResponse({"jsonrpc": "2.0", "id": msg_id, "result": True})

            elif method == "tools/list":
                tools_list = await mcp.list_tools()
                result = {
                    "tools": [
                        {
                            "name": t.name,
                            "description": t.description,
                            "inputSchema": t.inputSchema
                        } for t in tools_list
                    ]
                }

            elif method == "tools/call":
                params = data.get("params", {})
                name = params.get("name")
                args = params.get("arguments", {})
                
                # Call the tool
                tool_result = await mcp.call_tool(name, args)
                
                # --- FIX: Serialize the content objects manually ---
                serialized_content = []
                for content in tool_result:
                    if hasattr(content, "type") and content.type == "text":
                        serialized_content.append({"type": "text", "text": content.text})
                    elif hasattr(content, "type") and content.type == "image":
                         serialized_content.append({
                             "type": "image", 
                             "data": content.data, 
                             "mimeType": content.mimeType
                         })
                    else:
                        # Fallback for dictionaries or other types
                        serialized_content.append(content if isinstance(content, dict) else str(content))

                result = {
                    "content": serialized_content,
                    "isError": False
                }

            elif method == "ping":
                result = {}

            else:
                return JSONResponse(
                    {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": "Method not found"}},
                    status_code=404
                )

            return JSONResponse({"jsonrpc": "2.0", "id": msg_id, "result": result})

        except Exception as e:
            # Print error to logs for debugging
            import traceback
            traceback.print_exc()
            return JSONResponse(
                {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(e)}},
                status_code=500
            )

    app = Starlette(routes=[
        Route("/mcp", handle_mcp, methods=["POST"]),
        Route("/", lambda r: JSONResponse({"status": "ok"}), methods=["GET"])
    ])

    if __name__ == "__main__":
        print("Starting Fixed Math Server on port 8000...")
        uvicorn.run(app, host="0.0.0.0", port=8000)
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-math-server
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mcp-math-server
  template:
    metadata:
      labels:
        app: mcp-math-server
    spec:
      containers:
      - name: math
        image: python:3.11-slim
        command: ["/bin/sh", "-c"]
        args:
        - |
          pip install "mcp[cli]" uvicorn starlette && 
          python /app/server.py
        ports:
        - containerPort: 8000
        volumeMounts:
        - name: script-volume
          mountPath: /app
        readinessProbe:
          httpGet:
            path: /
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: script-volume
        configMap:
          name: mcp-math-script
---
apiVersion: v1
kind: Service
metadata:
  name: mcp-math-server
  namespace: default
spec:
  selector:
    app: mcp-math-server
  ports:
  - port: 80
    targetPort: 8000
EOF
```

1. Create a gateway for the MCP server you deployed
```
kubectl apply -f - <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: mcp-gateway
  namespace: agentgateway-system
  labels:
    app: mcp-math-server
spec:
  gatewayClassName: enterprise-agentgateway
  listeners:
    - name: mcp
      port: 3000
      protocol: HTTP
      allowedRoutes:
        namespaces:
          from: Same
EOF
```

2. Apply the backend so the gateway knows what to route to. In this case, it's an MCP server
```
kubectl apply -f - <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: demo-mcp-server
  namespace: agentgateway-system
spec:
  mcp:
    targets:
      - name: demo-mcp-server
        static:
          host: mcp-math-server.default.svc.cluster.local
          port: 80
          path: /mcp
          protocol: StreamableHTTP
EOF
```

3. Apply the route so the MCP Server can be reached
```
kubectl apply -f - <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: mcp-route
  namespace: agentgateway-system
  labels:
    app: mcp-math-server
spec:
  parentRefs:
    - name: mcp-gateway
  rules:
    - backendRefs:
      - name: demo-mcp-server
        namespace: agentgateway-system
        group: agentgateway.dev
        kind: AgentgatewayBackend
EOF
```

4. Capture the IP of the gateway
```
export GATEWAY_IP=$(kubectl get svc mcp-gateway -n agentgateway-system -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo $GATEWAY_IP
```

### Gateway Setup

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
export INGRESS_GW_ADDRESS=$(kubectl get svc -n agentgateway-system agentgateway-route -o jsonpath="{.status.loadBalancer.ingress[0]['hostname','ip']}")
echo $INGRESS_GW_ADDRESS
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
          model: "claude-sonnet-4-5-20250929"
  policies:
    auth:
      secretRef:
        name: anthropic-secret
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
        value: /anthropic
    filters:
    - type: URLRewrite
      urlRewrite:
        path:
          type: ReplaceFullPath
          replaceFullPath: /v1/chat/completions
    backendRefs:
    - name: anthropic
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

Test LLM connectivity:

```
curl "$INGRESS_GW_ADDRESS:8080/anthropic" -v -H content-type:application/json -H "anthropic-version: 2023-06-01" -d '{
  "messages": [
    {
      "role": "system",
      "content": "You are a skilled cloud-native network engineer."
    },
    {
      "role": "user",
      "content": "Write me a paragraph containing the best way to think about Istio Ambient Mesh"
    }
  ]
}' | jq
```

Check agentgateway pod logs for token usage:

```
kubectl logs -n agentgateway-system deploy/agentgateway-route --tail=20
```

Expected log output showing token counts:
```
info    request gateway=agentgateway-system/agentgateway-route listener=http route=agentgateway-system/claude endpoint=api.anthropic.com:443 ... http.status=200 protocol=llm gen_ai.operation.name=chat gen_ai.provider.name=anthropic gen_ai.request.model=claude-sonnet-4-5-20250929 gen_ai.usage.input_tokens=35 gen_ai.usage.output_tokens=196 duration=5157ms
```

### Kube Prometheus Setup

1. Add the Chart
```
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
```

2. Install Kube-Prometheus
```
helm install kube-prometheus -n monitoring prometheus-community/kube-prometheus-stack --create-namespace
```

To look at the metrics in Prometheus
```
kubectl --namespace monitoring port-forward svc/kube-prometheus-kube-prome-prometheus 9090
```

To build a dashboard with the metrics
```
kubectl --namespace monitoring port-forward svc/kube-prometheus-grafana 3000:80
```

To log into the Grafana UI:

1. Username: admin
2. Password: `kubectl get secret kube-prometheus-grafana -n monitoring -o jsonpath='{.data.admin-password}' | base64 --decode`


Deploy a PodMonitor to scrape agentgateway metrics:

```
kubectl apply -f - <<EOF
apiVersion: monitoring.coreos.com/v1
kind: PodMonitor
metadata:
  name: agentgateway
  namespace: agentgateway-system
  labels:
    app: agentgateway
    release: kube-prometheus
spec:
  selector:
    matchLabels:
      gateway.networking.k8s.io/gateway-class-name: enterprise-agentgateway
  podMetricsEndpoints:
  - port: metrics
    path: /metrics
    interval: 30s
    scrapeTimeout: 10s
EOF
```

---

### Configure Tracing

Distributed Tracing (OpenTelemetry)

Install the OpenTelemetry collector with Tempo backend:

```
helm upgrade --install opentelemetry-collector-traces opentelemetry-collector \
  --repo https://open-telemetry.github.io/opentelemetry-helm-charts \
  --version 0.127.2 \
  --set mode=deployment \
  --set image.repository="otel/opentelemetry-collector-contrib" \
  --set command.name="otelcol-contrib" \
  --namespace=telemetry \
  --create-namespace \
  -f -<<EOF
config:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317
        http:
          endpoint: 0.0.0.0:4318
  exporters:
    otlp/tempo:
      endpoint: http://tempo.telemetry.svc.cluster.local:4317
      tls:
        insecure: true
    debug:
      verbosity: detailed
  service:
    pipelines:
      traces:
        receivers: [otlp]
        processors: [batch]
        exporters: [debug, otlp/tempo]
EOF
```

```
kubectl get pods -n telemetry
```

Configure agentgateway tracing with gen_ai.* fields:

```
kubectl apply -f- <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: agent-gateway-config
  namespace: agentgateway-system
data:
  config.yaml: |-
    config:
      tracing:
        otlpEndpoint: http://opentelemetry-collector-traces.telemetry.svc.cluster.local:4317
        otlpProtocol: grpc
        randomSampling: true
        fields:
          add:
            gen_ai.operation.name: '"chat"'
            gen_ai.system: "llm.provider"
            gen_ai.request.model: "llm.requestModel"
            gen_ai.response.model: "llm.responseModel"
            gen_ai.usage.completion_tokens: "llm.outputTokens"
            gen_ai.usage.prompt_tokens: "llm.inputTokens"
EOF
```

---

## Section 1: Core Agentgateway Features


### 1b. Rate Limiting

1. Create a rate limit rule that targets the `HTTPRoute` you just created
```
kubectl apply -f - <<EOF
apiVersion: enterpriseagentgateway.solo.io/v1alpha1
kind: EnterpriseAgentgatewayPolicy
metadata:
  name: traffic-policy
  namespace: agentgateway-system
  labels:
    app: agentgateway-rate
spec:
  targetRefs:
  - group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: claude
  traffic:
    rateLimit:
      local:
        - requests: 1
          unit: Minutes
EOF
```

2. Capture the LB IP of the service to test again
```
export INGRESS_GW_ADDRESS=$(kubectl get svc -n agentgateway-system agentgateway-route -o jsonpath="{.status.loadBalancer.ingress[0]['hostname','ip']}")
echo $INGRESS_GW_ADDRESS
```

3. Test the LLM connectivity
```
curl "$INGRESS_GW_ADDRESS:8080/anthropic" -v \ -H content-type:application/json -H "anthropic-version: 2023-06-01" -d '{
  "model": "claude-sonnet-4-5",
  "messages": [
    {
      "role": "system",
      "content": "You are a skilled cloud-native network engineer."
    },
    {
      "role": "user",
      "content": "Write me a paragraph containing the best way to think about Istio Ambient Mesh"
    }
  ]
}' | jq
```

4. Run the `curl` again

You'll see a `curl` error that looks something like this:

```
< x-ratelimit-limit: 1
< x-ratelimit-remaining: 0
< x-ratelimit-reset: 76
< content-length: 19
```

5. Clean up the policy:
```
kubectl delete -f - <<EOF
apiVersion: enterpriseagentgateway.solo.io/v1alpha1
kind: EnterpriseAgentgatewayPolicy
metadata:
  name: traffic-policy
  namespace: agentgateway-system
  labels:
    app: agentgateway-rate
spec:
  targetRefs:
  - group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: claude
  traffic:
    rateLimit:
      local:
        - requests: 1
          unit: Minutes
EOF
```

#### Token-Based Rate Limiting

kubectl apply -f- <<EOF
apiVersion: ratelimit.solo.io/v1alpha1
kind: RateLimitConfig
metadata:
  name: openai-rate-limit
  namespace: agentgateway-system
spec:
  raw:
    descriptors:
    - key: X-User-ID
      rateLimit:
        unit: MINUTE
        requestsPerUnit: 100
    rateLimits:
      type: TOKEN
EOF

---

### 1d. Observability With Prometheus/Grafana

Generate Observability Data

```
curl "$INGRESS_GW_ADDRESS:8080/anthropic" -v \ -H content-type:application/json -H "anthropic-version: 2023-06-01" -d '{
  "model": "claude-sonnet-4-5",
  "messages": [
    {
      "role": "system",
      "content": "You are a skilled cloud-native network engineer."
    },
    {
      "role": "user",
      "content": "Write me a paragraph containing the best way to think about Istio Ambient Mesh"
    }
  ]
}' | jq
```

![](images/1.png)

### 1d. Access Control (Prompt Guards)

Apply a prompt guard policy that blocks queries containing "credit card":

```
kubectl apply -f - <<EOF
apiVersion: enterpriseagentgateway.solo.io/v1alpha1
kind: EnterpriseAgentgatewayPolicy
metadata:
  name: credit-guard-prompt-guard
  namespace: agentgateway-system
  labels:
    app: agentgateway-route
spec:
  targetRefs:
  - group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: claude
  backend:
    ai:
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

Test — this should return a 403:

```
curl "$INGRESS_GW_ADDRESS:8080/anthropic" -v -H content-type:application/json -H "anthropic-version: 2023-06-01" -d '{
  "messages": [
    {
      "role": "system",
      "content": "You are a skilled cloud-native network engineer."
    },
    {
      "role": "user",
      "content": "What is a credit card?"
    }
  ]
}' | jq
```

Expected:
```
< HTTP/1.1 403 Forbidden
```

Test with a non-blocked prompt (should return 200):
```
curl "$INGRESS_GW_ADDRESS:8080/anthropic" -v \
  -H content-type:application/json \
  -H "anthropic-version: 2023-06-01" \
  -d '{
  "model": "claude-sonnet-4-5-20250929",
  "messages": [
    {"role": "user", "content": "What is Kubernetes?"}
  ]
}' 2>&1 | grep "HTTP"
```

Clean up:
```
kubectl delete enterpriseagentgatewaypolicy credit-guard-prompt-guard -n agentgateway-system
```

---


### 1e. MCP JWT Authentication

1. Capture the IP of the gateway
```
export GATEWAY_IP=$(kubectl get svc agentgateway-route -n agentgateway-system -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo $GATEWAY_IP
```

2. Open MCP Inspector
```
npx modelcontextprotocol/inspector#0.20.0
```

3. Specify, within the **URL** section, the following:
```
http://YOUR_ALB_IP:3000/mcp
```

You should now be able to see the connection without any security. This means that the MCP Server is wide open.

4. To implement auth security, add a gateway policy
```
kubectl apply -f- <<EOF
apiVersion: enterpriseagentgateway.solo.io/v1alpha1
kind: EnterpriseAgentgatewayPolicy
metadata:
  name: jwt
  namespace: agentgateway-system
spec:
  targetRefs:
    - group: gateway.networking.k8s.io
      kind: Gateway
      name: mcp-gateway
  traffic:
    jwtAuthentication:
      providers:
        - issuer: solo.io
          jwks:
            inline: '{"keys": [{"kty": "RSA", "kid": "solo-public-key-001", "use": "sig", "alg": "RS256", "n": "vdV2XxH70WcgDKedYXNQ3Dy1LN8LKziw3pxBe0M-QG3_urCbN-oTPL2e0xrj5t2JOV-eBNaII17oZ6z9q84lLzn4mgU_UzP-Efv6iTZLlC_SD30AknifnoX8k38zbJtuwkvVcZvkam0LM5oIwSf4wJVpdPKHb3o_gGRpCBxWdQHPdBWMBPwOeqFfONFrM0bEnShFWf3d87EgckdVcrypelLyUZJ_ACdEGYUhS6FHmyojA1g6zKryAAWsH5Y-UCUuJd7VlOCMoBpAKK0BSdlF3WVSYHDlyMSB5H61eYCXSpfKcGhoHxViLgq6yjUR7TOHkJ-OtWna513TrkRw2Y0hsQ", "e": "AQAB"}]}'
EOF
```

5. Open the MCP Inspector and under **Authentication**, add in the following:
- Header Name: **Authorization**
- Bearer Token (ensure to put `Bearer` in before the token):
```
eyJhbGciOiJSUzI1NiIsImtpZCI6InNvbG8tcHVibGljLWtleS0wMDEiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJzb2xvLmlvIiwib3JnIjoic29sby5pbyIsInN1YiI6ImJvYiIsInRlYW0iOiJvcHMiLCJleHAiOjIwNzQyNzQ5NTQsImxsbXMiOnsibWlzdHJhbGFpIjpbIm1pc3RyYWwtbGFyZ2UtbGF0ZXN0Il19fQ.AZF6QKJJbnayVvP4bWVr7geYp6sdfSP-OZVyWAA4RuyjHMELE-K-z1lzddLt03i-kG7A3RrCuuF80NeYnI_Cm6pWtwJoFGbLfGoE0WXsBi50-0wLnpjAb2DVIez55njP9NVv3kHbVu1J8_ZO6ttuW6QOZU7AKWE1-vymcDVsNkpFyPBFXV7b-RIHFZpHqgp7udhD6BRBjshhrzA4752qovb-M-GRDrVO9tJhDXEmhStKkV1WLMJkH43xPSf1uNR1M10gMMzjFZgVB-kg6a1MRzElccpRum729c5rRGzd-_C4DsGm4oqBjg-bqXNNtUwNCIlmfRI5yeAsbeayVcnTIg
```

6. Delete the auth policy
```
kubectl delete -f- <<EOF
apiVersion: enterpriseagentgateway.solo.io/v1alpha1
kind: EnterpriseAgentgatewayPolicy
metadata:
  name: jwt
  namespace: agentgateway-system
spec:
  targetRefs:
    - group: gateway.networking.k8s.io
      kind: Gateway
      name: mcp-gateway
  traffic:
    jwtAuthentication:
      providers:
        - issuer: solo.io
          jwks:
            inline: '{"keys": [{"kty": "RSA", "kid": "solo-public-key-001", "use": "sig", "alg": "RS256", "n": "vdV2XxH70WcgDKedYXNQ3Dy1LN8LKziw3pxBe0M-QG3_urCbN-oTPL2e0xrj5t2JOV-eBNaII17oZ6z9q84lLzn4mgU_UzP-Efv6iTZLlC_SD30AknifnoX8k38zbJtuwkvVcZvkam0LM5oIwSf4wJVpdPKHb3o_gGRpCBxWdQHPdBWMBPwOeqFfONFrM0bEnShFWf3d87EgckdVcrypelLyUZJ_ACdEGYUhS6FHmyojA1g6zKryAAWsH5Y-UCUuJd7VlOCMoBpAKK0BSdlF3WVSYHDlyMSB5H61eYCXSpfKcGhoHxViLgq6yjUR7TOHkJ-OtWna513TrkRw2Y0hsQ", "e": "AQAB"}]}'
EOF
```

---

### 2f. OIDC Authentication (oAuth for MCP)

```
https://github.com/AdminTurnedDevOps/agentic-demo-repo/tree/main/mcp/mcp-oauth-demos
```

---

## Section 3: Performance Metrics & Stress Testing

### 3a. LLM Endpoint Stress Test (k6)

Install k6:
```
# macOS
brew install k6

# Linux
sudo gpg -k && sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D68 && echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list && sudo apt-get update && sudo apt-get install k6
```

Run the test:

```
export GATEWAY_ADDRESS=$INGRESS_GW_ADDRESS:8080

k6 run --out json=results.json -e GATEWAY_ADDRESS=$GATEWAY_ADDRESS k6-llm-stress.js
```

---

### 3b. Rate Limit Stress Test (k6)

This test validates rate limiting enforcement by sending rapid requests.

First apply the rate limit policy (from Section 1b), then run:

```
k6 run -e GATEWAY_ADDRESS=$GATEWAY_ADDRESS k6-ratelimit-stress.js
```

---

## Section 4: kagent & Agentgateway Extensibility

### 4a. Agent and MCP Creation
1. Creat a new namespace to work in and enroll it into the mesh:
```
kubectl create ns policies

kubectl label namespaces policies istio.io/dataplane-mode=ambient
```

2. Create an MCP Server object
```
kubectl apply -f - <<EOF
apiVersion: kagent.dev/v1alpha1
kind: MCPServer
metadata:
  name: test-mcp-server
  namespace: policies
  labels:
    kagent.solo.io/waypoint: "true"
spec:
  deployment:
    image: mcp/everything
    port: 3000
    cmd: npx
    args:
      - "-y"
      - "@modelcontextprotocol/server-github"
  transportType: stdio
EOF
```

3. Create an environment variable and k8s secret for your Anthropic key:
```
export ANTHROPIC_API_KEY=

kubectl create secret generic kagent-anthropic --from-literal=ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY -n policies
```

4. Create a Model Config
```
kubectl apply -f - <<EOF
apiVersion: kagent.dev/v1alpha2
kind: ModelConfig
metadata:
  name: anthropic-model-config
  namespace: policies
spec:
  apiKeySecret: kagent-anthropic
  apiKeySecretKey: ANTHROPIC_API_KEY
  model: claude-sonnet-4-20250514
  provider: Anthropic
  anthropic: {}
EOF
```

5. Create an Agent
```
kubectl apply -f - <<EOF
apiVersion: kagent.dev/v1alpha2
kind: Agent
metadata:
  name: test-tools-agent
  namespace: policies
spec:
  description: This agent can use a single tool to expand it's Kubernetes knowledge for troubleshooting and deployment
  type: Declarative
  declarative:
    modelConfig: anthropic-model-config
    systemMessage: |-
      You're a friendly and helpful agent that uses the Kubernetes tool to help troubleshooting and deploy environments
  
      # Instructions
  
      - If user question is unclear, ask for clarification before running any tools
      - Always be helpful and friendly
      - If you don't know how to answer the question DO NOT make things up
        respond with "Sorry, I don't know how to answer that" and ask the user to further clarify the question
  
      # Response format
      - ALWAYS format your response as Markdown
      - Your response will include a summary of actions you took and an explanation of the result
    tools:
    - type: McpServer
      mcpServer:
        name: test-mcp-server
        kind: MCPServer
        toolNames:
        - search_repositories
        - search_issues
        - search_code
        - search_users
EOF
```

6. Open the Agent in kagent and ask `What tools do you have available? Give me the list`

You should see four tools:
        - search_repositories
        - search_issues
        - search_code
        - search_users
---

### 4b. Agent Skills (A2A)

Agents can expose skills via the A2A (Agent-to-Agent) protocol, enabling capability discovery and inter-agent collaboration.

Deploy an agent with A2A skills:

```
kubectl apply -f - <<EOF
apiVersion: kagent.dev/v1alpha2
kind: Agent
metadata:
  name: kubernetes-mcp-agent
  namespace: kagent
spec:
  description: Kubernetes management agent with exposed A2A skills
  type: Declarative
  declarative:
    modelConfig: agentgateway-model-config
    systemMessage: |-
      You're a friendly and helpful agent that uses the Kubernetes tool to help troubleshooting and deploy environments

      # Instructions

      - If user question is unclear, ask for clarification before running any tools
      - Always be helpful and friendly
      - If you don't know how to answer the question DO NOT make things up
        respond with "Sorry, I don't know how to answer that" and ask the user to further clarify the question

      # Response format
      - ALWAYS format your response as Markdown
      - Your response will include a summary of actions you took and an explanation of the result
    tools:
    - type: McpServer
      mcpServer:
        name: mcp-kubernetes-server
        kind: MCPServer
        toolNames:
        - events_list
        - namespaces_list
        - pods_list
        - pods_list_in_namespace
        - pods_get
        - pods_delete
    a2aConfig:
      skills:
        - id: cluster-diagnostics
          name: Cluster Diagnostics
          description: The ability to analyze and diagnose Kubernetes Cluster issues.
          tags:
            - cluster
            - diagnostics
          examples:
            - "What is the status of my cluster?"
            - "How can I troubleshoot a failing pod?"
            - "What are the resource limits for my nodes?"
        - id: resource-management
          name: Resource Management
          description: The ability to manage and optimize Kubernetes resources.
          tags:
            - resource
            - management
          examples:
            - "Scale my deployment X to 3 replicas."
            - "Optimize resource requests for my pods."
            - "Reserve more CPU for my nodes."
        - id: security-audit
          name: Security Audit
          description: The ability to audit and enhance Kubernetes security.
          tags:
            - security
            - audit
          examples:
            - "Check for RBAC misconfigurations."
            - "Audit my network policies."
            - "Identify potential security vulnerabilities in my cluster."
EOF
```

---

### 4c. Tool-Level Access Policies (Enterprise)
1. Apply an access policy that specifies only access to one of the tools
```
kubectl apply -f - <<EOF
apiVersion: policy.kagent-enterprise.solo.io/v1alpha1
kind: AccessPolicy
metadata:
  name: deny-github-tool-server
  namespace: policies
spec:
  from:
    subjects:
    - kind: Agent
      name: test-tools-agent
      namespace: policies
  targetRef:
    kind: MCPServer
    name: test-mcp-server
    tools: ["search_repositories"]
  action: DENY
EOF
```

2. Prompt again
```
What tools do you have available? Give me the list
```

You should now not the `search_repositories` tool

3. Delete the policy

```
kubectl delete -f - <<EOF
apiVersion: policy.kagent-enterprise.solo.io/v1alpha1
kind: AccessPolicy
metadata:
  name: deny-github-tool-server
  namespace: policies
spec:
  from:
    subjects:
    - kind: Agent
      name: test-access-policy
      namespace: kagent
  targetRef:
    kind: MCPServer
    name: test-mcp-server
    tools: ["search_repositories"]
  action: DENY
EOF
```

---

### 4e. kagent + Agentgateway Together
```
helm install kagent-crds oci://ghcr.io/kagent-dev/kagent/helm/kagent-crds \
    --namespace kagent \
    --create-namespace
```

```
export ANTHROPIC_API_KEY=your_api_key
```

```
helm upgrade --install kagent oci://ghcr.io/kagent-dev/kagent/helm/kagent \
    --namespace kagent \
    --set providers.default=anthropic \
    --set providers.anthropic.apiKey=$ANTHROPIC_API_KEY \
    --set ui.service.type=LoadBalancer
```

## Section 5: Observability

### 5a. Langfuse Integration

Langfuse provides LLM observability with trace visualization, token usage tracking, and cost analysis. This integrates agentgateway's OpenTelemetry traces into Langfuse.

#### Option A: Langfuse Cloud

If using Langfuse Cloud, obtain your keys from https://cloud.langfuse.com:

```
export LANGFUSE_PUBLIC_KEY=
export LANGFUSE_SECRET_KEY=
export LANGFUSE_HOST=https://cloud.langfuse.com
```

#### Option B: Self-Hosted Langfuse

Deploy Langfuse self-hosted with PostgreSQL:

```
kubectl create namespace langfuse

kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: langfuse-secrets
  namespace: langfuse
type: Opaque
stringData:
  NEXTAUTH_SECRET: "$(openssl rand -base64 32)"
  SALT: "$(openssl rand -base64 32)"
  DATABASE_URL: "postgresql://langfuse:langfuse@langfuse-postgres:5432/langfuse"
  NEXTAUTH_URL: "http://localhost:3001"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: langfuse-postgres
  namespace: langfuse
spec:
  replicas: 1
  selector:
    matchLabels:
      app: langfuse-postgres
  template:
    metadata:
      labels:
        app: langfuse-postgres
    spec:
      containers:
      - name: postgres
        image: postgres:16-alpine
        env:
        - name: POSTGRES_USER
          value: "langfuse"
        - name: POSTGRES_PASSWORD
          value: "langfuse"
        - name: POSTGRES_DB
          value: "langfuse"
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: pgdata
          mountPath: /var/lib/postgresql/data
      volumes:
      - name: pgdata
        emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: langfuse-postgres
  namespace: langfuse
spec:
  selector:
    app: langfuse-postgres
  ports:
  - port: 5432
    targetPort: 5432
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: langfuse
  namespace: langfuse
spec:
  replicas: 1
  selector:
    matchLabels:
      app: langfuse
  template:
    metadata:
      labels:
        app: langfuse
    spec:
      containers:
      - name: langfuse
        image: langfuse/langfuse:latest
        envFrom:
        - secretRef:
            name: langfuse-secrets
        env:
        - name: LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES
          value: "true"
        - name: TELEMETRY_ENABLED
          value: "false"
        ports:
        - containerPort: 3000
---
apiVersion: v1
kind: Service
metadata:
  name: langfuse
  namespace: langfuse
spec:
  selector:
    app: langfuse
  ports:
  - port: 3000
    targetPort: 3000
EOF
```

Wait for Langfuse to be ready:
```
kubectl rollout status deploy/langfuse -n langfuse
kubectl rollout status deploy/langfuse-postgres -n langfuse
```

#### Configure OTel Collector to Export to Langfuse

Langfuse accepts OTLP traces over HTTP. Update the OTel collector to include a Langfuse exporter.

Get your Langfuse API keys (from Cloud or self-hosted UI):
```
export LANGFUSE_PUBLIC_KEY=
export LANGFUSE_SECRET_KEY=
```

For self-hosted, the endpoint is `http://langfuse.langfuse.svc.cluster.local:3000`.
For cloud, it is `https://cloud.langfuse.com`.

```
kubectl create secret generic langfuse-otel-keys \
  -n telemetry \
  --from-literal=LANGFUSE_PUBLIC_KEY=$LANGFUSE_PUBLIC_KEY \
  --from-literal=LANGFUSE_SECRET_KEY=$LANGFUSE_SECRET_KEY
```

Deploy (or upgrade) the OTel collector with dual export — Tempo + Langfuse:

```
helm upgrade --install opentelemetry-collector-traces opentelemetry-collector \
  --repo https://open-telemetry.github.io/opentelemetry-helm-charts \
  --version 0.127.2 \
  --set mode=deployment \
  --set image.repository="otel/opentelemetry-collector-contrib" \
  --set command.name="otelcol-contrib" \
  --namespace=telemetry \
  -f -<<EOF
extraEnvFrom:
  - secretRef:
      name: langfuse-otel-keys

config:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317
        http:
          endpoint: 0.0.0.0:4318
  exporters:
    otlp/tempo:
      endpoint: http://tempo.telemetry.svc.cluster.local:4317
      tls:
        insecure: true
    otlphttp/langfuse:
      endpoint: http://langfuse.langfuse.svc.cluster.local:3000/api/public/otel
      headers:
        Authorization: "Basic \${env:LANGFUSE_PUBLIC_KEY}:\${env:LANGFUSE_SECRET_KEY}"
    debug:
      verbosity: detailed
  service:
    pipelines:
      traces:
        receivers: [otlp]
        processors: [batch]
        exporters: [debug, otlp/tempo, otlphttp/langfuse]
EOF
```

Verify by sending a request through agentgateway and checking the Langfuse UI:

```
# Send a test request
curl "$INGRESS_GW_ADDRESS:8080/anthropic" \
  -H content-type:application/json \
  -H "anthropic-version: 2023-06-01" \
  -d '{
  "model": "claude-sonnet-4-5-20250929",
  "messages": [{"role": "user", "content": "What is agentgateway?"}]
}' | jq

# Port-forward Langfuse UI
kubectl port-forward -n langfuse svc/langfuse 3001:3000 &
```

Open http://localhost:3001 — you should see traces with:
- `gen_ai.operation.name: chat`
- `gen_ai.provider.name: anthropic`
- `gen_ai.request.model` and `gen_ai.response.model`
- `gen_ai.usage.prompt_tokens` and `gen_ai.usage.completion_tokens`
- Request duration

---

### 5b. ELK Stack Integration

Deploy Elasticsearch, Kibana, and Filebeat for agentgateway log aggregation and analysis.

#### Deploy Elasticsearch

```
helm repo add elastic https://helm.elastic.co

helm install elasticsearch elastic/elasticsearch \
  --namespace logging \
  --create-namespace \
  --set replicas=1 \
  --set minimumMasterNodes=1 \
  --set resources.requests.cpu=500m \
  --set resources.requests.memory=1Gi \
  --set resources.limits.cpu=1 \
  --set resources.limits.memory=2Gi \
  --set persistence.enabled=false \
  --set discovery.type=single-node \
  --set esConfig."elasticsearch\.yml"="xpack.security.enabled: false"
```

#### Deploy Kibana

```
helm install kibana elastic/kibana \
  --namespace logging \
  --set service.type=ClusterIP \
  --set resources.requests.cpu=250m \
  --set resources.requests.memory=512Mi
```

Wait for both to be ready:
```
kubectl rollout status statefulset/elasticsearch-master -n logging
kubectl rollout status deploy/kibana-kibana -n logging
```

#### Deploy Filebeat DaemonSet

Filebeat collects agentgateway pod logs and ships them to Elasticsearch:

```
kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: filebeat-config
  namespace: logging
data:
  filebeat.yml: |-
    filebeat.autodiscover:
      providers:
        - type: kubernetes
          node: \${NODE_NAME}
          hints.enabled: true
          templates:
            - condition:
                contains:
                  kubernetes.namespace: "agentgateway-system"
              config:
                - type: container
                  paths:
                    - /var/log/containers/*\${data.kubernetes.container.id}.log
                  processors:
                    - dissect:
                        tokenizer: "%{timestamp} %{log_level} %{message}"
                        field: "message"
                        target_prefix: "agentgateway"
                    - add_kubernetes_metadata:
                        host: \${NODE_NAME}
                        matchers:
                          - logs_path:
                              logs_path: "/var/log/containers/"
    output.elasticsearch:
      hosts: ["http://elasticsearch-master.logging.svc.cluster.local:9200"]
      index: "agentgateway-logs-%{+yyyy.MM.dd}"
    setup.template:
      name: "agentgateway-logs"
      pattern: "agentgateway-logs-*"
    setup.ilm.enabled: false
---
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: filebeat
  namespace: logging
spec:
  selector:
    matchLabels:
      app: filebeat
  template:
    metadata:
      labels:
        app: filebeat
    spec:
      serviceAccountName: filebeat
      terminationGracePeriodSeconds: 30
      containers:
      - name: filebeat
        image: docker.elastic.co/beats/filebeat:8.17.0
        args: ["-c", "/etc/filebeat.yml", "-e"]
        env:
        - name: NODE_NAME
          valueFrom:
            fieldRef:
              fieldPath: spec.nodeName
        volumeMounts:
        - name: config
          mountPath: /etc/filebeat.yml
          readOnly: true
          subPath: filebeat.yml
        - name: varlogcontainers
          mountPath: /var/log/containers
          readOnly: true
        - name: varlogpods
          mountPath: /var/log/pods
          readOnly: true
        - name: varlibdockercontainers
          mountPath: /var/lib/docker/containers
          readOnly: true
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 200m
            memory: 256Mi
      volumes:
      - name: config
        configMap:
          name: filebeat-config
      - name: varlogcontainers
        hostPath:
          path: /var/log/containers
      - name: varlogpods
        hostPath:
          path: /var/log/pods
      - name: varlibdockercontainers
        hostPath:
          path: /var/lib/docker/containers
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: filebeat
  namespace: logging
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: filebeat
rules:
- apiGroups: [""]
  resources: ["namespaces", "pods", "nodes"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: filebeat
subjects:
- kind: ServiceAccount
  name: filebeat
  namespace: logging
roleRef:
  kind: ClusterRole
  name: filebeat
  apiGroup: rbac.authorization.k8s.io
EOF
```

Send test requests through agentgateway then verify in Kibana:

```
# Port-forward Kibana
kubectl port-forward -n logging svc/kibana-kibana 5601 &
```

1. Open http://localhost:5601
2. Go to **Stack Management** > **Index Patterns** > Create pattern: `agentgateway-logs-*`
3. Go to **Discover** — filter by `kubernetes.namespace: agentgateway-system`
4. Key fields to explore:
   - `http.status` — response codes (200, 403, 429)
   - `gen_ai.provider.name` — LLM provider
   - `gen_ai.usage.input_tokens` — token consumption
   - `duration` — request latency