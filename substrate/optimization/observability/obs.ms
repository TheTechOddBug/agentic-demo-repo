---
title: "Agent Substrate Observability: Wake Latency, Lifecycle Rate, and Worker Utilization"
date: 2026-07-12
description: >
  Install Prometheus and Grafana for Agent Substrate, generate repeated actor
  wake and suspend traffic, visualize routing and restore latency, and watch
  worker-pool utilization while actors rotate through pooled compute.
tags: [agent-substrate, kubernetes, observability, prometheus, grafana, opentelemetry, benchmarking]
author: Michael Levan
---

# Watch Actors Wake, Work, and Yield Their Workers

Tldr; The cost benchmark proved wake latency with TSV files and `awk`. This
lab turns the same lifecycle into a live operating view:

- routing p95,
- `ResumeActor` p95,
- resume and suspend operations per second,
- routing outcomes and error rate,
- snapshot size,
- workers assigned versus free.

The dashboard is useful for a live demo because the lifecycle is visible as
it happens: a batch of suspended actors wakes, worker utilization rises,
requests become warm, snapshots are written, and utilization drops again.

## What upstream actually ships

Substrate currently has two separate observability paths:

| Path | What exists upstream | Where |
|---|---|---|
| GKE / production | Three **Google Cloud Monitoring** dashboards for gRPC, routing/E2E latency, and snapshot size | `tools/setup-gcp/dashboards/` |
| Kind / local | Prometheus plus an OpenTelemetry Collector and Jaeger | `manifests/ate-install/kind/` |
| Benchmarking | A Prometheus/Grafana stack whose bundled dashboards focus on Locust metrics | `benchmarking/monitoring.yaml` |

There are not currently upstream Grafana dashboards for the Substrate system
metrics themselves. This lab reuses upstream's Prometheus deployment and
provisions a small Grafana dashboard from the exact metric instruments in
`docs/observability.md`.

> **Current telemetry gap:** Substrate does not yet emit a worker-count or
> worker-utilization gauge. The source contains a TODO for this in
> `cmd/ateapi/internal/workercache/workercache.go`. This lab does not invent
> a metric. Grafana covers the telemetry that exists; a second terminal
> computes assigned/free utilization from `kubectl ate get workers -o json`.

---

## The metric model

Substrate emits metrics through OpenTelemetry and exposes the same
instruments on each component's Prometheus `/metrics` endpoint.

| OpenTelemetry instrument | Prometheus name used here | Meaning |
|---|---|---|
| `atenet.router.route.duration` | `atenet_router_route_duration_seconds_*` | Time from atenet receiving request headers until it resolves a worker, including resume when needed but excluding actor compute and response. |
| `rpc.server.call.duration` | `rpc_server_call_duration_seconds_*` | gRPC duration/count by `rpc_method` and `rpc_response_status_code`; used for ResumeActor, SuspendActor, atelet Restore, and Checkpoint. |
| `atelet.snapshot.size` | `atelet_snapshot_size_bytes_*` | Uncompressed snapshot image size by kind and ActorTemplate. |

Dots become underscores in the Prometheus exporter, and the exporter adds
unit suffixes (`_seconds`, `_bytes`). The optional Cloud Monitoring path
keeps the dotted instrument names in PromQL.

---

## Prerequisites

- A working GKE Standard Substrate installation from the main
  [setup lab](../../setup.md).
- The counter demo deployed:

  ```bash
  source .ate-dev-env.sh
  ./hack/install-ate.sh --deploy-demo-counter
  ```

- `kubectl-ate` installed and on `PATH`:

  ```bash
  go install ./cmd/kubectl-ate
  export PATH="$(go env GOPATH)/bin:$PATH"
  ```

- Local tools: `kubectl`, `curl`, `jq`.
- Run commands from the root of the Substrate source checkout.

Confirm the system and counter template are ready:

```bash
kubectl get pods -n ate-system
kubectl wait --for=condition=Ready actortemplate/counter \
  -n ate-demo-counter --timeout=5m
kubectl get workerpool counter -n ate-demo-counter
```

---

## Step 1 - Install upstream Prometheus

Every core component carries Prometheus scrape annotations on port `9090`.
The Kind Prometheus manifest is not Kind-specific in how it scrapes: it uses
Kubernetes pod discovery for `ate-system` and can run on GKE unchanged.

