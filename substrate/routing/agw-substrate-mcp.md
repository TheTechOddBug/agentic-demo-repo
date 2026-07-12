
# agentgateway + Agent Substrate: Route An MCP Server and Scale

"An MCP Tool Server That Exists Only When Called" is the gist of this lab.

agentgateway exposes one stable `/mcp` endpoint. Behind it, the actual
MCP server is a Substrate actor. Suspend the actor and its process disappears
from the worker. Send the next MCP tool call through agentgateway and
Substrate restores the server before forwarding the request.

This connects two separate control planes:

1. **agentgateway** understands MCP: sessions, `tools/list`, `tools/call`,
   policy, metrics, and one stable client-facing endpoint.
2. **Agent Substrate** understands actor lifecycle: snapshot, release the
   worker, restore on demand, and route by actor DNS name.

The request path is:

```text
MCP client
  -> agentgateway /mcp
  -> everything.tools.actors.resources.substrate.ate.dev:80/mcp
  -> Kubernetes DNS stub domain
  -> atenet-router
  -> ResumeActor (if suspended)
  -> restored MCP server on a warm Substrate worker
```

The result is an MCP endpoint with gateway-level governance and
actor-level scale-to-zero.

> **Be precise about "scale-to-zero."** The MCP server process scales to
> zero: while the actor is suspended it owns no worker and has no running
> container process. The Substrate `WorkerPool` still keeps one generic pod
> warm so this or another actor can resume quickly. This is pooled capacity,
> not Kubernetes Deployment replicas dropping to zero.

## What this lab proves

| Beat | Proof |
|---|---|
| MCP server as an actor | The reference `mcp/everything` Streamable HTTP server runs inside a gVisor-backed ActorTemplate instead of a Deployment. |
| agentgateway to actor DNS | An `AgentgatewayBackend` targets the actor's uniform DNS name, while `hostRewrite: Auto` preserves the hostname at the Substrate router. |
| First-call wake | The actor starts `STATUS_SUSPENDED`; the MCP `initialize` request causes atenet to invoke `ResumeActor` before forwarding it. |
| Session survives suspension | Suspend the actor after an MCP handshake, then reuse the same client session ID for `tools/call`. Full-state restore preserves the server-side MCP session. |
---

## Prerequisites

Confirm the Substrate Control Planes are healthy:

```bash
kubectl get pods -n ate-system
kubectl get pods -n agentgateway-system
kubectl get gatewayclass agentgateway
```

Build `kubectl-ate` from the same Substrate checkout used by this lab. Older
plugin binaries predate Atespaces and fail with `unknown flag: --atespace`:

```bash
go install ./cmd/kubectl-ate
export PATH="$(go env GOPATH)/bin:$PATH"
rehash 2>/dev/null || true

command -v kubectl-ate
kubectl ate create actor --help | grep atespace
```

The final command must show `--atespace`. If it does not, another
`kubectl-ate` binary appears earlier on `PATH`; invoke
`$(go env GOPATH)/bin/kubectl-ate` directly or remove the stale binary.

---

# Part 1: Deployment & Configuration

## Step 1: Prepare the Substrate environment

**Why `ko`?**: The source-oriented development manifest does not initially point to a prebuilt, pullable image. `ko` builds that package into a container, pushes it, and replaces the `ko://` reference with the resulting registry image. This is specifically the `ateom-gvisor` helper image, not gVisor itself. It contains the `ATE` component that controls actor workloads through gVisor. The actual `runsc` sandbox binary is supplied separately through the selected SandboxConfig. In the below, its only used to pull/store the `ateom` image. The MCP creation via the Template is done with standard ATE CRDs.

Set the snapshot bucket and the registry where `ko` will publish the
`ateom-gvisor` image. If the Substrate environment file is already
configured, source it:

```bash
source .ate-dev-env.sh

: "${BUCKET_NAME:?BUCKET_NAME must name the existing Substrate snapshot bucket}"
: "${KO_DOCKER_REPO:?KO_DOCKER_REPO must name a writable container registry}"
```

