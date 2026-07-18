# KServe Implementation

## Key Platforms and Tools For Serving LLMs In k8s

Quick breakdown:

1. KServe
2. vLLM
3. llm-d

KServe is the model deployment and scaling layer that runs on Kubernetes. It uses inference engines like vLLM to run the LLM, and takes care of things like traffic routing, scaling, canary deployments, etc. It's the Control Plane.

vLLM is the inference engine. Without an inference engine like vLLM, you wouldn't be able to run/host Models in Kubernetes.

llm-d is the scheduling layer. It routes incoming LLM requests to instance (Pods) of vLLM (the inference engine that loads your LLMs).

KServe integrates llm-d into its architecture to handle LLM deployments/scheduling. They work at different layers of the stack. KServe is the Control Plane and llm-d is the LLM scheduler that routes LLM traffic (e.g - asking your Agent to do perform an action) to vLLM.


## Gateway Deployment

```yaml
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: Issuer
metadata:
  name: kserve-selfsigned
  namespace: kserve
spec:
  selfSigned: {}
---
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: kserve-ingress
  namespace: kserve
spec:
  secretName: my-secret
  issuerRef:
    name: kserve-selfsigned
    kind: Issuer
  dnsNames:
    - "*.example.com"
    - "example.com"
EOF
```

```yaml
kubectl apply -f - <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: kserve-ingress-gateway
  namespace: kserve
spec:
  gatewayClassName: agentgateway
  listeners:
    - name: http
      protocol: HTTP
      port: 80
      allowedRoutes:
        namespaces:
          from: All
    - name: https
      protocol: HTTPS
      port: 443
      tls:
        mode: Terminate
        certificateRefs:
          - kind: Secret
            name: my-secret
            namespace: kserve
      allowedRoutes:
        namespaces:
          from: All
  infrastructure:
    labels:
      serving.kserve.io/gateway: kserve-ingress-gateway
EOF
```

## KServe Deployment

```bash
helm install kserve-crd oci://ghcr.io/kserve/charts/kserve-crd -n kserve --create-namespace --version v0.18.0
```

```bash
helm install kserve oci://ghcr.io/kserve/charts/kserve-resources -n kserve --version v0.18.0 \
  --set kserve.controller.deploymentMode=Standard \
  --set kserve.controller.gateway.ingressGateway.enableGatewayApi=true \
  --set kserve.controller.gateway.ingressGateway.kserveGateway=kserve/kserve-ingress-gateway
```

## LLM Deployment

```
kubectl apply -f - <<EOF
apiVersion: serving.kserve.io/v1alpha1
kind: ClusterServingRuntime
metadata:
  name: kserve-huggingfaceserver
  annotations:
    serving.kserve.io/server-type: huggingfaceserver
spec:
  annotations:
    prometheus.kserve.io/path: /metrics
    prometheus.kserve.io/port: "8080"
  containers:
    - name: kserve-container
      image: kserve/huggingfaceserver:latest
      args:
        - --model_name={{.Name}}
      resources:
        limits:
          cpu: "2"
          memory: 4Gi
        requests:
          cpu: "1"
          memory: 2Gi
  supportedModelFormats:
    - name: huggingface
      version: "1"
      autoSelect: true
      priority: 1
  protocolVersions:
    - v2
    - v1
EOF
```

```
kubectl apply -f - <<EOF
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: qwen-llm
  namespace: kserve
spec:
  predictor:
    model:
      modelFormat:
        name: huggingface
      args:
        - --model_name=qwen
        - --gpu-memory-utilization=0.5
        - --max-model-len=4096
      storageUri: "hf://Qwen/Qwen2.5-0.5B-Instruct"
      resources:
        limits:
          cpu: "2"
          memory: 6Gi
        requests:
          cpu: "1"
          memory: 4Gi
EOF
```