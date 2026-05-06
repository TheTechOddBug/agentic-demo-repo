# Kagent OSS + OpenShell (NemoClaw) Integration - Setup Guide

This guide walks through deploying kagent OSS with the OpenShell/OpenClaw sandbox integration from the `eitanya/openshell` branch to a GKE cluster. The integration adds sandbox CRDs, an OpenShell gRPC backend, SSH proxy support, and UI components for managing sandboxed agents.

## Prerequisites

- A running k8s cluster (amd64 nodes)
- `kubectl` configured and pointing at your cluster
- `helm` v3 installed
- `gcloud` CLI authenticated with access to a Google Artifact Registry repository
- Docker Desktop running (for building images)
- Docker Buildx with multi-platform support
- Go 1.26.1+ (for controller manifest generation)
- An LLM provider API key (Anthropic, OpenAI, etc.)

## Architecture Overview

The deployment consists of three components:

1. **OpenShell Gateway** (NVIDIA) -- sandbox runtime environment for autonomous agents. Deployed as a StatefulSet in the `openshell` namespace.
2. **Agent Sandbox Controller** -- Kubernetes controller for the `Sandbox` CRD. Deployed in `agent-sandbox-system` namespace.
3. **Kagent** (with OpenShell integration) -- the kagent controller, UI, agents, and tools. Deployed in the `kagent` namespace. The controller connects to the OpenShell gateway at startup.

The OpenShell gateway **must** be deployed before kagent. The kagent controller will crash (`CrashLoopBackOff`) if it cannot reach `openshell.openshell.svc.cluster.local:8080` on startup.

## 1. Clone the Required Repositories

```bash
# Clone the kagent OSS repo
git clone https://github.com/kagent-dev/kagent.git
cd kagent

# Checkout the openshell integration branch
git checkout upstream/eitanya/openshell
```

```bash
# Clone the OpenShell fork (in a separate directory)
git clone https://github.com/kagent-dev/OpenShell.git
cd OpenShell

# Switch to the correct branch
git checkout feat/k8s-supervisor-sideload-fork
```

## 2. Build and Push Kagent Container Images

The openshell branch includes changes to the controller, UI, and CRDs that are not in any published release. You must build and push images from this branch.

### Configure the Container Registry

These instructions use Google Artifact Registry (GAR). Adjust for your registry.

```bash
# Authenticate Docker with GAR
gcloud auth configure-docker us-docker.pkg.dev --quiet

# Set your registry variables
export DOCKER_REGISTRY=us-docker.pkg.dev/<YOUR_PROJECT>/<YOUR_REPO>
export DOCKER_REPO=kagent-dev/kagent
```

### Grant GKE Nodes Pull Access

GKE nodes need `artifactregistry.reader` on the GAR repository. Identify your node pool service accounts and grant access:

```bash
# Find the GKE node service accounts
gcloud container clusters describe <CLUSTER_NAME> --region <REGION> \
  --format="json(nodePools[].config.serviceAccount)"

# Grant each service account read access to your GAR repo
gcloud artifacts repositories add-iam-policy-binding <REPO_NAME> \
  --location=<LOCATION> \
  --member="serviceAccount:<SA_EMAIL>" \
  --role="roles/artifactregistry.reader" \
  --project=<PROJECT>
```