Otherwise, export both values explicitly:

```bash
export BUCKET_NAME="your-substrate-snapshot-bucket"
export KO_DOCKER_REPO="gcr.io/your-project-id/ate-images"
```

`BUCKET_NAME` becomes the `gs://` snapshot location in the ActorTemplate.
`KO_DOCKER_REPO` is required separately because `ko apply` must push the
locally built `ateom-gvisor` image before applying the WorkerPool CRD.

Select a node pool configured with the GKE Metadata Server. Snapshot upload
uses the `ate-system/atelet` Workload Identity principal, so a pool without
`GKE_METADATA` can run the worker but fails checkpoint upload with
`Provided scope(s) are not authorized`:

```bash
export SUBSTRATE_NODE_POOL="substrate-gvisor"

gcloud container node-pools describe "$SUBSTRATE_NODE_POOL" \
  --cluster="$CLUSTER_NAME" \
  --location="$CLUSTER_LOCATION" \
  --project="$PROJECT_ID" \
  --format='value(config.workloadMetadataConfig.mode)'
```

The command must print `GKE_METADATA`. Use the pool configured for Substrate
in your cluster; `substrate-gvisor` is the name used by the setup tooling,
not a universal GKE name. Check that pool's taints too:

```bash
kubectl get nodes \
  -l cloud.google.com/gke-nodepool="$SUBSTRATE_NODE_POOL" \
  -o jsonpath='{.items[*].spec.taints}{"\n"}'
```

The setup-created pool uses
`sandbox.gke.io/runtime=gvisor:NoSchedule`, which the WorkerPool manifest
below explicitly tolerates. If your selected pool uses a different taint,
adjust the toleration to match it.

---

## Step 2: Build and push the current Everything MCP image

The current official Everything source and npm package support native
Streamable HTTP, but the published `mcp/everything` image used by older
examples contains a stale stdio-only build. Build the official npm release's
exact Git commit and push it to the same registry used for Substrate images.

Pin both the package version and its npm provenance commit so rerunning this
lab cannot silently build different source:

```bash
export EVERYTHING_VERSION="2026.7.4"
export EVERYTHING_GIT_SHA="6dd0a683e198783e30feabf7abaf42f925bd18b1"
export EVERYTHING_IMAGE_TAG="${KO_DOCKER_REPO}/everything-mcp:${EVERYTHING_VERSION}"

export EVERYTHING_SRC="$(mktemp -d)/servers"
git clone https://github.com/modelcontextprotocol/servers.git "$EVERYTHING_SRC"
git -C "$EVERYTHING_SRC" checkout --detach "$EVERYTHING_GIT_SHA"
test "$(git -C "$EVERYTHING_SRC" rev-parse HEAD)" = "$EVERYTHING_GIT_SHA"
```

The upstream Dockerfile uses a BuildKit cache mount. Create a small Cloud
Build definition that enables BuildKit and builds that Dockerfile from the
repository root:

```bash
cat >"$EVERYTHING_SRC/cloudbuild.everything.yaml" <<'EOF'
steps:
- name: gcr.io/cloud-builders/docker
  env:
  - DOCKER_BUILDKIT=1
  args:
  - build
  - --file
  - src/everything/Dockerfile
  - --tag
  - ${_IMAGE}
  - .
images:
- ${_IMAGE}
EOF

gcloud builds submit "$EVERYTHING_SRC" \
  --project="$PROJECT_ID" \
  --config="$EVERYTHING_SRC/cloudbuild.everything.yaml" \
  --substitutions="_IMAGE=$EVERYTHING_IMAGE_TAG"
```

ActorTemplate images must be immutable because changing an image invalidates
its snapshots. Resolve the pushed tag to its registry digest and use only that
digest-qualified reference below:

```bash
export EVERYTHING_IMAGE_DIGEST=$(gcloud container images describe \
  "$EVERYTHING_IMAGE_TAG" --format='value(image_summary.digest)')
export MCP_IMAGE="${KO_DOCKER_REPO}/everything-mcp@${EVERYTHING_IMAGE_DIGEST}"

: "${EVERYTHING_IMAGE_DIGEST:?failed to resolve the pushed image digest}"
printf 'MCP_IMAGE=%s\n' "$MCP_IMAGE"
```

