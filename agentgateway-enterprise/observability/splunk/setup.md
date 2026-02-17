# Splunk Enterprise Observability for Agentgateway

This guide deploys Splunk Enterprise in the same Kubernetes cluster as agentgateway and configures end-to-end trace ingestion via HEC (HTTP Event Collector) through the OpenTelemetry Collector.

## Prerequisites

- agentgateway deployed and running in the cluster
- `kubectl` access to the cluster

## 1. Deploy Splunk Enterprise

Create a namespace and deploy Splunk Enterprise with HEC auto-enabled.

```
kubectl create namespace splunk
```

```
kubectl apply -f- <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: splunk
  namespace: splunk
spec:
  replicas: 1
  selector:
    matchLabels:
      app: splunk
  template:
    metadata:
      labels:
        app: splunk
    spec:
      containers:
      - name: splunk
        image: splunk/splunk:latest
        env:
        - name: SPLUNK_START_ARGS
          value: "--accept-license"
        - name: SPLUNK_GENERAL_TERMS
          value: "--accept-sgt-current-at-splunk-com"
        - name: SPLUNK_PASSWORD
          value: "changeme123"
        - name: SPLUNK_HEC_TOKEN
          value: "agentgateway-hec-token"
        - name: SPLUNK_HEC_SSL
          value: "false"
        ports:
        - containerPort: 8000
          name: web
        - containerPort: 8088
          name: hec
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
---
apiVersion: v1
kind: Service
metadata:
  name: splunk
  namespace: splunk
spec:
  selector:
    app: splunk
  ports:
  - name: web
    port: 8000
    targetPort: 8000
  - name: hec
    port: 8088
    targetPort: 8088
EOF
```

## 2. Verify Splunk is Running

Wait for the pod to be ready (Splunk takes 2-3 minutes to fully initialize):

```
kubectl get pods -n splunk -w
```

Once it's running, port-forward to access the Splunk Web UI:

```
kubectl port-forward svc/splunk -n splunk 8000:8000
```

Log in at http://localhost:8000:
- Username: `admin`
- Password: `changeme123`

## 3. Verify HEC is Enabled

The `SPLUNK_HEC_TOKEN` environment variable auto-enables HEC on startup. You can verify by running:

```
kubectl exec -n splunk deploy/splunk -- curl -s http://localhost:8088/services/collector/health
```

You should see `{"text":"HEC is healthy","code":17}`.

## 4. Install the OTel Traces Collector

Install the OpenTelemetry Traces Collector with both a `debug` exporter and a `splunk_hec` exporter. The collector receives OTLP traces from agentgateway and forwards them to Splunk via HEC.

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
    splunk_hec:
      endpoint: "http://splunk.splunk.svc.cluster.local:8088/services/collector"
      token: "agentgateway-hec-token"
      source: "agentgateway"
      sourcetype: "otlp"
      index: "main"
      tls:
        insecure: true
    debug:
      verbosity: detailed
  service:
    pipelines:
      traces:
        receivers: [otlp]
        processors: [batch]
        exporters: [debug, splunk_hec]
EOF
```

Ensure that it's running:
```
kubectl get pods -n telemetry
```

## 5. Install the OTel Metrics Collector

Install a separate OTel Collector for metrics. This collector scrapes Prometheus metrics from both the agentgateway data plane and control plane pods, then exports them to Splunk via HEC. Prometheus does not need to be installed. The metrics collector uses the OTel Collector's built-in prometheus receiver, which is just a scraper that knows how to pull Prometheus-format metrics from pod endpoints. It's not the Prometheus server itself.

```
helm upgrade --install opentelemetry-collector-metrics opentelemetry-collector \
--repo https://open-telemetry.github.io/opentelemetry-helm-charts \
--version 0.127.2 \
--set mode=deployment \
--set image.repository="otel/opentelemetry-collector-contrib" \
--set command.name="otelcol-contrib" \
--namespace=telemetry \
--create-namespace \
-f -<<EOF
clusterRole:
  create: true
  rules:
  - apiGroups:
    - ''
    resources:
    - 'pods'
    - 'nodes'
    verbs:
    - 'get'
    - 'list'
    - 'watch'
command:
  extraArgs:
    - "--feature-gates=receiver.prometheusreceiver.EnableNativeHistograms"
