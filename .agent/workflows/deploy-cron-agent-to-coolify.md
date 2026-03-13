---
description: How to deploy a cron-based Python agent to Coolify (not a web service)
---

# Deploy Cron Agent to Coolify

This workflow covers deploying a scheduled Python script (no HTTP server) to Coolify on the Hetzner server.

## Prerequisites
- Code pushed to `gvocale/agents` repo on GitHub
- Coolify connected to the GitHub repo

## 1. Docker Files

Your agent directory needs three files:

### Dockerfile
```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends cron && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py ./
COPY entrypoint.sh run.sh ./
RUN chmod +x entrypoint.sh run.sh
ENTRYPOINT ["/app/entrypoint.sh"]
```

### entrypoint.sh
Decodes base64 secrets from env vars, writes `.env` (cron doesn't inherit env), sets up cron, runs `cron -f`:
```bash
#!/bin/bash
set -e
# Decode any base64-encoded secret env vars to files here
# Write .env with all needed env vars
cat > /app/.env <<EOF
MY_API_KEY=${MY_API_KEY}
EOF
# Set up cron
CRON_SCHEDULE="${CRON_SCHEDULE:-0 8 * * *}"
echo "${CRON_SCHEDULE} /app/run.sh >> /proc/1/fd/1 2>&1" | crontab -
# Optional: run once on startup
if [ "${RUN_ON_STARTUP:-false}" = "true" ]; then /app/run.sh; fi
exec cron -f
```

### run.sh
```bash
#!/bin/bash
cd /app
/usr/local/bin/python main.py
```

## 2. Coolify Setup

// turbo-all

1. **New Resource** → Docker → Private Repository (GitHub App)
2. Set repo, branch `main`, Dockerfile path to `<agent-dir>/Dockerfile`, build context to `<agent-dir>/`
3. Add environment variables (secrets as base64-encoded strings)
4. **Disable health check** (no HTTP port)
5. Deploy

## 3. Verify

```bash
ssh coolify-de-falkenstein
docker ps | head -5
docker logs <container-id> --tail 20   # Should show entrypoint messages
docker exec <container-id> /app/run.sh  # Force manual run
```

## Key Patterns

- **Cron doesn't inherit env**: Write secrets to `.env` file in entrypoint
- **Logs to stdout**: `>> /proc/1/fd/1 2>&1` pipes cron output to docker logs
- **Base64 secrets**: Use `base64 -i secret.json | tr -d '\n'` locally, paste into Coolify env vars, decode in entrypoint
- **Configurable schedule**: `CRON_SCHEDULE` env var (default `0 8 * * *` = 8AM UTC)
- **Debug run**: `RUN_ON_STARTUP=true` env var or `docker exec <id> /app/run.sh`
