# agentgateway Enterprise vs. AWS Bedrock AgentCore Gateway: MCP Feature Comparison

## Executive Summary

**AWS Bedrock AgentCore Gateway** is a fully managed, serverless AWS service focused on making it easy to connect agents to tools via MCP in a single cloud. **agentgateway Enterprise** is an open-source-core, self-hosted (or Kubernetes-native) proxy that provides a broader scope -- MCP, A2A, and LLM gateway -- with deep control-plane customization and multi-cloud/hybrid deployment.

Both act as **MCP aggregation proxies**: they sit between AI agents and upstream MCP servers/tools, presenting a unified `tools/list` to clients. But they differ significantly in deployment model, protocol depth, extensibility, and enterprise feature surface.

---

## Deployment & Operations

| Dimension | AgentCore Gateway | agentgateway Enterprise |
|-----------|------------------|------------------------|
| **Deployment model** | Fully managed SaaS (AWS) | Self-hosted: standalone binary, Kubernetes (Helm + Gateway API controller), or Docker |
| **Infrastructure** | Serverless, zero ops | You manage the infra; Kubernetes controller auto-deploys proxy pods per Gateway resource |
| **Multi-cloud** | AWS only | Any cloud, on-prem, hybrid, edge |
| **Scaling** | Automatic (AWS-managed) | HPA/VPA overlays, manual replicas, or custom autoscaler |
| **Configuration model** | AWS API / Console / CLI | YAML/JSON config file with hot-reload, or xDS from Kubernetes control plane (CRDs) |
| **Pricing** | Pay-per-use (AWS metering) | Open-source core (Apache 2.0) + Solo enterprise license |

---

## MCP Protocol Support

| Capability | AgentCore Gateway | agentgateway Enterprise |
|-----------|------------------|------------------------|
| **MCP versions** | 2025-11-25, 2025-03-26, 2025-06-18 | All versions (negotiates lowest common across upstreams) |
| **Downstream transports** | Streamable HTTP | Streamable HTTP + Legacy SSE |
| **Upstream transports** | Streamable HTTP (to MCP servers) | Streamable HTTP, SSE, **stdio** (subprocess), OpenAPI |
| **Transport translation** | MCP-to-REST (OpenAPI, Smithy, Lambda) | Any-to-any (e.g., SSE client -> stdio upstream, Streamable HTTP client -> OpenAPI upstream) |
| **stdio support** | No (cloud-native only) | Yes -- spawn local processes (npx, uvx, etc.) as MCP servers |
| **`tools/list`** | Yes | Yes |
| **`tools/call`** | Yes | Yes |
| **`prompts/list`** | Yes | Yes (single-target; limited in multiplex mode) |
| **`prompts/get`** | Yes | Yes (single-target; limited in multiplex mode) |
| **`resources/list`** | Yes | Yes (single-target only; multiplex WIP) |
| **`resources/read`** | Yes | Yes (single-target only) |
| **`resources/templates/list`** | Yes | Yes (single-target only) |

---

## Tool Aggregation & Federation