```bash
kubectl create namespace otel-system \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f manifests/ate-install/kind/prometheus.yaml

kubectl rollout status deployment/prometheus \
  -n otel-system --timeout=2m
```

Port-forward Prometheus:

```bash
kubectl -n otel-system port-forward svc/prometheus 9090:9090 \
  >/tmp/pf-substrate-prometheus.log 2>&1 &
export PROMETHEUS_PF_PID=$!
```

Verify scrape targets and metric names:

```bash
curl -s http://localhost:9090/api/v1/targets \
  | jq -r '.data.activeTargets[] | [.labels.pod, .health] | @tsv'

curl -s http://localhost:9090/api/v1/label/__name__/values \
  | jq -r '.data[] | select(test("atenet_router|rpc_server|atelet_snapshot"))'
```

Before load, some histogram series may be absent because OpenTelemetry only
exports an instrument after it has recorded a value. `up` should still show
the core targets healthy.

Open `http://localhost:9090` and run:

```promql
up{namespace="ate-system"}
```

You should see healthy `ateapi`, `atelet`, and `atenet-router` targets.

---

## Step 2 - Install Grafana and the Substrate dashboard

The following dashboard is purpose-built for the current upstream metric
surface. It is provisioned from a ConfigMap, so there is no clicking through
the Grafana UI to create panels.

