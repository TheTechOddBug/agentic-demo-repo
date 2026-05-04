# AgentRegistry Enterprise - Setup Guide

This guide walks through installing AgentRegistry Enterprise on a Kubernetes cluster with Keycloak OIDC authentication and AWS Bedrock AgentCore integration.

## Prerequisites

- A running Kubernetes cluster (GKE, EKS, or Kind)
- `kubectl` configured and pointing at your cluster
- `helm` v3 installed
- `aws` CLI installed (for AWS provider setup)
- A running Keycloak instance with a configured realm (see [Keycloak Setup](#keycloak-setup) below)
- AWS IAM credentials (long-lived IAM user recommended over temporary session tokens)

## 1. Install the Enterprise arctl CLI

```bash
curl -sSL https://storage.googleapis.com/agentregistry-enterprise/install.sh | ARCTL_VERSION=v2026.05.0 sh
export PATH=$HOME/.arctl/bin:$PATH
```

Verify the installation:

```bash
arctl version --json
```

## 2. Create the Namespace

```bash
kubectl create namespace agentregistry-system
```

## 3. Prepare the Helm Values File

Create a values file. **Do not commit this file** — it contains secrets.

```bash
cat > /tmp/are-values.yaml <<'EOF'
image:
  tag: v2026.05.0

service:
  type: LoadBalancer

# OIDC / Keycloak
oidc:
  issuer: "<KEYCLOAK_ISSUER_URL>"          # e.g. https://keycloak.example.com/realms/my-realm
  clientId: "<OIDC_BACKEND_CLIENT_ID>"     # e.g. kagent-backend
  publicClientId: "<OIDC_UI_CLIENT_ID>"    # e.g. kagent-ui
  clientSecret: "<OIDC_CLIENT_SECRET>"
  roleClaim: "Groups"                       # Must match the claim name in your Keycloak token
  superuserRole: "admins"
  insecureSkipVerify: false

# AWS credentials (long-lived IAM user keys recommended)
aws:
  enabled: true
  accessKeyId: "<AWS_ACCESS_KEY_ID>"
  secretAccessKey: "<AWS_SECRET_ACCESS_KEY>"
  sessionToken: ""                          # Leave empty for IAM user keys
  region: "us-east-1"

# Bundled PostgreSQL (dev/eval only)
database:
  postgres:
    bundled:
      enabled: true

# ClickHouse (observability)
clickhouse:
  enabled: true

# OTel Collector
telemetry:
  enabled: true
EOF
```

### Important Notes on Values

**OIDC `roleClaim`**: This must match the exact claim name in the JWT token issued by your Keycloak realm. Common values:
- `Groups` (capital G) — used by many Keycloak configurations with a Groups protocol mapper
- `groups` (lowercase) — some configurations use this
- `realm_access.roles` — Keycloak's built-in realm roles claim

If you see the error _"The logged in user does not have any mapped roles"_ after logging in, the `roleClaim` value does not match what's in your token. Decode your token at [jwt.io](https://jwt.io) to find the correct claim name.

**AWS Credentials**: Use long-lived IAM user credentials rather than temporary session tokens (STS). Session tokens expire (typically 1-12 hours) and require frequent Helm upgrades to rotate. If you must use temporary credentials, include the `sessionToken` field.

## 4. Install the Helm Chart

```bash
helm upgrade --install agentregistry-enterprise \
  oci://us-docker.pkg.dev/solo-public/agentregistry-enterprise/helm/agentregistry-enterprise \
  --version 2026.05.0 \
  --namespace agentregistry-system \
  -f /tmp/are-values.yaml \
  --wait --timeout 5m
```

## 5. Verify the Installation

Check that all pods are running:

```bash
kubectl get pods -n agentregistry-system
```

Expected output (all 1/1 Running):

```
NAME                                                            READY   STATUS
agentregistry-enterprise-<hash>                                 1/1     Running
agentregistry-enterprise-clickhouse-shard0-0                    1/1     Running
agentregistry-enterprise-postgresql-<hash>                      1/1     Running
agentregistry-enterprise-telemetry-collector-<hash>             1/1     Running
```

Check the services:

```bash
kubectl get svc -n agentregistry-system
```

The `agentregistry-enterprise` service will have an external IP (LoadBalancer) with ports:
- **8080** — HTTP (UI + API)
- **21212** — Agent Gateway gRPC
- **31313** — MCP server

Check the server logs for any errors:

```bash
kubectl logs -n agentregistry-system deployment/agentregistry-enterprise --tail=30
```

You should see:
- `all migrations applied successfully` (both OSS and enterprise migrations)
- `HTTP server starting` on `:8080`
- `MCP HTTP server starting` on `:31313`
- `using OIDC authentication`

Get the external IP for accessing the UI:

```bash
export AR_IP=$(kubectl get svc agentregistry-enterprise -n agentregistry-system -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "UI: http://$AR_IP:8080"
echo "API docs: http://$AR_IP:8080/docs"
```

## 6. Configure and Authenticate the arctl CLI

Point the CLI at your server:

```bash
export ARCTL_API_BASE_URL=http://$AR_IP:8080
```

Verify connectivity:

```bash
arctl version --json
```

The output should show both `arctl_version` and `server_version`.

### Log In

Authenticate via the device-code flow (opens a browser):

```bash
arctl user login \
  --oidc-issuer-url <KEYCLOAK_ISSUER_URL> \
  --oidc-client-id <OIDC_PUBLIC_CLIENT_ID>
```

For example:

```bash
arctl user login \
  --oidc-issuer-url http://34.23.253.195:8080/realms/kagent-dev \
  --oidc-client-id are-cli
```

This opens a browser where you authenticate with Keycloak. The token is stored in your system keychain and refreshed automatically on subsequent commands.

Verify authentication:

```bash
arctl get providers
```

> **Important**: The `arctl user login` command requires the **OAuth 2.0 Device Authorization Grant** to be enabled on the Keycloak client. If you see `Client is not allowed to initiate OAuth 2.0 Device Authorization Grant`, enable the device flow in Keycloak:
> Keycloak Admin > Realm > Clients > your client > Capability config > OAuth 2.0 Device Authorization Grant > ON.

> **Note**: The enterprise `arctl` installs to `$HOME/.arctl/bin/arctl`. If you also have the OSS `arctl` installed (e.g., at `/usr/local/bin/arctl`), make sure the enterprise one takes precedence in your PATH. The OSS CLI does not have `user login`, `apply`, `provider`, or other enterprise commands.

## 7. Set Up the AWS Provider

The AWS provider setup is a two-step process: create an IAM role in your AWS account, then register it with AgentRegistry.

### Step 1: Generate the CloudFormation Template

```bash
arctl provider setup aws --aws-account-id <YOUR_AWS_ACCOUNT_ID> > /tmp/agentregistry-cf.yaml
```

> **Note**: This command requires authentication. If running from the CLI, log in first with `arctl user login`. Alternatively, you can pass `--registry-token <token>`.

This outputs a CloudFormation template that creates an IAM role with permissions for:
- Bedrock AgentCore (create/manage agent runtimes)
- IAM (create execution roles for agents)
- S3 (upload agent code artifacts)
- CloudWatch Logs (agent logging)
- AppConfig (agentgateway configuration)
- Cognito (optional agent auth)
- EC2 (optional managed agentgateway instances)

Note the **External ID** and **Role Name** printed at the bottom of the template.

### Step 2: Deploy the CloudFormation Stack

```bash
aws cloudformation create-stack \
  --stack-name agentregistry-access-role \
  --template-body file:///tmp/agentregistry-cf.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

Wait for completion:

```bash
aws cloudformation wait stack-create-complete \
  --stack-name agentregistry-access-role \
  --region us-east-1
```

Retrieve the outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name agentregistry-access-role \
  --region us-east-1 \
  --query 'Stacks[0].Outputs'
```

Save the `RoleArn` and `ExternalId` from the output.

### Step 3: Register the AWS Provider

Create the provider manifest:

```bash
export AWS_ROLE_ARN="<RoleArn from CloudFormation output>"
export AWS_EXTERNAL_ID="<ExternalId from CloudFormation output>"
export AWS_REGION="us-east-1"

cat > /tmp/aws-provider.yaml <<EOF
apiVersion: ar.dev/v1alpha1
kind: Provider
metadata:
  name: my-aws
spec:
  platform: aws
  config:
    roleArn: "${AWS_ROLE_ARN}"
    externalId: "${AWS_EXTERNAL_ID}"
    region: "${AWS_REGION}"
EOF
```

Apply it:

```bash
arctl apply -f /tmp/aws-provider.yaml
```

> **Note**: This requires an authenticated session. You can authenticate via:
> - `arctl user login` (device-code flow, opens browser)
> - `--registry-token <token>` flag
> - The AgentRegistry UI (navigate to Providers and add the AWS provider there)

## 8. Deploy an Agent to AWS

Once the AWS provider is registered, you can deploy agents to AWS Bedrock AgentCore.

### Create a Test Agent

A minimal echo agent is included in this repo under `demo-agent/`. It has three files:

- `agent.py` — a simple Python agent that echoes back any message it receives (zero dependencies)
- `agent.yaml` — registers the agent in the AgentRegistry
- `deploy.yaml` — deploys it to AWS via the registered provider

The agent manifest (`agent.yaml`):

```yaml
apiVersion: ar.dev/v1alpha1
kind: Agent
metadata:
  name: echo-agent
  version: "1.0.0"
spec:
  description: "A minimal echo agent for testing deployments to AWS Bedrock AgentCore"
  source:
    type: python
    entrypoint: agent.py
```

The deployment manifest (`deploy.yaml`):

```yaml
apiVersion: ar.dev/v1alpha1
kind: Deployment
metadata:
  name: echo-agent
spec:
  providerRef:
    name: AWS          # Must match the name of your registered AWS provider
  targetRef:
    kind: Agent
    name: echo-agent
```

### Register and Deploy

```bash
cd demo-agent/

# Register the agent in the registry
arctl apply -f agent.yaml

# Deploy it to AWS Bedrock AgentCore
arctl apply -f deploy.yaml
```

### Check Deployment Status

```bash
arctl get deployments
```

The deployment will go through `deploying` -> `deployed` (or `failed` with an error message). You can also check deployment logs:

```bash
arctl get deployments echo-agent --logs
```

### Clean Up the Deployment

To remove the agent from AWS:

```bash
arctl delete -f deploy.yaml
```

## 9. Updating AWS Credentials

If your AWS credentials change (e.g., key rotation), update the Helm values file and run:

```bash
helm upgrade agentregistry-enterprise \
  oci://us-docker.pkg.dev/solo-public/agentregistry-enterprise/helm/agentregistry-enterprise \
  --version 2026.05.0 \
  --namespace agentregistry-system \
  -f /tmp/are-values.yaml \
  --wait --timeout 5m
```

The server pod will roll automatically when the AWS secret changes.

## Keycloak Setup

If you need to deploy a local Keycloak instance on your cluster (rather than using an external one), follow these steps.

### Deploy Keycloak

The agentregistry-enterprise repo includes a pre-configured realm export at `dev/keycloak/realm-data/`. Deploy Keycloak with:

```bash
kubectl create namespace keycloak
kubectl create configmap keycloak-realm-config -n keycloak \
  --from-file=kagent-dev.json=dev/keycloak/realm-data/kagent-dev-realm.json

kubectl apply -n keycloak -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: keycloak
spec:
  replicas: 1
  selector:
    matchLabels:
      app: keycloak
  template:
    metadata:
      labels:
        app: keycloak
    spec:
      containers:
      - name: keycloak
        image: quay.io/keycloak/keycloak:24.0
        args: ["start-dev", "--import-realm"]
        env:
        - name: KEYCLOAK_ADMIN
          value: admin
        - name: KEYCLOAK_ADMIN_PASSWORD
          value: admin123
        - name: KC_HTTP_ENABLED
          value: "true"
        - name: KC_HOSTNAME_STRICT
          value: "false"
        - name: KC_HOSTNAME_STRICT_HTTPS
          value: "false"
        ports:
        - containerPort: 8080
        readinessProbe:
          httpGet:
            path: /realms/master
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        volumeMounts:
        - name: realm-config
          mountPath: /opt/keycloak/data/import
      volumes:
      - name: realm-config
        configMap:
          name: keycloak-realm-config
---
apiVersion: v1
kind: Service
metadata:
  name: keycloak
spec:
  type: LoadBalancer
  selector:
    app: keycloak
  ports:
  - port: 8080
    targetPort: 8080
EOF
```

Wait for the external IP:

```bash
export KC_IP=$(kubectl get svc keycloak -n keycloak -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "Keycloak admin: http://$KC_IP:8080 (admin / admin123)"
```

### Configure the Realm

The imported realm includes clients and groups but needs users and additional configuration:

```bash
# Get admin token
KC_TOKEN=$(curl -s -X POST "http://$KC_IP:8080/realms/master/protocol/openid-connect/token" \
  -d "grant_type=password" -d "client_id=admin-cli" \
  -d "username=admin" -d "password=admin123" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Import users (admin, reader, writer)
curl -s -X POST -H "Authorization: Bearer $KC_TOKEN" -H "Content-Type: application/json" \
  "http://$KC_IP:8080/admin/realms/kagent-dev/partialImport" \
  -d @dev/keycloak/realm-data/kagent-dev-users-0.json

# Set passwords (username = password for dev)
for USER in admin reader writer; do
  USER_ID=$(curl -s -H "Authorization: Bearer $KC_TOKEN" \
    "http://$KC_IP:8080/admin/realms/kagent-dev/users?username=$USER" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
  curl -s -X PUT -H "Authorization: Bearer $KC_TOKEN" -H "Content-Type: application/json" \
    "http://$KC_IP:8080/admin/realms/kagent-dev/users/$USER_ID/reset-password" \
    -d "{\"type\":\"password\",\"value\":\"$USER\",\"temporary\":false}"
done

# Add the groups scope to all clients so the "groups" claim appears in tokens
for CLIENT_ID in $(curl -s -H "Authorization: Bearer $KC_TOKEN" \
  "http://$KC_IP:8080/admin/realms/kagent-dev/clients" | python3 -c "
import sys,json
for c in json.load(sys.stdin):
    if c.get('clientId') in ('are-backend','are-cli','kagent-ui','kagent-backend'):
        print(c['id'])
"); do
  curl -s -X PUT -H "Authorization: Bearer $KC_TOKEN" \
    "http://$KC_IP:8080/admin/realms/kagent-dev/clients/$CLIENT_ID/default-client-scopes/groups-scope-kagent-dev"
done

# Enable standard flow + redirect URIs on are-cli (needed for browser login)
ARE_CLI_UUID=$(curl -s -H "Authorization: Bearer $KC_TOKEN" \
  "http://$KC_IP:8080/admin/realms/kagent-dev/clients" | python3 -c "
import sys,json
for c in json.load(sys.stdin):
    if c.get('clientId')=='are-cli': print(c['id'])
")
curl -s -X PUT -H "Authorization: Bearer $KC_TOKEN" -H "Content-Type: application/json" \
  "http://$KC_IP:8080/admin/realms/kagent-dev/clients/$ARE_CLI_UUID" \
  -d '{"clientId":"are-cli","standardFlowEnabled":true,"redirectUris":["*"],"webOrigins":["*"]}'

# Get the are-backend client secret (needed for Helm values)
ARE_BACKEND_UUID=$(curl -s -H "Authorization: Bearer $KC_TOKEN" \
  "http://$KC_IP:8080/admin/realms/kagent-dev/clients" | python3 -c "
import sys,json
for c in json.load(sys.stdin):
    if c.get('clientId')=='are-backend': print(c['id'])
")
ARE_SECRET=$(curl -s -X POST -H "Authorization: Bearer $KC_TOKEN" \
  "http://$KC_IP:8080/admin/realms/kagent-dev/clients/$ARE_BACKEND_UUID/client-secret" | python3 -c "import sys,json; print(json.load(sys.stdin)['value'])")
echo "are-backend client secret: $ARE_SECRET"
```

### Users and Groups

| User | Password | Group | Role |
|------|----------|-------|------|
| admin | admin | admins | Superuser (full access) |
| reader | reader | readers | Read-only |
| writer | writer | writers | Read + write |

### Keycloak Clients

| Client ID | Type | Device Flow | Use |
|-----------|------|-------------|-----|
| `are-backend` | Confidential | No | Server-side token validation |
| `are-cli` | Public | Yes | CLI device-code login |
| `kagent-backend` | Confidential | No | kagent integration |
| `kagent-ui` | Public | No | kagent UI |

### Helm Values for Local Keycloak

When using the local Keycloak, set these in your values file:

```yaml
oidc:
  issuer: "http://<KC_IP>:8080/realms/kagent-dev"
  clientId: "are-backend"
  publicClientId: "are-cli"
  clientSecret: "<are-backend client secret from above>"
  roleClaim: "groups"        # lowercase — matches the realm's Groups mapper claim name
  superuserRole: "admins"
  insecureSkipVerify: false
```

> **Note**: If Keycloak shows a "Cookie not found" error in the browser, ensure `KC_HOSTNAME_URL` is set to the external URL (e.g., `http://<KC_IP>:8080`) in the Keycloak deployment env vars. This ensures Keycloak generates cookies with the correct domain. For HTTPS setups, this is not needed.

## Troubleshooting

### "The logged in user does not have any mapped roles"

The OIDC token doesn't contain the expected role claim. Fix:

1. Decode your token (browser dev tools > Application > Storage, or [jwt.io](https://jwt.io))
2. Find the claim that contains your group/role memberships (e.g., `Groups`, `groups`, `realm_access.roles`)
3. Update `oidc.roleClaim` in your Helm values to match
4. Run `helm upgrade` to apply the change
5. Log out and back in

### "Token provider: disabled (encryption key not set)"

This is informational, not an error. Agent token minting (JWT) requires setting `config.jwtPrivateKey` in the Helm values (a 64-character hex string). This is only needed if you want to issue tokens to deployed agents. Generate one with:

```bash
openssl rand -hex 32
```

Then add to your values file:

```yaml
config:
  jwtPrivateKey: "<generated-hex-string>"
```

### Pods not starting

Check events and logs:

```bash
kubectl describe pod -n agentregistry-system -l app.kubernetes.io/name=agentregistry-enterprise
kubectl logs -n agentregistry-system deployment/agentregistry-enterprise -c wait-for-postgres
kubectl logs -n agentregistry-system deployment/agentregistry-enterprise
```

### CloudFormation stack fails

Check the stack events:

```bash
aws cloudformation describe-stack-events \
  --stack-name agentregistry-access-role \
  --region us-east-1 \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]'
```

Common causes:
- IAM user lacks `iam:CreateRole` or `cloudformation:CreateStack` permissions
- Role name already exists (use `--role-name` flag with a unique name in `arctl provider setup aws`)

## Cleanup

To remove the installation:

```bash
# Remove the Helm release
helm uninstall agentregistry-enterprise -n agentregistry-system

# Delete the namespace
kubectl delete namespace agentregistry-system

# Remove the AWS CloudFormation stack
aws cloudformation delete-stack \
  --stack-name agentregistry-access-role \
  --region us-east-1

# Remove temporary files
rm -f /tmp/are-values.yaml /tmp/aws-provider.yaml /tmp/agentregistry-cf.yaml
```

## Reference

| Component | Value |
|-----------|-------|
| Chart | `oci://us-docker.pkg.dev/solo-public/agentregistry-enterprise/helm/agentregistry-enterprise` |
| Chart Version | `2026.05.0` |
| Image | `us-docker.pkg.dev/solo-public/agentregistry-enterprise/server:v2026.05.0` |
| CLI Install | `curl -sSL https://storage.googleapis.com/agentregistry-enterprise/install.sh \| ARCTL_VERSION=v2026.05.0 sh` |
| HTTP Port | 8080 |
| gRPC Port | 21212 |
| MCP Port | 31313 |
| GitHub Release | [v2026.05.0](https://github.com/solo-io/agentregistry-enterprise/releases/tag/v2026.05.0) |
