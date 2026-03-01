# ABAC With Agentgateway

agentgateway has multiple methods of implementing and helping with ABAC. The goal of this "doc" (which will hopefully turn into a real doc), is to be a living doc that as we go, we can add what works with agetngateway for ABAC.

## Implementations

1. Guardrails

Because the guardrail webhook is your own service, you can make it attribute-aware. If agentgateway passes enough context for your use case, or if you can derive it from headers/body/session/token context available to the webhook.

With Agentgateway 2.1.x, the guardrail webhook is a synchronous hook that Agentgateway calls before the LLM request and after the LLM response.

If you google guarddrails, you'll see an explanation about it being real-time policy enforcement. If it is "real-time policy enforcement", that means the guarddrail webhook can work with a policy enforcement tool like OPA or Kyverno. For example, if a request comes into agentgateway, the guarddrails webhook can call to OPA or Kyverno to ensure that the policies that are set are met.

Client → Agentgateway → Guardrail webhook → OPA or Kyverno → webhook returns allow/modify/reject → Agentgateway continues or blocks

Use ABAC for:
- who can access which route/model/tool
- tenant/team/role/claim-based decisions
- environment-aware authorization decisions

Use guardrails for:
- PII masking
- prompt/response moderation
- output schema/JSON validation
- jailbreak/injection inspection
- response redaction or rewriting


2. MCP Server Tool Access

Tools can be exposed and seen based on a policy from policy enforcement. It dynamically adjusts so Agents can only see the tools they have access to.

The [tool-access guide](https://docs.solo.io/agentgateway/2.1.x/mcp/tool-access/) shows CEL expressions over both JWT claims and resource attributes like tool name, for example:

```
jwt.sub == "alice"

mcp.tool.name == "add_issue_comment"

jwt.sub == "alice" && mcp.tool.name == "add_issue_comment"
```


3. BYO Policy Enforcement

You can use OPA, Kyverno, or any other policy enforcement platform/tool you'd like within your environment. Agentgateway can call out to it for authorization decisions.

BYO external auth means that agentgateway can call your gRPC external authorization service with headers, path, and method, and that service can make decisions using tokens, headers, database lookups, etc. It can also optionally inject headers back into the request. That is the right path when your policy depends on business data like account tier, project membership, entitlements, or time-based rules.

https://docs.solo.io/agentgateway/2.1.x/security/extauth/byo-ext-auth-service/

Sidenote: For attribute enrichment, ExtProc is useful when the attributes are not already present as headers/claims. The docs say ExtProc can read and modify headers, body, and trailers, and can terminate the request.


4. Token Exchange

On-Behalf-Of/Elicitation. This feeds ABAC because the exchanged tokens carry scoped claims/attributes that downstream policy engines can evaluate.

5. CEL

Common Expression Language is very similar to, if you need a comparison, if statements/logic. You can specify, from a transformation policy perspective, requests or responses on specific parameters.

Agentgateway’s CEL-based auth can evaluate request attributes. Agentgateway proxies use CEL expressions to match requests or responses on parameters such as request headers or source address, and allow/deny based on whether the condition matches.


Please note, this is more coarse-grained than fine-grained, but it's a good RBAC primitive to have if you have any workflows that require the standard roles/permissions approach.

Example:
```
apiVersion: enterpriseagentgateway.solo.io/v1alpha1
kind: EnterpriseAgentgatewayPolicy
metadata:
  name: rbac-policy
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
          - "request.headers['x-llm'] == 'gemini'"
```