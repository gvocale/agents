#!/usr/bin/env bash
set -euo pipefail

# ── Deploy job-hunting-agent to Hetzner/Coolify server ────────────────────────
#
# Prerequisites:
#   1. You've already run `python3 main.py` locally to generate token.json
#   2. Your SSH config has the alias `coolify-de-falkenstein`
#   3. credentials.json and token.json exist locally in this directory
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh
# ──────────────────────────────────────────────────────────────────────────────

SSH_HOST="coolify-de-falkenstein"
REMOTE_DIR="/opt/job-hunting-agent"
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "═══════════════════════════════════════════════════════"
echo "  Deploying Job Hunting Agent → ${SSH_HOST}:${REMOTE_DIR}"
echo "═══════════════════════════════════════════════════════"

# ── Pre-flight checks ────────────────────────────────────────────────────────
echo ""
echo "▸ Pre-flight checks …"

if [ ! -f "$LOCAL_DIR/credentials.json" ]; then
    echo "  ✗ credentials.json not found in $LOCAL_DIR"
    echo "    → Download it from Google Cloud Console (see README.md)"
    exit 1
fi

if [ ! -f "$LOCAL_DIR/token.json" ]; then
    echo "  ✗ token.json not found in $LOCAL_DIR"
    echo "    → Run 'python3 main.py' locally first to complete OAuth"
    exit 1
fi

if [ ! -f "$LOCAL_DIR/.env" ]; then
    echo "  ✗ .env not found in $LOCAL_DIR"
    echo "    → Copy .env.example to .env and add your GEMINI_API_KEY"
    exit 1
fi

echo "  ✓ credentials.json found"
echo "  ✓ token.json found"
echo "  ✓ .env found"

# ── Create remote directory and install Python ─────────────────────────────
echo ""
echo "▸ Setting up remote environment …"

ssh "$SSH_HOST" bash <<'REMOTE_SETUP'
set -euo pipefail

apt-get update -qq
apt-get install -y -qq python3-venv python3-pip > /dev/null 2>&1 || true

mkdir -p /opt/job-hunting-agent
echo "  ✓ Remote directory ready"
echo "  ✓ Python3 + venv available"
REMOTE_SETUP

# ── Upload project files ──────────────────────────────────────────────────────
echo ""
echo "▸ Uploading project files …"

# Upload Python source + config
scp -q \
    "$LOCAL_DIR/main.py" \
    "$LOCAL_DIR/config.py" \
    "$LOCAL_DIR/gmail_client.py" \
    "$LOCAL_DIR/job_parser.py" \
    "$LOCAL_DIR/web_fetcher.py" \
    "$LOCAL_DIR/llm_evaluator.py" \
    "$LOCAL_DIR/email_composer.py" \
    "$LOCAL_DIR/requirements.txt" \
    "${SSH_HOST}:${REMOTE_DIR}/"

# Upload secrets (these never go in git)
scp -q \
    "$LOCAL_DIR/.env" \
    "$LOCAL_DIR/credentials.json" \
    "$LOCAL_DIR/token.json" \
    "${SSH_HOST}:${REMOTE_DIR}/"

echo "  ✓ All files uploaded"

# ── Install dependencies ──────────────────────────────────────────────────────
echo ""
echo "▸ Installing Python dependencies …"

ssh "$SSH_HOST" bash <<REMOTE_INSTALL
set -euo pipefail
cd ${REMOTE_DIR}

if [ ! -d .venv ]; then
    python3 -m venv .venv
    echo "  ✓ Virtual environment created"
fi

.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
echo "  ✓ Dependencies installed"
REMOTE_INSTALL

# ── Set up cron ───────────────────────────────────────────────────────────────
echo ""
echo "▸ Configuring daily cron job (8:00 AM UTC) …"

ssh "$SSH_HOST" bash <<REMOTE_CRON
set -euo pipefail

CRON_CMD="0 8 * * * cd ${REMOTE_DIR} && ${REMOTE_DIR}/.venv/bin/python main.py >> /var/log/job-agent.log 2>&1"

# Check if cron entry already exists
if crontab -l 2>/dev/null | grep -qF "job-hunting-agent"; then
    # Replace existing entry
    crontab -l 2>/dev/null | grep -vF "job-hunting-agent" | { cat; echo "\$CRON_CMD"; } | crontab -
    echo "  ✓ Cron entry updated"
else
    # Add new entry
    (crontab -l 2>/dev/null; echo "\$CRON_CMD") | crontab -
    echo "  ✓ Cron entry added"
fi

echo "  ✓ Scheduled: daily at 08:00 UTC"
REMOTE_CRON

# ── Verify ────────────────────────────────────────────────────────────────────
echo ""
echo "▸ Verification …"

ssh "$SSH_HOST" bash <<REMOTE_VERIFY
set -euo pipefail
cd ${REMOTE_DIR}

echo "  Files on server:"
ls -la *.py .env credentials.json token.json 2>/dev/null | awk '{print "    " \$NF " (" \$5 " bytes)"}'

echo ""
echo "  Cron schedule:"
crontab -l 2>/dev/null | grep job-hunting | awk '{print "    " \$0}'

echo ""
echo "  Python version:"
.venv/bin/python --version 2>&1 | awk '{print "    " \$0}'
REMOTE_VERIFY

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  ✅ Deployment complete!"
echo ""
echo "  To test now:  ssh ${SSH_HOST} 'cd ${REMOTE_DIR} && .venv/bin/python main.py'"
echo "  View logs:    ssh ${SSH_HOST} 'tail -50 /var/log/job-agent.log'"
echo "  To redeploy:  ./deploy.sh"
echo "═══════════════════════════════════════════════════════"