> **Note**: If your node pool uses the `default` compute service account with `devstorage.read_only` OAuth scope (common for default GKE node pools), the IAM binding alone is insufficient. The nodes lack the OAuth scope for GAR. In this case, create an `imagePullSecret` instead (see [Troubleshooting](#troubleshooting)).

### Build the Images

All builds target `linux/amd64` for GKE. Run from the kagent repo root:

```bash
cd kagent

# Generate controller manifests (required before building)
make controller-manifests

# Build and push all images (controller, UI, app, kagent-adk, skills-init)
DOCKER_REGISTRY=$DOCKER_REGISTRY \
DOCKER_REPO=$DOCKER_REPO \
DOCKER_BUILD_ARGS="--push --platform linux/amd64" \
  make build-controller build-ui build-kagent-adk build-skills-init

# Build the app image (depends on kagent-adk, must run after)
DOCKER_REGISTRY=$DOCKER_REGISTRY \
DOCKER_REPO=$DOCKER_REPO \
DOCKER_BUILD_ARGS="--push --platform linux/amd64" \
  make build-app
```

Note the version tag printed during the build (e.g., `v0.9.1-8-g4398e62e`). You will need it for the Helm install:

```bash
export VERSION=$(git describe --tags --always)
echo "Image tag: $VERSION"
```

### Generate the Helm Charts

The kagent Helm charts use templated `Chart.yaml` files that must be generated before install:

```bash
make helm-version
```

This generates `Chart.yaml` for all sub-charts, downloads dependencies, and packages everything.

## 3. Deploy the OpenShell Gateway

The OpenShell gateway must be running before kagent is installed.

### Install the OpenShell Helm Chart

From the OpenShell repo root:

```bash
cd OpenShell

helm upgrade --install openshell deploy/helm/openshell \
  -n openshell --create-namespace \
  --set server.disableTls=true \
  --set server.disableGatewayAuth=true \
  --set service.type=ClusterIP \
  --set service.metricsPort=0 \
  --set image.pullPolicy=Always \
  --set supervisor.image.repository=ghcr.io/nvidia/openshell/supervisor \
  --set supervisor.image.tag=latest \
  --set server.sandboxImagePullPolicy=IfNotPresent
```

The chart pulls public images from `ghcr.io/nvidia/openshell/`.

### Create the SSH Handshake Secret

This secret is not created by the Helm chart and must be created manually:

```bash
kubectl -n openshell create secret generic openshell-ssh-handshake \
  --from-literal=secret=$(openssl rand -hex 32)
```

### Apply the Sandbox CRD

```bash
kubectl apply -f deploy/kube/manifests/agent-sandbox.yaml
```

This creates:
- The `agent-sandbox-system` namespace
- The `sandboxes.agents.x-k8s.io` CRD
- The sandbox controller StatefulSet with associated RBAC

### Wait for Ready

```bash
kubectl -n openshell rollout status statefulset/openshell --timeout=120s
```

### Verify

```bash
kubectl get pods -n openshell
kubectl get pods -n agent-sandbox-system
```

Expected output:

```
# openshell namespace
NAME          READY   STATUS    RESTARTS   AGE
openshell-0   1/1     Running   0          60s

# agent-sandbox-system namespace
NAME                         READY   STATUS    RESTARTS   AGE
agent-sandbox-controller-0   1/1     Running   0          45s
```

## 4. Install Kagent

### Install CRDs

From the kagent repo root:

```bash
cd kagent

helm install kagent-crds ./helm/kagent-crds/ \
  --namespace kagent \
  --create-namespace \
  --wait \
  --timeout 5m
```

### Install the Main Chart

```bash
helm install kagent ./helm/kagent/ \
  --namespace kagent \
  --create-namespace \
  --timeout 5m \
  --wait \
  --set registry=$DOCKER_REGISTRY \
  --set tag=$VERSION \
  --set imagePullPolicy=Always \
  --set controller.image.pullPolicy=Always \
  --set ui.image.pullPolicy=Always \
  --set ui.service.type=LoadBalancer \
  --set providers.default=anthropic \
  --set providers.anthropic.apiKey=<YOUR_ANTHROPIC_API_KEY>
```

Replace `providers.default` and the API key flag with your chosen provider:

| Provider | Flags |
|----------|-------|
| Anthropic | `--set providers.default=anthropic --set providers.anthropic.apiKey=<KEY>` |
| OpenAI | `--set providers.default=openAI --set providers.openAI.apiKey=<KEY>` |
| Gemini | `--set providers.default=gemini --set providers.gemini.apiKey=<KEY>` |
| Ollama | `--set providers.default=ollama` (no API key needed) |

## 5. Verify the Installation

### Check All Pods

```bash
kubectl get pods -n kagent
```

Expected output (all 1/1 Running):

```
NAME                                              READY   STATUS
kagent-controller-<hash>                          1/1     Running
kagent-ui-<hash>                                  1/1     Running
kagent-kmcp-controller-manager-<hash>             1/1     Running
kagent-postgresql-<hash>                          1/1     Running
kagent-grafana-mcp-<hash>                         1/1     Running
kagent-querydoc-<hash>                            1/1     Running
kagent-tools-<hash>                               1/1     Running
k8s-agent-<hash>                                  1/1     Running
istio-agent-<hash>                                1/1     Running
kgateway-agent-<hash>                             1/1     Running
promql-agent-<hash>                               1/1     Running
observability-agent-<hash>                        1/1     Running
helm-agent-<hash>                                 1/1     Running
argo-rollouts-conversion-agent-<hash>             1/1     Running
cilium-policy-agent-<hash>                        1/1     Running
cilium-manager-agent-<hash>                       1/1     Running
cilium-debug-agent-<hash>                         1/1     Running
```

### Check Controller Logs

```bash
kubectl logs -n kagent -l app.kubernetes.io/component=controller --tail=20
```

You should see successful startup including the openshell configuration:

```
"msg":"Starting KAgent Controller"
"msg":"running database migrations"
"msg":"database migrations complete"
```

If you see `unable to build openshell sandbox backends`, the OpenShell gateway is not reachable. See [Troubleshooting](#troubleshooting).

### Access the UI

Get the external IP:

```bash
export KAGENT_IP=$(kubectl get svc kagent-ui -n kagent -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "Kagent UI: http://$KAGENT_IP:8080"
```

Or port-forward:

```bash
kubectl -n kagent port-forward svc/kagent-ui 8080:8080
# Open http://localhost:8080
```

## Troubleshooting

### Controller CrashLoopBackOff: "unable to build openshell sandbox backends"

The kagent controller cannot reach the OpenShell gateway. Verify:

```bash
# Check OpenShell is running
kubectl get pods -n openshell

# Check the service is resolvable
kubectl run -it --rm debug --image=busybox --restart=Never -- \
  nslookup openshell.openshell.svc.cluster.local

# Check connectivity
kubectl run -it --rm debug --image=busybox --restart=Never -- \
  wget -qO- --timeout=5 http://openshell.openshell.svc.cluster.local:8080/healthz
```

If OpenShell was deployed after kagent, restart the controller:

```bash
kubectl rollout restart deployment kagent-controller -n kagent
```

### ImagePullBackOff: 403 Forbidden

The GKE nodes cannot pull from your container registry. Two fixes:

**Option A: Create an imagePullSecret** (recommended for default node pools with limited OAuth scopes):

```bash
kubectl create secret docker-registry gar-pull-secret \
  --namespace kagent \
  --docker-server=us-docker.pkg.dev \
  --docker-username=oauth2accesstoken \
  --docker-password="$(gcloud auth print-access-token)"
```

Then add `--set 'imagePullSecrets[0].name=gar-pull-secret'` to your Helm install/upgrade command.

> **Note**: The `oauth2accesstoken` credential expires after ~1 hour. For longer-lived access, use a service account key or Workload Identity.

**Option B: Grant IAM access** (requires `cloud-platform` OAuth scope on the node pool):

```bash
gcloud artifacts repositories add-iam-policy-binding <REPO> \
  --location=<LOCATION> \
  --member="serviceAccount:<NODE_SA_EMAIL>" \
  --role="roles/artifactregistry.reader" \
  --project=<PROJECT>
```

### Agent Pods Stuck at 0/1

Agent pods (k8s-agent, istio-agent, etc.) take 30-60 seconds to initialize. If they remain at 0/1 after 2 minutes, check the logs:

```bash
kubectl logs -n kagent <agent-pod-name>
```

## Cleanup

To remove the full installation:

```bash
# Remove kagent
helm uninstall kagent -n kagent
helm uninstall kagent-crds -n kagent
kubectl delete namespace kagent

# Remove OpenShell
helm uninstall openshell -n openshell
kubectl delete namespace openshell

# Remove sandbox controller and CRD
kubectl delete -f deploy/kube/manifests/agent-sandbox.yaml
kubectl delete namespace agent-sandbox-system
```

## Reference

| Component | Value |
|-----------|-------|
| Kagent Branch | `upstream/eitanya/openshell` (kagent-dev/kagent) |
| OpenShell Branch | `feat/k8s-supervisor-sideload-fork` (kagent-dev/OpenShell) |
| OpenShell Gateway Image | `ghcr.io/nvidia/openshell/gateway:latest` |
| OpenShell Supervisor Image | `ghcr.io/nvidia/openshell/supervisor:latest` |
| Sandbox Base Image | `ghcr.io/nvidia/openshell-community/sandboxes/base:latest` |
| Kagent UI Port | 8080 |
| Kagent Controller API Port | 8083 |
| OpenShell gRPC Port | 8080 |
| OpenShell Health Port | 8081 |