For release `2026.7.4`, the validated image contains
`node /app/dist/index.js streamableHttp` and serves the session-based MCP
endpoint at `/mcp`.

---

## Step 3: Deploy the MCP ActorTemplate and one warm worker

```bash
cat <<EOF | ./hack/run-tool.sh ko apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: mcp-substrate
---
apiVersion: ate.dev/v1alpha1
kind: WorkerPool
metadata:
  name: mcp-tools
  namespace: mcp-substrate
  labels:
    workload: mcp-tools
spec:
  replicas: 1
  ateomImage: ko://github.com/agent-substrate/substrate/cmd/ateom-gvisor
  template:
    nodeSelector:
      cloud.google.com/gke-nodepool: ${SUBSTRATE_NODE_POOL}
    tolerations:
    - key: sandbox.gke.io/runtime
      operator: Equal
      value: gvisor
      effect: NoSchedule
---
apiVersion: ate.dev/v1alpha1
kind: ActorTemplate
metadata:
  name: everything-mcp
  namespace: mcp-substrate
spec:
  pauseImage: "registry.k8s.io/pause:3.10.2@sha256:f548e0e8e3dc1896ca956272154dde3314e8cc4fde0a57577ee9fa1c63f5baf4"
  containers:
  - name: mcp
    image: ${MCP_IMAGE}
    command:
    - node
    - /app/dist/index.js
    - streamableHttp
    env:
    - name: PORT
      value: "80"
  workerSelector:
    matchLabels:
      workload: mcp-tools
  snapshotsConfig:
    onPause: Full
    onCommit: Full
    location: gs://${BUCKET_NAME}/mcp-substrate/everything/
EOF
```

The upstream server does not expose a dedicated HTTP readiness endpoint, so
this template intentionally omits `readyz`. Substrate applies its golden-actor
warmup before taking the initial full snapshot; subsequent resumes restore the
already-listening socket with the process.

Ensure everything is up and operational

```bash
kubectl get workerpool,actortemplate,pods -n mcp-substrate
```

---

## Step 4: Create the MCP actor

Create an atespace and one actor named `everything`:

```bash
kubectl ate create atespace tools
```

```bash
kubectl ate create actor everything \
  --template mcp-substrate/everything-mcp \
  --atespace tools
```

```bash
kubectl ate get actor everything --atespace tools
```

The actor should show:

```text
STATUS_SUSPENDED   ATEOM POD: <none>
```

Its address exists even while its process does not:

```text
everything.tools.actors.resources.substrate.ate.dev
```

Substrate installs a kube-dns stub domain for
`actors.resources.substrate.ate.dev`.

Verify that an ordinary pod can resolve the actor name to the atenet router:

```bash
kubectl run actor-dns-check --rm -i --restart=Never \
  --image=busybox:1.36 -- \
  nslookup everything.tools.actors.resources.substrate.ate.dev
```

The returned address is the router Service, not a worker IP. The worker is
chosen only when a request arrives.

You'll see in the next section that `everything.tools.actors.resources.substrate.ate.dev` (the DNS name) is used in the `AgentgatewayBackend` so traffic can be routed to the MCP Server running in the Substrate Actor

---

## Step 5: Put agentgateway in front of the actor

Create a Gateway, an MCP-aware backend, a route, and an explicit hostname
rewrite policy.

The backend's target is the **actor DNS name**, not the `atenet-router`
Service name. This gives agentgateway two things at once:

- Kubernetes DNS resolves the target to the router.
- The HTTP authority remains
  `everything.tools.actors.resources.substrate.ate.dev`, which tells atenet
  which actor to resume.

