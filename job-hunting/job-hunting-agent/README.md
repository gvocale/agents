# Job Hunting Agent

A personal job-hunting agent that runs on a daily schedule, reads job alert emails from Gmail, evaluates each opportunity against your professional profile using Gemini, and sends a curated summary email with the best matches.

---

## How It Works

1. **Reads Gmail** — fetches all emails labelled `_job-hunting` from the last 24 hours
2. **Triages** — fast keyword-based filter rejects obvious mismatches (DevOps, junior, QA, etc.)
3. **Fetches job pages** — downloads the actual job posting for richer context
4. **Evaluates with Gemini** — uses `gemini-3.1-flash-lite` to assess fit against Giovanni's profile (~$0.01/day)
5. **Sends a summary email** — a beautiful HTML digest of the best matches, sorted by confidence
6. **Exits silently** — no email sent if there are zero matches

---

## Project Structure

```
job-hunting-agent/
├── main.py            # Entry point — run via cron
├── gmail_client.py    # Gmail API auth + read/send
├── job_parser.py      # Email parsing, URL extraction, triage, dedup
├── web_fetcher.py     # Download and parse job posting pages
├── llm_evaluator.py   # Gemini API evaluation
├── email_composer.py  # HTML summary email
├── config.py          # Constants, profile, keyword lists
├── requirements.txt
├── Dockerfile
├── .env.example
└── .gitignore
```

---

## Setup

### 1. Python environment

```bash
cd job-hunting-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Gmail API credentials

1. Go to [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Enable the **Gmail API**
4. Go to **Credentials → Create Credentials → OAuth 2.0 Client IDs**
5. Application type: **Desktop app**
6. Download the JSON file and save it as `credentials.json` in the project root
7. Run the agent once to complete the browser-based OAuth consent flow:
   ```bash
   python main.py
   ```
   After authorising, `token.json` is saved automatically and used for all future runs without a browser.

**Required scopes** (requested automatically):
- `https://www.googleapis.com/auth/gmail.readonly`
- `https://www.googleapis.com/auth/gmail.send`
- `https://www.googleapis.com/auth/gmail.labels`

### 3. Gmail label

Create a label called `_job-hunting` in Gmail and apply it (manually or with a filter) to job alert emails from LinkedIn, Indeed, Greenhouse, etc.

### 4. Environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
GEMINI_API_KEY=...
GMAIL_SENDER_EMAIL=gvocale@gmail.com
LOG_LEVEL=INFO
```

---

## Running

### Manual run

```bash
source .venv/bin/activate
python main.py
```

### Local cron job (runs every day at 8:00 AM)

```bash
crontab -e
```

Add:

```cron
0 8 * * * cd /path/to/job-hunting-agent && /path/to/.venv/bin/python main.py >> /var/log/job-agent.log 2>&1
```

Replace `/path/to/` with actual paths. To find Python:

```bash
which python  # inside the venv
```

### Docker

```bash
docker build -t job-hunting-agent .
docker run --env-file .env \
  -v "$(pwd)/credentials.json:/app/credentials.json" \
  -v "$(pwd)/token.json:/app/token.json" \
  job-hunting-agent
```

For scheduled Docker runs, use the host cron to trigger the container.

---

## Containerised Deployment (Railway, Fly.io, Render)

Since these platforms don't have a local filesystem for `credentials.json` / `token.json`, encode them as base64 environment variables:

```bash
# Run these locally after completing the OAuth flow
base64 -i credentials.json | tr -d '\n'   # → paste as GMAIL_CREDENTIALS_JSON
base64 -i token.json | tr -d '\n'         # → paste as GMAIL_TOKEN_JSON
```

Set these in your platform's dashboard (alongside `GEMINI_API_KEY`). The agent will decode and write the files at startup automatically.

**Scheduling on Railway:** Use the Railway cron service or a [Cron Service](https://docs.railway.app/guides/cron).

**Scheduling on Fly.io:** Use `fly deploy` with a `[processes]` section or a companion cron machine.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success (may or may not have sent an email) |
| `1` | Fatal error (auth failure, Gmail send failure, misconfiguration) |

---

## Configuration

All tunable constants are in `config.py`:

| Constant | Default | Purpose |
|----------|---------|---------|
| `LLM_MODEL` | `gemini-3.1-flash-lite` | Gemini model |
| `LLM_MAX_TOKENS` | `1024` | Max response tokens |
| `FETCH_TIMEOUT_SECONDS` | `10` | Web fetch timeout |
| `MAX_JOB_DESCRIPTION_CHARS` | `4000` | Truncation limit for job descriptions |
| `BLOCKLIST_KEYWORDS` | (see config.py) | Fast-reject job title keywords |
| `ALLOWLIST_KEYWORDS` | (see config.py) | Fast-track job title keywords |

---

## Assumptions & Design Decisions

- **LinkedIn multi-listing emails**: The parser attempts two heuristic strategies (`·` separator and `at` separator) to extract multiple listings from a single alert email. If both fail, the whole email is treated as one listing using the subject line as the title.
- **URL assignment**: If a listing doesn't have an explicit URL, the first job-board-looking URL found in the email body (Greenhouse, LinkedIn, Lever, etc.) is used.
- **Token refresh**: The OAuth refresh token is long-lived. If it expires (rare), delete `token.json` and run `python main.py` again to re-authorise.
- **Rate limiting**: Web fetches are sequential with a 0.5s delay. Gemini calls have a built-in rate-limit retry with a 30s backoff.
- **No email on zero matches**: The agent exits cleanly (code 0) without sending anything if there are no matches. Silence is success.
