```
curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash
```

```
nemoclaw --version
```

```
❯ nemoclaw --version
nemoclaw v0.0.38
```

```
NEMOCLAW_GATEWAY_PORT=8081 \
NEMOCLAW_PROVIDER=custom \
NEMOCLAW_ENDPOINT_URL=http://YOUR_GW_IP_OR_HOST:YOUR_PORT/v1 \
NEMOCLAW_MODEL=placeholder-model \
COMPATIBLE_API_KEY=agentgateway-placeholder \
NEMOCLAW_POLICY_TIER=balanced \
nemoclaw onboard \
--non-interactive \
--yes \
--yes-i-accept-third-party-software \
--name agentgateway-assistant
```

```
nemoclaw agentgateway-assistant doctor
```

```
nemoclaw agentgateway-assistant connect
```

```
2026-05-10T15:16:07.118334Z     info    request gateway=agentgateway-system/agentgateway-openshell listener=http route=agentgateway-system/openshell-openai endpoint=api.anthropic.com:443 src.addr=10.224.0.4:19129 http.method=GET http.host=20.253.171.166 http.path=/v1/models http.version=HTTP/1.1 http.status=200 protocol=llm duration=160ms
```

Step-by-step instructions: https://www.cloudnativedeepdive.com/nemoclaw-agentgateway-inference-routing-for-llms/