```bash
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-datasources
  namespace: otel-system
data:
  prometheus.yaml: |-
    apiVersion: 1
    datasources:
    - name: Prometheus
      uid: prometheus
      type: prometheus
      url: http://prometheus.otel-system.svc:9090
      access: proxy
      isDefault: true
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-dashboards-provider
  namespace: otel-system
data:
  provider.yaml: |-
    apiVersion: 1
    providers:
    - name: substrate
      orgId: 1
      folder: Agent Substrate
      type: file
      disableDeletion: false
      updateIntervalSeconds: 10
      editable: true
      options:
        path: /var/lib/grafana/dashboards
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-substrate-dashboard
  namespace: otel-system
data:
  substrate.json: |-
    {
      "uid": "agent-substrate-live",
      "title": "Agent Substrate - Live Lifecycle",
      "refresh": "5s",
      "time": {"from": "now-15m", "to": "now"},
      "schemaVersion": 38,
      "version": 1,
      "panels": [
        {
          "id": 1,
          "title": "Routing p95 (wake path included)",
          "type": "timeseries",
          "gridPos": {"h": 8, "w": 8, "x": 0, "y": 0},
          "targets": [{
            "expr": "histogram_quantile(0.95, sum(rate(atenet_router_route_duration_seconds_bucket[2m])) by (le))",
            "legendFormat": "route p95",
            "refId": "A"
          }],
          "fieldConfig": {"defaults": {"unit": "s", "min": 0}}
        },
        {
          "id": 2,
          "title": "ResumeActor p95",
          "type": "timeseries",
          "gridPos": {"h": 8, "w": 8, "x": 8, "y": 0},
          "targets": [{
            "expr": "histogram_quantile(0.95, sum(rate(rpc_server_call_duration_seconds_bucket{app=\"ate-api-server\",rpc_method=\"ateapi.Control/ResumeActor\"}[2m])) by (le))",
            "legendFormat": "resume p95",
            "refId": "A"
          }],
          "fieldConfig": {"defaults": {"unit": "s", "min": 0}}
        },
        {
          "id": 3,
          "title": "Restore p95 (atelet)",
          "type": "timeseries",
          "gridPos": {"h": 8, "w": 8, "x": 16, "y": 0},
          "targets": [{
            "expr": "histogram_quantile(0.95, sum(rate(rpc_server_call_duration_seconds_bucket{app=\"atelet\",rpc_method=\"atelet.AteomHerder/Restore\"}[2m])) by (le))",
            "legendFormat": "restore p95",
            "refId": "A"
          }],
          "fieldConfig": {"defaults": {"unit": "s", "min": 0}}
        },
        {
          "id": 4,
          "title": "Actor lifecycle operations / second",
          "type": "timeseries",
          "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
          "targets": [{
            "expr": "sum by (rpc_method) (rate(rpc_server_call_duration_seconds_count{app=\"ate-api-server\",rpc_method=~\"ateapi.Control/(ResumeActor|SuspendActor)\"}[2m]))",
            "legendFormat": "{{rpc_method}}",
            "refId": "A"
          }],
          "fieldConfig": {"defaults": {"unit": "ops", "min": 0}}
        },
        {
          "id": 5,
          "title": "Routing QPS by outcome",
          "type": "timeseries",
          "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
          "targets": [{
            "expr": "sum by (outcome) (rate(atenet_router_route_duration_seconds_count[2m]))",
            "legendFormat": "{{outcome}}",
            "refId": "A"
          }],
          "fieldConfig": {"defaults": {"unit": "reqps", "min": 0}}
        },
        {
          "id": 6,
          "title": "Resume/Suspend outcomes",
          "type": "timeseries",
          "gridPos": {"h": 8, "w": 12, "x": 0, "y": 16},
          "targets": [{
            "expr": "sum by (rpc_method, rpc_response_status_code) (rate(rpc_server_call_duration_seconds_count{app=\"ate-api-server\",rpc_method=~\"ateapi.Control/(ResumeActor|SuspendActor)\"}[2m]))",
            "legendFormat": "{{rpc_method}} {{rpc_response_status_code}}",
            "refId": "A"
          }],
          "fieldConfig": {"defaults": {"unit": "ops", "min": 0}}
        },
        {
          "id": 7,
          "title": "Snapshot size p95 by image kind",
          "type": "timeseries",
          "gridPos": {"h": 8, "w": 12, "x": 12, "y": 16},
          "targets": [{
            "expr": "histogram_quantile(0.95, sum by (le, kind) (rate(atelet_snapshot_size_bytes_bucket[5m])))",
            "legendFormat": "{{kind}}",
            "refId": "A"
          }],
          "fieldConfig": {"defaults": {"unit": "bytes", "min": 0}}
        },
        {
          "id": 8,
          "title": "Routing p95 by ActorTemplate",
          "type": "timeseries",
          "gridPos": {"h": 8, "w": 24, "x": 0, "y": 24},
          "targets": [{
            "expr": "histogram_quantile(0.95, sum by (le, actor_template_namespace, actor_template_name) (rate(atenet_router_route_duration_seconds_bucket{outcome=\"ok\"}[2m])))",
            "legendFormat": "{{actor_template_namespace}}/{{actor_template_name}}",
            "refId": "A"
          }],
          "fieldConfig": {"defaults": {"unit": "s", "min": 0}}
        }
      ]
    }
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: grafana
  namespace: otel-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: grafana
  template:
    metadata:
      labels:
        app: grafana
    spec:
      containers:
      - name: grafana
        image: grafana/grafana:10.0.0
        env:
        - name: GF_AUTH_ANONYMOUS_ENABLED
          value: "true"
        - name: GF_AUTH_ANONYMOUS_ORG_ROLE
          value: Viewer
        - name: GF_AUTH_DISABLE_LOGIN_FORM
          value: "true"
        ports:
        - name: http
          containerPort: 3000
        readinessProbe:
          httpGet:
            path: /api/health
            port: http
        volumeMounts:
        - name: datasources
          mountPath: /etc/grafana/provisioning/datasources
        - name: providers
          mountPath: /etc/grafana/provisioning/dashboards
        - name: dashboards
          mountPath: /var/lib/grafana/dashboards
      volumes:
      - name: datasources
        configMap:
          name: grafana-datasources
      - name: providers
        configMap:
          name: grafana-dashboards-provider
      - name: dashboards
        configMap:
          name: grafana-substrate-dashboard
---
apiVersion: v1
kind: Service
metadata:
  name: grafana
  namespace: otel-system
spec:
  selector:
    app: grafana
  ports:
  - name: http
    port: 3000
    targetPort: http
EOF

kubectl rollout status deployment/grafana -n otel-system --timeout=2m
```

Port-forward Grafana:

```bash
kubectl -n otel-system port-forward svc/grafana 3000:3000 \
  >/tmp/pf-substrate-grafana.log 2>&1 &
export GRAFANA_PF_PID=$!
```

Open `http://localhost:3000/d/agent-substrate-live`. The panels may say
`No data` until Step 6 generates lifecycle events.

