- Confirmed snapshot bucket  existed with uniform bucket-level access. If it doesn't exist, create one.

- Verified node service account permissions:
    - Artifact Registry image reads
    - Cloud Storage object reads

- Verified Atelet Workload Identity permissions:
    - Cloud Storage object administration
    - Artifact Registry reads
    - Bucket access

- Enabled Kubernetes beta APIs required by Agent Substrate:
    - PodCertificateRequest
    - ClusterTrustBundle

- Enabled GKE Workload Identity

- Installed Agent Substrate CRDs:
    - ActorTemplate
    - WorkerPool
    - SandboxConfig

- Installed cluster-wide RBAC for Substrate controller and runtime components.

- Installed SandboxConfig validation policy and binding.

- Created gvisor-default sandbox configuration using runsc assets.

- Created namespaces:
    - ate-system
    - podcertificate-controller-system

- Generated Substrate certificate-authority pools:
    - Service DNS CA
    - Pod identity CA
    - Session identity CA

- Generated JWT signing authority for session IDs.

- Installed Pod Certificate controller and its RBAC.

- Published service-DNS and pod-identity ClusterTrustBundle resources.

- Generated Valkey trust certificate from service-DNS CA.

- Created API server environment configuration:
    - Valkey cluster address
    - Valkey TLS server name
    - Client certificate path
    - JWT issuer
    - JWT authentication mode
    - Disabled Google IAM authentication for local Valkey

- Configured exact GKE JWT issuer URL for cluster authentication.

- Build current Substrate source images with `ko`.

- Pushed immutable images and SBOMs to project container registry:
    - API server
    - Controller
    - Atelet
    - Atenet
    - Pod Certificate controller

- Rendered JWT-mode Kubernetes manifests through Kustomize.

- Installed Substrate service accounts, Roles, RoleBindings, ClusterRoles, and ClusterRoleBindings.

- Installed core control-plane components:
    - Ate API server
    - Ate controller
    - Atelet DaemonSet
    - Atenet router
    - Atenet DNS controller
    - CoreDNS
    - Pod Certificate controller

- Installed supporting services and configuration:
    - API service
    - Controller service
    - Router service
    - DNS service
    - Valkey services
    - Envoy configuration
    - Valkey configuration

- Installed six-member TLS-enabled Valkey StatefulSet with persistent volumes.

- Installed one-time Valkey cluster initialization Job.

- Added gVisor taint toleration to Atelet so it could run on sandbox nodes.

- Added compatible-node placement and tolerations to certificate-dependent workloads:
    - API server
    - Controller
    - Router
    - Valkey
    - Valkey initialization Job

- Initialized Valkey topology:
    - Three masters
    - Three replicas
    - All 16,384 hash slots covered

- Verified final health:
    - API server 1/1
    - Controller 1/1
    - Router 1/1
    - DNS 1/1
    - Valkey 6/6
    - Atelet 13/13
    - Initialization Job Complete
    - Service endpoints populated