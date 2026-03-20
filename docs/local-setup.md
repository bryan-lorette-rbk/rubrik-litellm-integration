# Local Setup Guide

Run LiteLLM proxy directly on your machine with Python. Best for quick testing, debugging the plugin, and iterating on `config.yaml`.

## Prerequisites

- Python 3.13 (the Rubrik plugin requires this — newer versions may have issues with Prisma)
- Docker (for Postgres)
- `pip` or `uv` for package management

## Step 1: Start Postgres

LiteLLM uses Postgres to store model configurations and usage data.

```bash
docker run -d --name llm-postgres \
  -e POSTGRES_PASSWORD=dbpass \
  -p 5432:5432 \
  -v pgdata:/var/lib/postgresql/data \
  postgres:17
```

Create the database:

```bash
docker exec -it llm-postgres psql -U postgres -c "CREATE DATABASE litellm;"
```

## Step 2: Install LiteLLM

```bash
pip install 'litellm[proxy]'
```

After install, generate the Prisma client (required for database connectivity):

```bash
prisma generate
```

> **Note:** If `prisma generate` fails, confirm you're on Python 3.13. Newer Python versions may not be supported by the Prisma client yet.

## Step 3: Set Environment Variables

Export your API keys and Rubrik credentials. You can also use a `.env` file.

```bash
export ANTH_KEY="your-anthropic-key"
export OPENAI_KEY="your-openai-key"
export RBK_WEBHOOK="your-rubrik-webhook-url"
export RBK_KEY="your-rubrik-key"
```

## Step 4: Review the Config

The `config.yaml` in the repo root is ready to use. Key things to note:

- **`model_list`** — Defines which models are available through the proxy. Add or remove models as needed for your POC.
- **`callbacks: rubrik_plugin.proxy_handler_instance`** — This is what loads the Rubrik plugin. The plugin file must be in the same directory you run the proxy from.
- **`database_url`** — Points to the Postgres container. Update if you changed the password or port.
- **`master_key`** — Clients authenticate with this key. Change `sk_1234` to something real for anything beyond local testing.

## Step 5: Run the Proxy

From the repo root (where `config.yaml` and `rubrik_plugin.py` live):

```bash
litellm --config config.yaml --detailed_debug
```

The proxy starts on `http://localhost:4000`. The `--detailed_debug` flag gives verbose output so you can see the Rubrik plugin intercepting calls.

## Step 6: Verify

```bash
# Health check
curl http://localhost:4000/health/liveliness

# Test a completion
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer sk_1234" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-6",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

Check the proxy logs — you should see the Rubrik plugin logging the request and forwarding telemetry to RAC via the webhook.

## Troubleshooting

| Issue | Fix |
|---|---|
| `prisma generate` fails | Ensure Python 3.13 — check with `python --version` |
| Plugin not loading | Run from the same directory as `rubrik_plugin.py` |
| Database connection refused | Confirm Postgres is running: `docker ps` |
| `401 Unauthorized` on API calls | Pass the master key: `-H "Authorization: Bearer sk_1234"` |

## Cleanup

```bash
docker stop llm-postgres && docker rm llm-postgres
docker volume rm pgdata  # optional — removes stored data
```