> Anonymous access is enabled for a local port-forwarded demo. Do not expose
> this Grafana Service publicly with that configuration.

---

## Step 3 - Create benchmark actors

Use a dedicated atespace so actor names and cleanup cannot collide with
other labs:

```bash
export OBS_ATESPACE=observability
export OBS_ACTOR_COUNT=20
export OBS_PREFIX=obs-counter

kubectl ate create atespace "$OBS_ATESPACE"

for i in $(seq 1 "$OBS_ACTOR_COUNT"); do
  actor=$(printf "%s-%03d" "$OBS_PREFIX" "$i")
  kubectl ate create actor "$actor" \
    --template ate-demo-counter/counter \
    --atespace "$OBS_ATESPACE"
done

kubectl ate get actors --atespace "$OBS_ATESPACE"
```

All 20 actors start suspended and consume no worker slots.

---

## Step 4 - Create the in-cluster load client

The load client sends traffic inside the cluster, avoiding port-forward and
local-network latency. It addresses atenet directly and supplies the actor's
uniform DNS name as Host.

```bash
kubectl create namespace substrate-observability-load \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl run benchmark-client \
  -n substrate-observability-load \
  --image=curlimages/curl:8.10.1 \
  --restart=Never \
  --command -- sleep 7200

kubectl wait --for=condition=Ready pod/benchmark-client \
  -n substrate-observability-load --timeout=2m
```

Capture the current WorkerPool size. The load generator uses that as its
batch size so it fills the pool without intentionally producing
`no free workers` failures:

```bash
export OBS_BATCH_SIZE=$(kubectl get workerpool counter \
  -n ate-demo-counter -o jsonpath='{.spec.replicas}')

printf "actors=%s workers=%s\n" "$OBS_ACTOR_COUNT" "$OBS_BATCH_SIZE"
```

---

## Step 5 - Open the live worker-utilization terminal

This is the view Grafana cannot provide yet because no worker gauge is
emitted. It reads the canonical worker state from ateapi every two seconds:

```bash
while true; do
  workers=$(kubectl ate get workers -o json)
  pool_workers=$(printf '%s' "$workers" | jq \
    '[.workers[] | select(.workerNamespace == "ate-demo-counter" and .workerPool == "counter")]')
  total=$(printf '%s' "$pool_workers" | jq 'length')
  assigned=$(printf '%s' "$pool_workers" \
    | jq '[.[] | select(.assignment != null)] | length')
  free=$((total - assigned))

  if [ "$total" -gt 0 ]; then
    pct=$((assigned * 100 / total))
  else
    pct=0
  fi

  clear
  date
  printf "counter pool: total=%d assigned=%d free=%d utilization=%d%%\n\n" \
    "$total" "$assigned" "$free" "$pct"
  kubectl ate get workers
  sleep 2
done
```

Leave it running while Step 6 runs in another terminal. Press `Ctrl-C` when
the load test is finished.

---

## Step 6 - Drive wake, warm, and suspend cycles

The loop processes actors in batches equal to the WorkerPool size:

1. First request resumes every actor in the batch concurrently.
2. Second request is warm.
3. The batch remains assigned for five seconds so utilization is visible.
4. Every actor is suspended, writing snapshots and releasing the workers.
5. The next batch repeats the lifecycle.

Three cycles create enough events for the two-minute dashboard rates and
quantiles to stabilize.

