# Kubernetes Setup Guide

Deploy LiteLLM proxy with the Rubrik plugin to Kubernetes with F5 NGINX Ingress.

> **Note:** This guide uses [Kind](https://kind.sigs.k8s.io/) (Kubernetes in Docker) for local development, but the manifests in `kube-setup/litellm/` are standard Kubernetes resources. They work on any K8s cluster — EKS, GKE, AKS, self-hosted, etc. The Kind-specific steps (cluster creation, image sideloading, port mapping) can be skipped if you're deploying to a real cluster.

Two options for loading the Rubrik plugin:

- **Option A — ConfigMap:** Mount the plugin script via a Kubernetes ConfigMap. No image build needed.
- **Option B — Custom Image:** Bake the plugin into a custom Docker image. Cleaner for production, no ConfigMap size limits.

Both use the same cluster, ingress, secrets, and service setup.

## Prerequisites

- Docker
- [Kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installation)
- kubectl
- Helm

## Step 1: Create the Kind Cluster

The Kind config maps your machine's port 80 to the cluster so the ingress controller can receive traffic.

```bash
kind create cluster --name litellm-local --config ./kube-setup/kind-config.yaml
```

The config (`kube-setup/kind-config.yaml`) maps `localhost:80 → cluster node:80`.

## Step 2: Install NGINX Ingress Controller

This repo includes the F5 NGINX Ingress Controller Helm chart locally in `kube-setup/nginx-ingress/`.

```bash
helm install nginx-ingress ./kube-setup/nginx-ingress \
  --namespace nginx-ingress --create-namespace \
  -f ./kube-setup/nginx-simple-vals.yaml
```

Wait for the NGINX pod to be ready:

```bash
kubectl get pods -n nginx-ingress -w
```

## Step 3: Configure Secrets

Edit `kube-setup/litellm/secrets.yaml` with your actual API keys and Rubrik credentials:

```yaml
stringData:
  OPENAI_KEY: "your-openai-key"
  ANTH_KEY: "your-anthropic-key"
  RBK_KEY: "your-rubrik-key"
  RBK_WEBHOOK: "your-rubrik-webhook-url"
  LITELLM_MASTER_KEY: "sk_1234"
```

> **Tip:** The `.gitignore` already excludes `real-secrets.yaml` if you want to keep a copy with actual values alongside the template.

Apply:

```bash
kubectl apply -f ./kube-setup/litellm/secrets.yaml
```

## Step 4: Deploy LiteLLM

### Option A: ConfigMap (No Image Build)

This mounts both the config and plugin into the container via ConfigMaps.

```bash
# Apply ConfigMaps
kubectl apply -f ./kube-setup/litellm/litellm-configmap.yaml
kubectl apply -f ./kube-setup/litellm/plugin-configmap.yaml

# Deploy
kubectl apply -f ./kube-setup/litellm/deployment.yaml

# Service and Ingress
kubectl apply -f ./kube-setup/litellm/service.yaml
kubectl apply -f ./kube-setup/litellm/ingress.yaml
```

**How it works:** The deployment mounts two ConfigMaps as files:
- `litellm-config` → `/app/config.yaml`
- `litellm-plugin` → `/app/rubrik_plugin.py`

### Option B: Custom Image

Bake the plugin into the image so you don't need the plugin ConfigMap.

**Build and load the image:**

```bash
# Build locally
docker build -t litellm-custom-proxy:local -f build/Dockerfile .

# Sideload into Kind (required since Kind can't pull from your local Docker)
kind load docker-image litellm-custom-proxy:local --name litellm-local
```

**Deploy:**

```bash
# Config only (plugin is in the image)
kubectl apply -f ./kube-setup/litellm/litellm-configmap.yaml

# Use the custom image deployment
kubectl apply -f ./kube-setup/litellm/deployment-custom-image.yaml

# Service and Ingress
kubectl apply -f ./kube-setup/litellm/service.yaml
kubectl apply -f ./kube-setup/litellm/ingress.yaml
```

> **Important:** The `deployment-custom-image.yaml` sets `imagePullPolicy: Always` by default. For local Kind development, change this to `IfNotPresent` or `Never` — otherwise Kubernetes will try to pull `litellm-custom-proxy:local` from the internet and fail with `ImagePullBackOff`.

## Step 5: Verify

Watch pods come up:

```bash
kubectl get pods -w
```

Wait for pods to show `READY` (may take 15-30 seconds for image pull and health probes).

Check the ingress:

```bash
kubectl get ingress litellm-ingress
```

## Step 6: Test

The ingress is configured for `litellm.yourdomain.com`. Two ways to test locally:

**Quick — pass the Host header:**

```bash
curl -H "Host: litellm.yourdomain.com" http://localhost/health/liveliness
```

**Proper — add to /etc/hosts:**

Add this line to `/etc/hosts`:

```
127.0.0.1 litellm.yourdomain.com
```

Then:

```bash
curl http://litellm.yourdomain.com/health/liveliness

curl http://litellm.yourdomain.com/v1/chat/completions \
  -H "Authorization: Bearer sk_1234" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-6",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## Debugging

```bash
# Pod logs
kubectl logs -l app=litellm -f

# Describe pod for events (image pull issues, probe failures, etc.)
kubectl describe pod -l app=litellm

# Check NGINX ingress logs
kubectl logs -n nginx-ingress -l app.kubernetes.io/name=nginx-ingress -f

# Shell into a pod
kubectl exec -it $(kubectl get pod -l app=litellm -o jsonpath='{.items[0].metadata.name}') -- /bin/bash
```

## Manifest Reference

| File | Purpose |
|---|---|
| `secrets.yaml` | API keys and Rubrik credentials as a Kubernetes Secret |
| `litellm-configmap.yaml` | LiteLLM `config.yaml` as a ConfigMap |
| `plugin-configmap.yaml` | `rubrik_plugin.py` as a ConfigMap (Option A only) |
| `deployment.yaml` | Deployment using ConfigMaps for config + plugin |
| `deployment-custom-image.yaml` | Deployment using custom image (plugin baked in) |
| `service.yaml` | ClusterIP service exposing port 80 → 4000 |
| `ingress.yaml` | NGINX ingress routing `litellm.yourdomain.com` to the service |

## Cleanup

Destroy the entire Kind cluster (removes everything — LiteLLM, NGINX, all resources):

```bash
kind delete cluster --name litellm-local
```
