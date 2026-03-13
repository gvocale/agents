#!/bin/bash
set -e

echo "[entrypoint] Starting job-hunting-agent container…"

# ── Decode secrets from env vars (if present) ─────────────────────────────────
if [ -n "$GMAIL_CREDENTIALS_JSON" ] && [ ! -f /app/credentials.json ]; then
    echo "$GMAIL_CREDENTIALS_JSON" | base64 -d > /app/credentials.json
    echo "[entrypoint] Decoded GMAIL_CREDENTIALS_JSON → credentials.json"
fi

if [ -n "$GMAIL_TOKEN_JSON" ] && [ ! -f /app/token.json ]; then
    echo "$GMAIL_TOKEN_JSON" | base64 -d > /app/token.json
    echo "[entrypoint] Decoded GMAIL_TOKEN_JSON → token.json"
fi

# ── Write .env file from env vars (cron doesn't inherit env) ──────────────────
cat > /app/.env <<EOF
GEMINI_API_KEY=${GEMINI_API_KEY}
GMAIL_SENDER_EMAIL=${GMAIL_SENDER_EMAIL:-gvocale@gmail.com}
LOG_LEVEL=${LOG_LEVEL:-INFO}
EOF
echo "[entrypoint] Wrote .env file"

# ── Set up cron job ───────────────────────────────────────────────────────────
CRON_SCHEDULE="${CRON_SCHEDULE:-0 8 * * *}"
echo "${CRON_SCHEDULE} /app/run.sh >> /proc/1/fd/1 2>&1" | crontab -
echo "[entrypoint] Cron scheduled: ${CRON_SCHEDULE}"

# ── Run once at startup (optional) ────────────────────────────────────────────
if [ "${RUN_ON_STARTUP:-false}" = "true" ]; then
    echo "[entrypoint] RUN_ON_STARTUP=true — running agent now…"
    /app/run.sh
fi

echo "[entrypoint] Container ready. Waiting for cron…"
exec cron -f