```bash
kubectl apply -f - <<'EOF'
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: mcp-substrate-gateway
  namespace: mcp-substrate
spec:
  gatewayClassName: agentgateway
  listeners:
  - name: http
    protocol: HTTP
    port: 8080
    allowedRoutes:
      namespaces:
        from: Same
---
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: substrate-mcp
  namespace: mcp-substrate
spec:
  mcp:
    sessionRouting: Stateful
    targets:
    - name: everything
      static:
        host: everything.tools.actors.resources.substrate.ate.dev
        port: 80
        protocol: StreamableHTTP
        path: /mcp
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: substrate-mcp
  namespace: mcp-substrate
spec:
  parentRefs:
  - name: mcp-substrate-gateway
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /mcp
    backendRefs:
    - group: agentgateway.dev
      kind: AgentgatewayBackend
      name: substrate-mcp
---
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayPolicy
metadata:
  name: substrate-actor-host
  namespace: mcp-substrate
spec:
  targetRefs:
  - group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: substrate-mcp
  traffic:
    hostRewrite:
      mode: Auto
EOF
```

`AgentgatewayBackend` targets already default to automatic host rewriting.
The explicit policy makes the integration contract visible and protects the
demo from an accidental route-level override: atenet rejects requests whose
Host does not match `<actor>.<atespace>.actors.resources.substrate.ate.dev`.

Ensure the resources were created.

```bash
kubectl get all -n mcp-substrate
```

---

## Step 6: First MCP request wakes the suspended Actor

Port-forward agentgateway. Do not port-forward atenet; every MCP request in
this lab must pass through both layers.

```bash
kubectl -n mcp-substrate port-forward \
  svc/mcp-substrate-gateway 8080:8080 >/tmp/pf-agw-substrate.log 2>&1 &

export PF_PID=$!
export MCP_URL=http://localhost:8080/mcp
MCP_HEADERS=(-H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream')
```

Confirm the actor is still suspended immediately before the call:

```bash
kubectl ate get actor everything --atespace tools
```

Now initialize an MCP session. Preserve both headers and body so an HTTP
error is not hidden by the SSE parser. A successful response contains the
agentgateway client session ID; keep it for every later request.

```bash
HTTP_STATUS=$(curl -sS -D /tmp/mcp-substrate-headers.txt \
  -o /tmp/mcp-substrate-body.txt \
  -w '%{http_code}' \
  "${MCP_HEADERS[@]}" "$MCP_URL" -d '{
    "jsonrpc":"2.0",
    "id":1,
    "method":"initialize",
    "params":{
      "protocolVersion":"2025-03-26",
      "capabilities":{},
      "clientInfo":{"name":"agw-substrate-demo","version":"1.0"}
    }
  }')

printf 'HTTP %s\n' "$HTTP_STATUS"
sed -n 's/^data: //p' /tmp/mcp-substrate-body.txt > /tmp/mcp-substrate-json.txt

if [ -s /tmp/mcp-substrate-json.txt ]; then
  jq . /tmp/mcp-substrate-json.txt
else
  cat /tmp/mcp-substrate-body.txt
fi

if [ "$HTTP_STATUS" = "200" ]; then
  export MCP_SID=$(sed -n \
    's/^[Mm][Cc][Pp]-[Ss]ession-[Ii][Dd]:[[:space:]]*//p' \
    /tmp/mcp-substrate-headers.txt | tr -d '\r')

  : "${MCP_SID:?initialize succeeded but returned no MCP session ID}"
  printf 'MCP session: %s\n' "$MCP_SID"
else
  printf 'Initialization failed; inspect the response above before continuing.\n' >&2
fi
```

Do not continue to `notifications/initialized` or `tools/list` unless the
status is `HTTP 200` and `$MCP_SID` is non-empty. For example, an Envoy
`HTTP 503` is a routing/backend failure, not an MCP response.

The first call is slower than a warm request because this happened inside
the request path:

1. agentgateway opened its MCP target at the actor DNS name.
2. Kubernetes DNS returned the atenet router.
3. atenet parsed `everything.tools` from the Host header.
4. atenet called `ResumeActor`.
5. atelet restored the MCP process from object storage into the warm worker.
6. Envoy rewrote the upstream target to the worker IP on port 80.
7. The restored MCP server handled `initialize`.

