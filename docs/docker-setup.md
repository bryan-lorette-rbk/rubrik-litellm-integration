# Docker Setup Guide

Run LiteLLM proxy in a Docker container with the config and Rubrik plugin mounted as volumes. No local Python install required.

## Prerequisites

- Docker

## Quick Start

From the repo root:

```bash
docker run \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -v $(pwd)/rubrik_plugin.py:/app/rubrik_plugin.py \
  -e ANTH_KEY="your-anthropic-key" \
  -e OPENAI_KEY="your-openai-key" \
  -e RBK_WEBHOOK="your-rubrik-webhook-url" \
  -e RBK_KEY="your-rubrik-key" \
  -p 4000:4000 \
  ghcr.io/berriai/litellm:main-latest \
  --config /app/config.yaml --detailed_debug
```

This pulls the official LiteLLM image and mounts your local files into the container at `/app/`.

## What's Happening

- **`-v $(pwd)/config.yaml:/app/config.yaml`** — Mounts your proxy config into the container
- **`-v $(pwd)/rubrik_plugin.py:/app/rubrik_plugin.py`** — Mounts the Rubrik plugin so LiteLLM can load it via the `callbacks` setting in config
- **`-e`** flags — Pass API keys and Rubrik credentials as environment variables
- **`-p 4000:4000`** — Exposes the proxy on your machine's port 4000
- **`--config /app/config.yaml`** — Tells LiteLLM where to find the config inside the container

## Database Note

The `docker run` approach above does **not** include a database. The `config.yaml` in this repo has `database_url` pointing to `localhost:5432`, which won't resolve inside the container.

If you need database support (model storage, usage tracking), either:

1. **Start Postgres on a Docker network:**
   ```bash
   docker network create litellm-net

   docker run -d --name llm-postgres --network litellm-net \
     -e POSTGRES_PASSWORD=dbpass \
     postgres:17

   docker exec -it llm-postgres psql -U postgres -c "CREATE DATABASE litellm;"
   ```
   Then update `database_url` in your config to `postgresql://postgres:dbpass@llm-postgres:5432/litellm` and add `--network litellm-net` to the LiteLLM run command.

2. **Remove the `database_url` and `store_models_in_db`** settings from `config.yaml` if you don't need persistence.

## Building a Custom Image

Instead of mounting files at runtime, you can bake the plugin into a custom image. This is useful when deploying to environments where volume mounts aren't practical (e.g., Kubernetes without ConfigMaps).

The Dockerfile is at `build/Dockerfile`:

```bash
docker build -t litellm-custom-proxy:v1 -f build/Dockerfile .
```

> **Note:** The Dockerfile copies `custom_plugin.py` — rename your `rubrik_plugin.py` accordingly or update the `COPY` line in the Dockerfile.

Run it:

```bash
docker run \
  -e ANTH_KEY="your-anthropic-key" \
  -e RBK_WEBHOOK="your-rubrik-webhook-url" \
  -e RBK_KEY="your-rubrik-key" \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -p 4000:4000 \
  litellm-custom-proxy:v1 \
  --config /app/config.yaml
```

The plugin is already in the image, so you only need to mount the config.

## Verify

```bash
curl http://localhost:4000/health/liveliness

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
docker stop <container-id> && docker rm <container-id>
```