```bash
export OBS_CYCLES=3
export OBS_ROUTER_URL=http://atenet-router.ate-system.svc:80

for cycle in $(seq 1 "$OBS_CYCLES"); do
  printf "cycle %s/%s\n" "$cycle" "$OBS_CYCLES"

  offset=1
  while [ "$offset" -le "$OBS_ACTOR_COUNT" ]; do
    batch_end=$((offset + OBS_BATCH_SIZE - 1))
    if [ "$batch_end" -gt "$OBS_ACTOR_COUNT" ]; then
      batch_end=$OBS_ACTOR_COUNT
    fi

    printf "  waking actors %03d-%03d\n" "$offset" "$batch_end"

    for i in $(seq "$offset" "$batch_end"); do
      actor=$(printf "%s-%03d" "$OBS_PREFIX" "$i")
      host="${actor}.${OBS_ATESPACE}.actors.resources.substrate.ate.dev"
      kubectl exec -n substrate-observability-load benchmark-client -- \
        curl -sS -o /dev/null -X POST -H "Host: ${host}" \
        "$OBS_ROUTER_URL" &
    done
    wait

    printf "  warm requests\n"
    for i in $(seq "$offset" "$batch_end"); do
      actor=$(printf "%s-%03d" "$OBS_PREFIX" "$i")
      host="${actor}.${OBS_ATESPACE}.actors.resources.substrate.ate.dev"
      kubectl exec -n substrate-observability-load benchmark-client -- \
        curl -sS -o /dev/null -X POST -H "Host: ${host}" \
        "$OBS_ROUTER_URL" &
    done
    wait

    sleep 5

    printf "  suspending batch\n"
    for i in $(seq "$offset" "$batch_end"); do
      actor=$(printf "%s-%03d" "$OBS_PREFIX" "$i")
      kubectl ate suspend actor "$actor" \
        --atespace "$OBS_ATESPACE" >/dev/null
    done

    offset=$((batch_end + 1))
  done
done
```

What to watch:

- **Worker terminal:** assigned rises toward the counter pool's replica count,
  stays there during the five-second hold, then returns to zero.
- **Routing p95:** wake batches are visibly slower than the warm batch because
  route duration includes actor resolution/resume.
- **ResumeActor p95 and Restore p95:** separate control-plane coordination
  from atelet snapshot restoration.
- **Lifecycle operations/sec:** ResumeActor rises during wake batches;
  SuspendActor rises after the hold.
- **Snapshot size:** the counter template uses `onCommit: Data`, so suspend
  snapshots emphasize the durable-volume image rather than full process RAM.

---

## Step 7 - Query the same signals directly

Grafana is presentation; PromQL is the source of truth. These API queries
return the current value of each expression.

Routing p95:

```bash
curl -sG http://localhost:9090/api/v1/query \
  --data-urlencode 'query=histogram_quantile(0.95, sum(rate(atenet_router_route_duration_seconds_bucket[2m])) by (le))' \
  | jq '.data.result'
```

Resume p95:

```bash
curl -sG http://localhost:9090/api/v1/query \
  --data-urlencode 'query=histogram_quantile(0.95, sum(rate(rpc_server_call_duration_seconds_bucket{app="ate-api-server",rpc_method="ateapi.Control/ResumeActor"}[2m])) by (le))' \
  | jq '.data.result'
```

Resume and suspend rate:

```bash
curl -sG http://localhost:9090/api/v1/query \
  --data-urlencode 'query=sum by (rpc_method) (rate(rpc_server_call_duration_seconds_count{app="ate-api-server",rpc_method=~"ateapi.Control/(ResumeActor|SuspendActor)"}[2m]))' \
  | jq '.data.result'
```

These values should agree with the Grafana panels for the same time window.

---

## Step 8 - Optional upstream Google Cloud dashboards

For the GKE-native view, upstream ships three Cloud Monitoring dashboards:

| Dashboard | Main use |
|---|---|
| `Substrate gRPC` | ateapi and atelet p50/p95/p99, method QPS, errors |
| `Substrate Routing & E2E Latency` | route p50/p95/p99, ResumeActor and Restore stages, routing outcomes, Envoy round-trip context |
| `Substrate Snapshot Size & QPS` | snapshot sizes and checkpoint throughput |

Create or update all three idempotently:

```bash
go run ./tools/setup-gcp create dashboards --project-id="$PROJECT_ID"
```

Then open Google Cloud Console -> **Monitoring -> Dashboards**.

The cluster must have GKE Managed OpenTelemetry enabled because the core
manifests export OTLP to:

```text
opentelemetry-collector.gke-managed-otel.svc.cluster.local:4317
```

Check for that collector before expecting Cloud dashboard data:

```bash
kubectl get svc opentelemetry-collector -n gke-managed-otel
```

For the Envoy full-round-trip panels, install the upstream PodMonitoring:

```bash
kubectl apply -f manifests/ate-install/atenet-router-monitoring.yaml
kubectl get podmonitoring -n ate-system
```

