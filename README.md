# LiteLLM Proxy + Rubrik Agent Cloud Integration

A quick-start guide for integrating [LiteLLM Proxy](https://docs.litellm.ai/) with [Rubrik Agent Cloud (RAC)](https://www.rubrik.com/). This repo contains everything needed to deploy a LiteLLM proxy that routes LLM API calls through the Rubrik plugin for logging, guardrails, and tool blocking.

Use this as a reference when supporting customers looking to integrate their LiteLLM deployments with RAC, or when running a POC.

## Architecture

```
┌──────────────┐        ┌──────────────────┐        ┌─────────────────────┐
│  Client /    │  HTTP   │   LiteLLM Proxy  │  HTTP   │   LLM Provider      │
│  Application ├───────►│                  ├───────►│  (Anthropic, OpenAI) │
│              │        │  ┌────────────┐  │        └─────────────────────┘
└──────────────┘        │  │  Rubrik    │  │
                        │  │  Plugin    │  │
                        │  └─────┬──────┘  │
                        └────────┼─────────┘
                                 │ Webhook
                                 ▼
                        ┌──────────────────┐
                        │  Rubrik Agent    │
                        │  Cloud (RAC)     │
                        └──────────────────┘
```

The Rubrik plugin (`rubrik_plugin.py`) is loaded by LiteLLM as a callback. It intercepts requests and responses, forwarding telemetry and policy decisions to RAC via the configured webhook endpoint.

## Prerequisites

- **Docker** (all methods)
- **Python 3.13** (local method only)
- **Kind** + **kubectl** + **Helm** (Kubernetes method only)
- API keys for your LLM providers (Anthropic, OpenAI, Azure, etc.)
- Rubrik Agent Cloud webhook URL and key

## Environment Variables

| Variable | Description |
|---|---|
| `ANTH_KEY` | Anthropic API key |
| `OPENAI_KEY` | OpenAI API key |
| `AZURE_API_KEY` | Azure OpenAI API key |
| `AZURE_API_BASE` | Azure OpenAI endpoint URL |
| `RBK_WEBHOOK` | Rubrik Agent Cloud webhook URL |
| `RBK_KEY` | Rubrik Agent Cloud API key |
| `LITELLM_MASTER_KEY` | Master key for LiteLLM proxy auth (clients pass this as `Authorization: Bearer <key>`) |

## Key Files

| File | Purpose |
|---|---|
| `config.yaml` | LiteLLM proxy configuration — model list, callbacks, database |
| `rubrik_plugin.py` | Rubrik custom plugin for logging and guardrails ([source](https://github.com/predibase/litellm/blob/13935695fdf9d33cf4f526486a1b9983b3f37387/litellm/integrations/rubrik.py)) |
| `build/Dockerfile` | Custom image that bakes the plugin into the LiteLLM container |
| `kube-setup/` | Kubernetes manifests (Kind config, NGINX ingress, LiteLLM deployment) |

## Deployment Methods

There are three ways to run this, from simplest to most production-like:

### 1. Local (Python)

Run LiteLLM directly with Python. Good for quick testing and debugging.

```bash
# Start Postgres (required for LiteLLM's database)
docker run -d --name llm-postgres \
  -e POSTGRES_PASSWORD=dbpass \
  -p 5432:5432 \
  -v pgdata:/var/lib/postgresql/data \
  postgres:17

docker exec -it llm-postgres psql -U postgres -c "CREATE DATABASE litellm;"

# Set your env vars (see .env.example or export manually)
export ANTH_KEY="your-key"
export RBK_WEBHOOK="your-webhook-url"
export RBK_KEY="your-rubrik-key"

# Run the proxy
litellm --config config.yaml --detailed_debug
```

**[Full local setup guide →](docs/local-setup.md)**

### 2. Docker

Run LiteLLM in a container with your config and plugin mounted as volumes. No local Python required.

```bash
docker run \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -v $(pwd)/rubrik_plugin.py:/app/rubrik_plugin.py \
  -e ANTH_KEY="your-key" \
  -e RBK_WEBHOOK="your-webhook-url" \
  -e RBK_KEY="your-rubrik-key" \
  -p 4000:4000 \
  ghcr.io/berriai/litellm:main-latest \
  --config /app/config.yaml --detailed_debug
```

**[Full Docker guide →](docs/docker-setup.md)**

### 3. Kubernetes (Kind)

Deploy to a local Kind cluster with NGINX ingress. Two options for loading the plugin:

- **Option A — ConfigMap:** Mount the plugin script via a ConfigMap (no image build required)
- **Option B — Custom Image:** Bake the plugin into a custom Docker image

Both approaches use the same Kind cluster, NGINX ingress, secrets, and service/ingress manifests.

```bash
# Create cluster
kind create cluster --name litellm-local --config ./kube-setup/kind-config.yaml

# Install NGINX ingress
helm install nginx-ingress ./kube-setup/nginx-ingress \
  --namespace nginx-ingress --create-namespace \
  -f ./kube-setup/nginx-simple-vals.yaml

# Deploy LiteLLM (see full guide for Option A vs Option B)
kubectl apply -f ./kube-setup/litellm/secrets.yaml
kubectl apply -f ./kube-setup/litellm/
```

**[Full Kubernetes guide →](docs/kubernetes-setup.md)**

## Testing

Once the proxy is running (on any method), verify it's healthy:

```bash
# Local or Docker (port 4000)
curl http://localhost:4000/health/liveliness

# Kubernetes with Ingress (port 80)
curl -H "Host: litellm.yourdomain.com" http://localhost/health/liveliness
```

Send a test chat completion:

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer sk_1234" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-6",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## Cleanup

```bash
# Docker
docker stop llm-postgres && docker rm llm-postgres

# Kind cluster (removes everything)
kind delete cluster --name litellm-local
```

## Repo Structure

```
.
├── README.md                  # This file
├── config.yaml                # LiteLLM proxy config
├── rubrik_plugin.py           # Rubrik RAC plugin
├── main.py                    # Placeholder entrypoint
├── build/
│   └── Dockerfile             # Custom image with plugin baked in
├── kube-setup/
│   ├── kind-config.yaml       # Kind cluster config with port mapping
│   ├── nginx-simple-vals.yaml # Helm values for NGINX ingress
│   ├── nginx-ingress/         # F5 NGINX Ingress Controller Helm chart
│   └── litellm/
│       ├── secrets.yaml           # API keys and webhook credentials
│       ├── litellm-configmap.yaml # LiteLLM config as ConfigMap
│       ├── plugin-configmap.yaml  # Rubrik plugin as ConfigMap
│       ├── deployment.yaml        # Deployment (ConfigMap option)
│       ├── deployment-custom-image.yaml  # Deployment (custom image option)
│       ├── service.yaml           # ClusterIP service
│       └── ingress.yaml           # NGINX ingress rule
└── docs/
    ├── local-setup.md         # Detailed local setup guide
    ├── docker-setup.md        # Detailed Docker guide
    └── kubernetes-setup.md    # Detailed Kubernetes guide
```
