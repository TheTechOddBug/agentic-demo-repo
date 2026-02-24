1. JWT policy

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
      mode: Strict
      providers:
        - issuer: solo.io
          jwks:
            inline: '{"keys":[{"use":"sig","kty":"RSA","kid":"5891645032159894383","n":"5Zb1l_vtAp7DhKPNbY5qLzHIxDEIm3lpFYhBTiZyGBcnre8Y8RtNAnHpVPKdWohqhbihbVdb6U7m1E0VhLq7CS7k2Ng1LcQtVN3ekaNyk09NHuhl9LCgqXT4pATt6fYTKtZ__tEw4XKt3QqVcw7hV0YaNVC5xXGYVBh5_2-K5aW9u2LQ7FSax0jPhWdoUB3KbOQfWNOA3RwOqYn4gmc9wVToVLv6bXCVhIYWKnAVcX89C00eM7uBHENvOydD14-ZnLb4pzz2VGbU6U65odpw_i4r_mWXvoUgwogXAXp80TsYwMzLHcFo4GVDNkaH0hjuLJCeISPfYtbUJK6fFaZGBw","e":"AQAB","x5c":["MIIC3jCCAcagAwIBAgIBJTANBgkqhkiG9w0BAQsFADAXMRUwEwYDVQQKEwxrZ2F0ZXdheS5kZXYwHhcNMjUxMjE4MTkzNDQyWhcNMjUxMjE4MjEzNDQyWjAXMRUwEwYDVQQKEwxrZ2F0ZXdheS5kZXYwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQDllvWX++0CnsOEo81tjmovMcjEMQibeWkViEFOJnIYFyet7xjxG00CcelU8p1aiGqFuKFtV1vpTubUTRWEursJLuTY2DUtxC1U3d6Ro3KTT00e6GX0sKCpdPikBO3p9hMq1n/+0TDhcq3dCpVzDuFXRho1ULnFcZhUGHn/b4rlpb27YtDsVJrHSM+FZ2hQHcps5B9Y04DdHA6pifiCZz3BVOhUu/ptcJWEhhYqcBVxfz0LTR4zu4EcQ287J0PXj5mctvinPPZUZtTpTrmh2nD+Liv+ZZe+hSDCiBcBenzROxjAzMsdwWjgZUM2RofSGO4skJ4hI99i1tQkrp8VpkYHAgMBAAGjNTAzMA4GA1UdDwEB/wQEAwIFoDATBgNVHSUEDDAKBggrBgEFBQcDATAMBgNVHRMBAf8EAjAAMA0GCSqGSIb3DQEBCwUAA4IBAQBeA8lKrnfRjo18RkLBqVKuO441nZLFGKrJwpJu+G5cVOJ06txKsZEXE3qu2Yh9abeOJkC+SsWMELWHYNJlip4JGE0Oby7chol+ahrwBILUixBG/qvhwJG6YntoDZi0wbNFqQiQ6FZt89awcs2pdxL5thYR/Pqx4QXN8oKd4DNkcX5vWdz9P6nstLUmrEBV4EFs7fY0L/n3ssDvyZ3xfpM1Q/CQFz4OqB4U20+Qt6x7eap6qhTSBZt8rZWIiy57BsSww12gLYYU1x+Klg1AdPsVrcuvVdiZM1ru232Ihip0rYH7Mf7vcN+HLUrjpXvMoeyWRwbB61GPsXz+BTksqoql"]}]}'
EOF
```

The JWT to use for token-based auth in MCP Inspector
```
"eyJhbGciOiJSUzI1NiIsImtpZCI6IjU4OTE2NDUwMzIxNTk4OTQzODMiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJzb2xvLmlvIiwic3ViIjoiYm9iIiwiZXhwIjoyMDczNjcwNDgyLCJuYmYiOjE3NjYwODY0ODIsImlhdCI6MTc2NjA4NjQ4Mn0.ZHAw7nbANhnYvBBknN9_ORCQZ934Vv_vAelx8odC3bsC5Yesif7ZSsnEp9zFjGG6wBvvV3LrtuBuWx9mTYUZS6rwWUKsvDXyheZXYRmXndOqpY0gcJJaulGGqXncQDkmqDA7ZeJLG1s0a6shMXRs6BbV370mYpu8-1dZdtikyVL3pC27QNei35JhfqdYuMw1fMptTVzypx437l9j2htxqtIVgdWUc1iKD9kNKpkJ5O6SNbi6xm267jZ3V_Ns75p_UjLq7krQIUl1W0mB0ywzosFkrRcyXsBsljXec468hgHEARW2lec8FEe-i6uqRuVkFD-AeXMfPhXzqdwysjG_og"
```

```
kubectl apply -f- <<EOF
apiVersion: enterpriseagentgateway.solo.io/v1alpha1
kind: EnterpriseAgentgatewayPolicy
metadata:
  name: mcp-tool-access
  namespace: agentgateway-system
spec:
  targetRefs:
    - group: agentgateway.dev
      kind: AgentgatewayBackend
      name: demo-mcp-server
  backend:
    mcp:
      authorization:
        action: Allow
        policy:
          matchExpressions:
            - 'jwt.sub == "bob" && mcp.tool.name == "add"'
EOF
```