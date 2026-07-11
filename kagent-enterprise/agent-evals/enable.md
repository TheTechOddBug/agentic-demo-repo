Agent Evals is a feature flag within the kagent helm installation. To enable it:

```
agentevals.enabled=true
```

Example:

```
helm upgrade kagent-mgmt oci://us-docker.pkg.dev/developers-369321/solo-enterprise/charts/management \
  --version 0.4.5 \
  --namespace kagent \
  --reuse-values \
  --set agentevals.enabled=true
```