Verify the actor is now running and bound to the one worker:

```bash
kubectl ate get actor everything --atespace tools
kubectl ate get workers
```

Complete the MCP handshake and list the tools:

```bash
curl -sS "${MCP_HEADERS[@]}" -H "Mcp-Session-Id: $MCP_SID" \
  "$MCP_URL" -d '{
    "jsonrpc":"2.0",
    "method":"notifications/initialized"
  }' >/dev/null

curl -sS "${MCP_HEADERS[@]}" -H "Mcp-Session-Id: $MCP_SID" \
  "$MCP_URL" -d '{
    "jsonrpc":"2.0",
    "id":2,
    "method":"tools/list"
  }' | sed -n 's/^data: //p' | jq -r '.result.tools[].name'
```

You should see tools such as `echo`, `add`, and `printEnv`.

---

## Step 7: Warm tool call

Call the `echo` tool while the actor is already running:

```bash
time curl -sS "${MCP_HEADERS[@]}" -H "Mcp-Session-Id: $MCP_SID" \
  "$MCP_URL" -d '{
    "jsonrpc":"2.0",
    "id":3,
    "method":"tools/call",
    "params":{
      "name":"echo",
      "arguments":{"message":"warm call through agentgateway"}
    }
  }' | sed -n 's/^data: //p' | jq .
```

This is the baseline: agentgateway's MCP handling plus two HTTP proxies,
with no actor restore in the path.

---

# Part 2: Scale

## Step 1: Scale the MCP server to zero

Suspend the actor while keeping agentgateway and the client session alive:

```bash
kubectl ate suspend actor everything --atespace tools
kubectl ate get actor everything --atespace tools
kubectl ate get workers
```

The actor now shows `STATUS_SUSPENDED` and no `ATEOM POD`; the worker shows
no assigned actor. The `mcp/everything` process is gone from compute. Its
RAM, filesystem, open listener, and server-side MCP session state are in the
snapshot bucket.

agentgateway still exposes `http://localhost:8080/mcp`, and the client still
holds `$MCP_SID`.

---

## Step 2: First tool call wakes it, same MCP session

Do **not** initialize a new session. Reuse the same session ID and call the
same tool again:

```bash
time curl -sS "${MCP_HEADERS[@]}" -H "Mcp-Session-Id: $MCP_SID" \
  "$MCP_URL" -d '{
    "jsonrpc":"2.0",
    "id":4,
    "method":"tools/call",
    "params":{
      "name":"echo",
      "arguments":{"message":"this call woke a suspended MCP actor"}
    }
  }' | sed -n 's/^data: //p' | jq .
```

The tool call succeeds. That single result proves two separate things:

- **Routing wake-up:** agentgateway sent the request to the actor DNS name;
  atenet restored the suspended actor before forwarding it.
- **MCP state survival:** the old `$MCP_SID` remained valid. The MCP server's
  in-memory session manager was checkpointed and restored with the process.

Confirm the actor is running again:

```bash
kubectl ate get actor everything --atespace tools
```

Compare the `time` output from Part 1's warm tool call and this restored tool
call. The difference is the visible cost of restoring the tool server.
Subsequent calls return to warm latency.

This is stronger than restarting a Deployment: a restarted stateless pod
could serve a new MCP handshake, but it would not preserve an in-memory MCP
session through process termination. Substrate thawed the same server state.

---

## Cleanup

Stop the port-forward, then suspend and delete the actor before deleting its
atespace:

```bash
kill "$PF_PID" 2>/dev/null

kubectl ate suspend actor everything --atespace tools 2>/dev/null
kubectl ate delete actor everything --atespace tools
kubectl ate delete atespace tools
```

Delete agentgateway and Substrate demo resources. The main Substrate and
agentgateway control planes remain installed:

```bash
kubectl delete namespace mcp-substrate
```

Snapshot objects under
`gs://${BUCKET_NAME}/mcp-substrate/everything/` may remain. Remove that
prefix manually if the actor/template cleanup in your current Substrate
version does not garbage-collect it.