| Capability | AgentCore Gateway | agentgateway Enterprise |
|-----------|------------------|------------------------|
| **Multi-target aggregation** | Yes -- unified `tools/list` across all MCP targets | Yes -- fan-out to all targets, merge responses |
| **Tool naming** | Auto-generated: `{targetName}_{operationId}` format with configurable naming rules | `{targetName}_{toolName}` with `_` delimiter; configurable prefix mode (`Always` or `Conditional`) |
| **Prompt/resource aggregation** | Yes (tools, prompts, resources all aggregated) | Tools and prompts aggregated; resources NOT aggregated in multiplex mode (GitHub issue #404) |
| **Protocol version negotiation** | Not documented | Yes -- gateway selects lowest common version across all upstreams |
| **Instructions merging** | Not documented | Yes -- each upstream's instructions labeled with `[serverName]` and concatenated |

---

## Tool Discovery & Search

| Capability | AgentCore Gateway | agentgateway Enterprise |
|-----------|------------------|------------------------|
| **Semantic search** | Yes -- built-in `x_amz_bedrock_agentcore_search` tool with vector embeddings, natural language queries | No built-in semantic search |
| **Progressive disclosure** | Not a native feature (achievable via semantic search) | Yes -- `Search` tool mode exposes only `get_tool` and `invoke_tool` meta-tools; reduces context window |
| **Capability sync** | Implicit (on create/update) + explicit (`SynchronizeGatewayTargets` API) | Real-time via live MCP connections; file-watch for config changes; xDS push for Kubernetes |
| **Listing modes** | `DEFAULT` (pre-indexed) or `DYNAMIC` (live forward) | Always live (connections maintained to upstreams) |
| **Tool catalog persistence** | Server-side (AWS-managed, survives restarts) | In-memory; sessions reconstructed on reconnect |

---

## Target / Backend Types

| Target Type | AgentCore Gateway | agentgateway Enterprise |
|------------|------------------|------------------------|
| **Remote MCP servers** | Yes (Streamable HTTP) | Yes (Streamable HTTP + SSE) |
| **Local subprocess (stdio)** | No | Yes (spawn npx, uvx, docker, etc.) |
| **OpenAPI -> MCP** | Yes (OpenAPI 3.0/3.1, operationId-based) | Yes (OpenAPI 3.0, operationId-based, full schema resolution) |
| **Smithy -> MCP** | Yes (AWS Smithy models) | No |
| **Lambda -> MCP** | Yes (direct Lambda invocation) | No (would need OpenAPI/HTTP wrapper) |
| **API Gateway -> MCP** | Yes (REST API stages) | No (use as generic HTTP backend) |
| **Built-in integrations** | Yes -- 20+ templates (Slack, Jira, Salesforce, Teams, etc.) | No built-in templates |
| **Kubernetes service discovery** | No | Yes -- label selectors for dynamic MCP target discovery |
| **Static host/port** | Yes | Yes |
| **HTTP passthrough targets** | Yes (for AgentCore Runtime agents) | Yes (generic HTTP/TCP/TLS proxy) |

---

## Authentication & Authorization

| Capability | AgentCore Gateway | agentgateway Enterprise |
|-----------|------------------|------------------------|
| **Inbound auth types** | OAuth (JWT), IAM (SigV4), authenticate-only, none | JWT (multi-provider), API keys, Basic auth, OAuth/OIDC, MCP OAuth (RFC 8707), external auth |
| **MCP OAuth spec (RFC 8707)** | Not documented as native | Yes -- full implementation: `/.well-known/oauth-protected-resource`, IdP-specific adapters (Auth0, Keycloak), CORS handling |
| **Outbound auth types** | OAuth (2LO client credentials, 3LO auth code + PKCE), IAM SigV4, API keys, none | Passthrough, inline key, AWS (SigV4 + explicit/implicit creds), Azure (client secret, managed identity, workload identity), GCP (access/ID token) |
| **3-Legged OAuth (3LO)** | Yes -- full auth code flow with URL session binding for MCP server targets | Enterprise: full STS with dual-OAuth, PKCE, PAR, DCR, Entra OBO |
| **MCP-level RBAC** | Lambda interceptors for tool/operation/parameter-level access control | CEL-based RBAC: tool-level, prompt-level, resource-level filtering with JWT claims, source IP, etc. |
| **RBAC enforcement** | Pre-execution via REQUEST interceptors | Inline: filters `tools/list` responses, blocks unauthorized `tools/call`, applies to search mode meta-tools too |
| **Policy language** | Lambda code (any language) + Cedar for resource policies | CEL expressions (e.g., `mcp.tool.name == "echo" && jwt.sub == "admin"`) |
| **Identity service** | AgentCore Identity (managed workload identities, credential providers) | Kubernetes ServiceAccount JWT, external IdP integration |

---

## Session Management

| Capability | AgentCore Gateway | agentgateway Enterprise |
|-----------|------------------|------------------------|
| **Stateful sessions** | Managed by AWS (serverless) | Yes -- `Stateful` mode with in-memory `SessionManager`, `Mcp-Session-Id` header, GET/DELETE support |
| **Stateless mode** | Not documented | Yes -- `Stateless` mode: each POST auto-wraps with Initialize/Initialized, no server-side state |
| **Session affinity** | Managed by AWS | Yes -- backend pinning: first request resolves endpoint, subsequent requests stick to same pod |
| **Session resume** | Not documented | Yes -- `SessionState::MCP` encodes per-target session IDs and pinned backends for resume |
| **Session encryption** | AWS-managed KMS | `SESSION_KEY` (32-byte hex) for cookie-based session persistence |

---

## Failure Handling

| Capability | AgentCore Gateway | agentgateway Enterprise |
|-----------|------------------|------------------------|
| **Failure modes** | Not documented (likely fail-closed) | Configurable: `FailClosed` (default) or `FailOpen` (skip failed targets, continue with healthy ones) |
| **Partial degradation** | Not documented | Yes -- FailOpen skips failed upstreams during fanout, initialization, stream merging |
| **Health tracking** | Not documented | Backend health tracking with EWMA scores, outlier detection, eviction with multiplicative backoff |

---

## Traffic Management & Policies

| Capability | AgentCore Gateway | agentgateway Enterprise |
|-----------|------------------|------------------------|
| **Rate limiting** | Not built-in (achievable via interceptors) | Local (token bucket per route), remote (external service), enterprise global (RateLimitConfig CRD) |
| **Request/response transformation** | Lambda interceptors (REQUEST/RESPONSE) | CEL-based transformations: header set/add/remove, body rewriting, metadata injection |
| **Traffic routing rules** | Gateway rules with priority, principal/path matching, weighted traffic splits | HTTPRoute/GRPCRoute/TCPRoute/TLSRoute matching (path, header, query, method), weighted backends |
| **A/B testing** | Yes -- weighted config bundle overrides | Yes -- weighted backend routing |
| **CORS** | Not documented | Full CORS policy support |
| **CSRF** | Not documented | CSRF protection with origin allowlisting |
| **Retries** | Not documented | HTTPRoute retry policy |
| **Timeouts** | Not documented | Request/response timeouts at route and backend level |
| **Header propagation** | Yes (configurable) | Yes (transformation policies) |

---

## Observability

| Capability | AgentCore Gateway | agentgateway Enterprise |
|-----------|------------------|------------------------|
| **Metrics** | CloudWatch (AWS-native) | Prometheus: `mcp_requests` counter with method/server/resource/tool labels; full HTTP metrics |
| **Tracing** | Not detailed (likely CloudWatch/X-Ray) | OpenTelemetry: per-MCP-operation spans, OTLP export, CEL-based sampling |
| **Logging** | CloudWatch Logs | Structured request logging with `mcp.tool.name`, `mcp.tool.arguments`, `mcp.tool.result`, `mcp.tool.error`, `session_id`; CEL-based log filtering |
| **Auditing** | Built-in auditing | CEL-based access log with custom attributes, OTLP log export |
| **Admin UI** | AWS Console | Built-in Next.js admin dashboard with playground, CEL editor, config management |
| **Integration** | AWS-native (CloudWatch, X-Ray) | Vendor-neutral (Prometheus, Grafana, Jaeger, any OTLP collector) |

---

## AI / LLM Specific (Beyond MCP)

| Capability | AgentCore Gateway | agentgateway Enterprise |
|-----------|------------------|------------------------|
| **LLM gateway** | No (separate Bedrock Runtime) | Yes -- unified OpenAI-compatible API routing to OpenAI, Anthropic, Gemini, Vertex, Bedrock, Azure OpenAI |
| **A2A protocol** | No | Yes -- Google A2A with capability discovery, modality negotiation |
| **Prompt enrichment** | No | Yes -- prepend/append prompts to AI requests |
| **Prompt guards** | Via AgentCore Policy (Cedar-based, tool-call interception) | Multi-layer: regex, OpenAI moderation, AWS Bedrock Guardrails, Google Model Armor, Azure Content Safety, custom webhooks |
| **Token counting** | Via AgentCore Observability | Built-in per-request token metrics (input/output/cached/reasoning/image/audio/text) |
| **Model failover** | No | Yes -- priority-based provider groups with health tracking |
| **Inference routing** | No | Yes -- Kubernetes Inference Gateway extensions (GPU utilization, KV cache, LoRA adapters) |
| **Budget controls** | No | Token/spend budget controls per route |

---

## Extensibility

| Capability | AgentCore Gateway | agentgateway Enterprise |
|-----------|------------------|------------------------|
| **Custom logic** | Lambda interceptors (REQUEST/RESPONSE) | CEL expressions for auth, transformation, rate-limit keys, log filtering; external auth/proc via gRPC |
| **Plugin architecture** | No (managed service) | Yes -- `AgwPlugin` interface for contributing policies, backends, custom resource types |
| **Custom CRDs** | No | Yes -- extensible via Kubernetes CRDs with controller reconciliation |
| **Config bundles** | Yes -- versioned configuration overrides | Strategic merge patch overlays on Deployment, Service, SA, PDB, HPA |

---

## When to Choose Which

| Scenario | Better Fit |
|----------|-----------|
| AWS-native, zero-ops, quick start with managed tools | **AgentCore Gateway** |
| Built-in integrations (Slack, Jira, Salesforce, etc.) | **AgentCore Gateway** |
| Semantic/natural-language tool search | **AgentCore Gateway** |
| Lambda/Smithy as MCP tool sources | **AgentCore Gateway** |
| Multi-cloud, hybrid, or on-prem deployment | **agentgateway Enterprise** |
| Local/stdio MCP servers (npx, uvx) | **agentgateway Enterprise** |
| Unified LLM + MCP + A2A gateway | **agentgateway Enterprise** |
| Deep MCP protocol support (all transports, session modes, failure modes) | **agentgateway Enterprise** |
| CEL-based fine-grained RBAC on tools/prompts/resources | **agentgateway Enterprise** |
| Kubernetes-native with Gateway API | **agentgateway Enterprise** |
| AI prompt guards, model failover, token budgets | **agentgateway Enterprise** |
| Vendor-neutral observability (Prometheus/OTLP) | **agentgateway Enterprise** |
| Token exchange, Entra OBO, dual-OAuth flows | **agentgateway Enterprise** |
| Progressive disclosure (search mode) to reduce context window | **agentgateway Enterprise** |

---

## Why agentgateway Enterprise Is the Stronger MCP Gateway

### 1. Protocol Depth and Completeness

AgentCore Gateway speaks Streamable HTTP to upstream MCP servers and translates non-MCP sources (Lambda, OpenAPI, Smithy) into MCP. That covers a specific set of cloud-native use cases well, but agentgateway goes significantly deeper into the MCP protocol itself:

- **All four upstream transports**: Streamable HTTP, SSE, stdio, and OpenAPI. Stdio is critical -- the majority of the MCP ecosystem today runs as local subprocesses (`npx @modelcontextprotocol/server-*`). AgentCore Gateway cannot connect to these at all.
- **Transport translation**: A client speaking SSE can transparently reach a stdio backend, or a Streamable HTTP client can reach an SSE server. AgentCore Gateway only does protocol conversion from non-MCP formats (Lambda, Smithy) into MCP, not between MCP transports.
- **Protocol version negotiation**: agentgateway negotiates the lowest common MCP version across all upstreams and presents a coherent version to the client. This matters as the MCP spec evolves and you have servers at different versions.
- **Legacy SSE downstream**: Many existing MCP clients still only support the older SSE transport. agentgateway serves both Streamable HTTP and SSE downstream simultaneously. AgentCore Gateway only exposes Streamable HTTP.

### 2. Real MCP Session Semantics

MCP sessions are stateful by design -- servers maintain context across requests within a session. agentgateway implements this faithfully:

- **Stateful mode** with session persistence, `Mcp-Session-Id` tracking, and GET/DELETE lifecycle operations.
- **Backend pinning**: When an MCP backend has multiple replicas, the first request resolves to a specific pod, and all subsequent session requests are pinned to that pod. This is essential for stateful MCP servers that hold in-memory state.
- **Stateless mode** for servers that don't need session state, with automatic Initialize/Initialized wrapping per request.
- **Session resume** with encoded session state (per-target session IDs and pinned backend addresses).

AgentCore Gateway abstracts sessions behind a serverless model. You don't control affinity, pinning, or session lifecycle. For simple stateless tool invocations this is fine, but for MCP servers that maintain conversation context, tool state, or subscriptions, the lack of session control is a real limitation.

### 3. Fine-Grained, Inline RBAC on MCP Operations

This is one of the sharpest differentiators. agentgateway implements **CEL-based RBAC that operates inside the MCP protocol**, not as an external sidecar:

- **Filtering on list responses**: Unauthorized tools are silently removed from `tools/list` before the client ever sees them. Same for prompts and resources. An agent with `role=analyst` sees only analyst-permitted tools; an agent with `role=admin` sees everything.
- **Blocking on call requests**: Unauthorized `tools/call` returns `"Unknown tool"` -- it doesn't even reveal that the tool exists.
- **CEL expressions combine MCP context with auth context**: `mcp.tool.name == "delete_record" && jwt.role != "admin"` -- this is evaluated per-request with near-zero overhead.
- **Applies to search mode too**: Both `get_tool` and `invoke_tool` meta-tools enforce RBAC before execution.

AgentCore Gateway's approach is Lambda interceptors. You write a Lambda function, deploy it, manage its IAM permissions, handle cold starts, and pay per invocation. It works, but it's operationally heavy for something that should be a policy declaration, and it adds latency on every request (Lambda cold/warm start vs. inline CEL evaluation in microseconds).

### 4. Progressive Disclosure (Search Mode)

AgentCore Gateway has semantic search -- a powerful feature for finding tools by natural language query. But it still returns full tool definitions to the LLM, consuming context window tokens.

agentgateway's `Search` tool mode takes a fundamentally different approach to the same problem:

- Only two meta-tools are exposed: `get_tool` (returns a single tool's schema) and `invoke_tool` (executes a tool by name).
- The LLM first sees a compact list of available tool names in the `get_tool` description. It can then selectively retrieve full schemas for only the tools it needs.
- This **dramatically reduces token consumption** -- instead of pushing 50 tool schemas into every prompt, the LLM pulls 2-3 as needed.
- RBAC is enforced on both meta-tools, so the filtered tool list respects access control.

These two approaches are actually complementary -- semantic search finds the right tool, progressive disclosure avoids loading all tool schemas into context -- but only agentgateway has the latter today.

### 5. Failure Resilience

MCP tool federation inherently involves multiple upstream servers. Some will fail. agentgateway gives you explicit control:

- **FailOpen mode**: Skip failed targets during initialization, fanout, and stream merging. Return results from healthy servers. This is critical for production MCP deployments where one flaky server shouldn't take down the entire tool surface.
- **FailClosed mode**: Any failure aborts the request. Appropriate for high-integrity workflows.
- **Backend health tracking**: EWMA-based health scores with outlier detection, automatic eviction, and multiplicative backoff recovery. Unhealthy MCP server replicas are taken out of rotation and gradually re-introduced.

AgentCore Gateway doesn't document failure modes. As a managed service, AWS presumably handles retries and health internally, but you have no visibility into or control over the behavior. If an MCP server target returns errors, you can't configure whether the gateway should degrade gracefully or fail hard.

### 6. MCP-Native Authentication (RFC 8707)

agentgateway implements the **MCP OAuth Resource Metadata specification** natively:

- Serves `/.well-known/oauth-protected-resource` with proper resource metadata.
- Serves `/.well-known/oauth-authorization-server` as a proxy to the upstream IdP (with CORS injection).
- IdP-specific adapters for Auth0 (RFC 8707 non-compliance workaround) and Keycloak (OIDC discovery instead of RFC 8414, Dynamic Client Registration proxy for CORS).
- Three enforcement modes: `Strict` (401 with WWW-Authenticate), `Optional` (validate if present), `Permissive` (never reject).

This means MCP clients that implement the standard MCP auth flow work out of the box -- they discover the authorization server from the gateway's well-known endpoints, complete the OAuth flow, and present tokens. AgentCore Gateway uses AWS-specific auth mechanisms (IAM SigV4, its own Identity service) which are powerful within AWS but not interoperable with the MCP auth specification.

### 7. Observability That Understands MCP

agentgateway's telemetry is MCP-aware, not just HTTP-aware:

- **`mcp_requests` Prometheus counter** with labels for `method` (`tools/list`, `tools/call`, `initialize`), `server` (target name), `resource` (tool name), and `resource_type`. You can graph tool invocation rates per server, alert on error rates per tool, and track which tools are actually being used.
- **Structured request logs** include `mcp.tool.name`, `mcp.tool.arguments`, `mcp.tool.result`, and `mcp.tool.error`. This is auditable tool-call logging, not just HTTP access logs.
- **OpenTelemetry spans** are created per MCP operation with the tool/server name in the span name. Traces through a multiplexed MCP gateway show exactly which upstream handled each tool call.
- **CEL-based log filtering**: You can write expressions like `mcp.tool.name == "sensitive_tool"` to selectively log certain tool calls at a different level.

AgentCore Gateway routes observability through CloudWatch, which is capable but AWS-locked. You can't export MCP-specific metrics to Prometheus/Grafana, Datadog, or any non-AWS observability stack without additional work.

### 8. It's Also an LLM and A2A Gateway

This isn't strictly an MCP comparison, but it matters for real-world agent architectures. An agent doesn't just call MCP tools -- it also talks to LLMs and other agents. agentgateway handles all three:

- **LLM routing** with unified OpenAI-compatible API, multi-provider failover, prompt guards, token budgets, and model aliases.
- **A2A protocol** support for agent-to-agent communication.
- **Shared policy surface**: The same JWT auth, CEL RBAC, rate limiting, transformation, and observability policies apply uniformly across MCP, LLM, and A2A traffic.

With AgentCore Gateway, you need separate services for each: AgentCore Gateway for MCP tools, Bedrock Runtime or direct provider APIs for LLMs, and custom code for A2A. Each has its own auth, observability, and policy model.

### 9. No Vendor Lock-In

agentgateway runs anywhere: a laptop, a VM, a Kubernetes cluster on any cloud, an air-gapped environment. The configuration is portable YAML or Kubernetes CRDs. The observability is OpenTelemetry. The auth is standard JWT/OAuth/OIDC.

AgentCore Gateway is an AWS service. Your gateway configuration, tool definitions, credential providers, identity management, and operational data all live in AWS APIs. Moving to another cloud or on-prem means rebuilding everything.

### 10. You Control the Data Plane

Every MCP `tools/call` request carries tool arguments and returns tool results. This is often sensitive data -- database queries, customer records, internal API payloads. With agentgateway, the data plane runs in your infrastructure, under your network policies, your encryption, your audit controls. No tool call data leaves your environment unless you explicitly route it there.

With AgentCore Gateway, tool call arguments and results transit through an AWS-managed service. For many enterprises, this is acceptable. For regulated industries, air-gapped environments, or organizations with strict data residency requirements, it is not.