> Do not run `go run ./tools/setup-gcp create cluster` casually against an
> existing cluster just to enable telemetry. The helper reconciles network,
> subnetwork, and Dataplane V2 settings and can recreate a cluster when they
> differ. Configure Managed OpenTelemetry through your established GKE
> change process instead.

---

## Cleanup

Suspend and delete the benchmark actors, then remove the atespace:

```bash
for i in $(seq 1 "$OBS_ACTOR_COUNT"); do
  actor=$(printf "%s-%03d" "$OBS_PREFIX" "$i")
  kubectl ate suspend actor "$actor" \
    --atespace "$OBS_ATESPACE" 2>/dev/null
  kubectl ate delete actor "$actor" --atespace "$OBS_ATESPACE"
done

kubectl ate delete atespace "$OBS_ATESPACE"
kubectl delete namespace substrate-observability-load
```

Stop local port-forwards:

```bash
kill "$PROMETHEUS_PF_PID" "$GRAFANA_PF_PID" 2>/dev/null
```

Remove the lab Grafana resources while keeping Prometheus:

```bash
kubectl delete deployment/grafana service/grafana \
  configmap/grafana-datasources \
  configmap/grafana-dashboards-provider \
  configmap/grafana-substrate-dashboard \
  -n otel-system
```

To remove the local Prometheus resources too (without deleting the shared
`otel-system` namespace):

```bash
kubectl delete deployment/prometheus service/prometheus \
  serviceaccount/prometheus configmap/prometheus-config -n otel-system
kubectl delete rolebinding/ate-prometheus -n ate-system
kubectl delete rolebinding/ate-prometheus -n otel-system
kubectl delete clusterrole/ate-prometheus
```

Do not delete the Cloud Monitoring dashboards if other operators use them;
they are project-wide resources, not lab-local Kubernetes objects.

---

## Troubleshooting

- **All panels say `No data`:** first check Prometheus targets, then query the
  metric-name label API from Step 1. Histogram series do not exist until at
  least one matching operation occurs.
- **Prometheus target is down:** inspect the discovered URL under Prometheus
  **Status -> Targets**. Substrate pods advertise port `9090`; NetworkPolicy
  or dataplane policy must permit the Prometheus pod to reach it.
- **`atenet_router_route_duration_seconds_*` is missing:** make sure requests
  went through `atenet-router`, not directly to ateapi. Check
  `kubectl logs -n ate-system deployment/atenet-router -c atenet-router`.
- **Metric names do not include `_seconds` or `_bytes`:** exporter naming can
  change across OpenTelemetry versions. Use the discovery command in Step 1
  and update the dashboard expressions to the names exposed by your build.
- **Resume p95 exists but route p95 does not:** ateapi was exercised through
  the CLI, while atenet was not. Run Step 6's HTTP load.
- **Worker utilization never reaches 100%:** the summary is filtered to the
  `ate-demo-counter/counter` pool, but the table beneath it shows the whole
  fleet. Check whether another actor already owns a counter worker, or reduce
  `OBS_BATCH_SIZE` to the number of slots actually free.
- **Wake calls report `no free workers`:** reduce `OBS_BATCH_SIZE` or wait for
  the previous batch's suspends to finish. Do not create a batch larger than
  the eligible counter WorkerPool.
- **Cloud dashboards are empty while Grafana works:** local Prometheus scrapes
  component endpoints directly. Cloud dashboards depend separately on GKE
  Managed OpenTelemetry and Google Managed Prometheus ingestion.
- **Snapshot panel is sparse:** it uses a five-minute rate and only changes
  when actors checkpoint. Run multiple Step 6 cycles and keep the Grafana
  time range at 15 minutes.

---

## Recap

| View | What it proved |
|---|---|
| Routing p95 | The user-visible routing stage changes when a request must wake an actor. |
| ResumeActor p95 | Control-plane scheduling and actor lifecycle coordination have their own measurable latency. |
| atelet Restore p95 | Snapshot restoration can be separated from the broader resume workflow. |
| Resume/Suspend rate | Actor churn is visible as an operational rate, not hidden behind request latency. |
| Snapshot size | The selected snapshot tier has a measurable storage and transfer footprint. |
| Live worker utilization | Many actors rotate through fewer workers; assigned capacity rises only while actors are active. |

The talk line: **"The actors look long-lived. The workers tell the truth:
they are being borrowed, released, and borrowed again."**
