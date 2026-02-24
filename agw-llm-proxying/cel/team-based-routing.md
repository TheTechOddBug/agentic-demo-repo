```
kubectl apply -f - <<EOF
apiVersion: enterpriseagentgateway.solo.io/v1alpha1
kind: EnterpriseAgentgatewayPolicy
metadata:
  name: developer-gemini-policy
  namespace: agentgateway-system
spec:
  targetRefs:
    - group: gateway.networking.k8s.io
      kind: HTTPRoute
      name: google
  traffic:
    authorization:
      action: Allow
    policy:
      matchExpressions:
        # PLEASE NOTE: The header name you use in the CEL expression needs to match whatever
        #              your authentication/identity layer injects into the request. You don't 
        #              pick it arbitrarily. Its determined by your upstream auth system.
        - "request.headers['x-user-group'] == 'developer'"
        - "request.headers['x-llm'] == 'azureopenai'"
EOF
```

```
  curl -X POST "http://$INGRESS_GW_ADDRESS:8080/azureopenai \
    -H "Content-Type: application/json" \
    -H "x-user-group: developer" \
    -d '{"model":"gemini/gemini-2.0-flash","messages":[{"role":"user","content":"Hello"}]}'
```