config:
  receivers:
    prometheus/agentgateway-dataplane:
      config:
        global:
          scrape_protocols: [ PrometheusProto, OpenMetricsText1.0.0, OpenMetricsText0.0.1, PrometheusText0.0.4 ]
        scrape_configs:
        - job_name: agentgateway-gateways
          honor_labels: true
          kubernetes_sd_configs:
          - role: pod
          relabel_configs:
            - action: keep
              regex: enterprise-agentgateway
              source_labels:
              - __meta_kubernetes_pod_label_gateway_networking_k8s_io_gateway_class_name
            - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
              action: keep
              regex: true
            - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
              action: replace
              target_label: __metrics_path__
              regex: (.+)
            - action: replace
              source_labels:
              - __meta_kubernetes_pod_ip
              - __meta_kubernetes_pod_annotation_prometheus_io_port
              separator: ':'
              target_label: __address__
            - action: labelmap
              regex: __meta_kubernetes_pod_label_(.+)
            - source_labels: [__meta_kubernetes_namespace]
              action: replace
              target_label: kube_namespace
            - source_labels: [__meta_kubernetes_pod_name]
              action: replace
              target_label: pod
    prometheus/agentgateway-controlplane:
      config:
        global:
          scrape_protocols: [ PrometheusProto, OpenMetricsText1.0.0, OpenMetricsText0.0.1, PrometheusText0.0.4 ]
        scrape_configs:
        - job_name: agentgateway-controlplane
          honor_labels: true
          kubernetes_sd_configs:
          - role: pod
          relabel_configs:
            - action: keep
              regex: agentgateway
              source_labels:
              - __meta_kubernetes_pod_label_agentgateway
            - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
              action: keep
              regex: true
            - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
              action: replace
              target_label: __metrics_path__
              regex: (.+)
            - action: replace
              source_labels:
              - __meta_kubernetes_pod_ip
              - __meta_kubernetes_pod_annotation_prometheus_io_port
              separator: ':'
              target_label: __address__
            - action: labelmap
              regex: __meta_kubernetes_pod_label_(.+)
            - source_labels: [__meta_kubernetes_namespace]
              action: replace
              target_label: kube_namespace
            - source_labels: [__meta_kubernetes_pod_name]
              action: replace
              target_label: pod
  exporters:
    splunk_hec:
      endpoint: "http://splunk.splunk.svc.cluster.local:8088/services/collector"
      token: "agentgateway-hec-token"
      source: "agentgateway-metrics"
      sourcetype: "prometheus"
      index: "main"
      tls:
        insecure: true
    debug:
      verbosity: detailed
  service:
    pipelines:
      metrics:
        receivers: [prometheus/agentgateway-dataplane, prometheus/agentgateway-controlplane]
        processors: [batch]
        exporters: [debug, splunk_hec]
EOF
```

Ensure both collectors are running:
```
kubectl get pods -n telemetry -l app.kubernetes.io/name=opentelemetry-collector
```

## 6. Set Up An Agentgateway Proxy

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

## 7. Configure Agentgateway Tracing

Create an `EnterpriseAgentgatewayPolicy` to enable tracing on the agentgateway proxy. This policy targets the Gateway and configures it to send traces to the OTel traces collector.

```
kubectl apply -f- <<EOF
apiVersion: enterpriseagentgateway.solo.io/v1alpha1
kind: EnterpriseAgentgatewayPolicy
metadata:
  name: tracing
  namespace: agentgateway-system
spec:
  targetRefs:
    - kind: Gateway
      name: agentgateway-route
      group: gateway.networking.k8s.io
  frontend:
    tracing:
      backendRef:
        name: opentelemetry-collector-traces
        namespace: telemetry
        port: 4317
      protocol: GRPC
      clientSampling: "true"
      randomSampling: "true"
EOF
```

## 8. Generate Trace Traffic

Send a request through agentgateway to generate traces.

```
export INGRESS_GW_ADDRESS=$(kubectl get svc -n agentgateway-system agentgateway-route -o jsonpath="{.status.loadBalancer.ingress[0]['hostname','ip']}")
echo $INGRESS_GW_ADDRESS
```

```
curl "$INGRESS_GW_ADDRESS:8080/anthropic" -H content-type:application/json -d '{
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant."
    },
    {
      "role": "user",
      "content": "Hello, this is a test for Splunk tracing."
    }
  ]
}' | jq
```

## 9. Verify Traces and Metrics are Flowing

Check the OTel Collector logs for successful exports to Splunk:

```
kubectl logs deploy/opentelemetry-collector-traces -n telemetry
kubectl logs deploy/opentelemetry-collector-metrics -n telemetry
```

You can also check agentgateway proxy logs for trace IDs:

```
kubectl logs deploy/agentgateway-proxy -n agentgateway-system
```

Look for `trace.id=` in the output.

## 10. Query Traces and Metrics in Splunk

Port-forward to the Splunk UI if not already:

```
kubectl port-forward svc/splunk -n splunk 8000:8000
```

Navigate to **Search & Reporting** in the Splunk UI and use these SPL queries:

### Find all agentgateway traces
```
index=main sourcetype=otlp source=agentgateway
```

### Find traces with token usage
```
index=main sourcetype=otlp source=agentgateway
| spath
| where isnotnull('attributes.gen_ai.usage.input_tokens')
| table _time, attributes.gen_ai.request.model, attributes.gen_ai.response.model, attributes.gen_ai.usage.input_tokens, attributes.gen_ai.usage.output_tokens
```

### Find traces by model
```
index=main sourcetype=otlp source=agentgateway
| spath
| stats count by attributes.gen_ai.request.model, attributes.gen_ai.response.model
```

### View trace latency
```
index=main sourcetype=otlp source=agentgateway
| spath
| table _time, trace_id, span_id, attributes.gen_ai.request.model, attributes.duration
| sort -attributes.duration
```

### Find all agentgateway metrics
```
index=main sourcetype=prometheus source=agentgateway-metrics
```

### View request rate by pod
```
index=main sourcetype=prometheus source=agentgateway-metrics
| stats count by pod, kube_namespace
```