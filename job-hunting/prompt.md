# Claude Code Prompt: Build a Job-Hunting Agent

## Project Overview

Build a standalone, independently deployable Python application that acts as a personal job-hunting agent. This agent runs on a schedule (cron), reads job-related emails from Gmail, evaluates each opportunity against a specific professional profile using an LLM (Claude API), and sends a curated daily summary email with the best matches.

This is a fully self-contained project — no frameworks, no agent platforms, no LangChain. Just Python, the Gmail API, the Anthropic API, and a few utility libraries.

---

## Goal

Every day, the agent should:

1. Connect to Gmail and read all emails with the label `_job-hunting` from the last 24 hours
2. Triage job listings by title and metadata (fast rejection of obvious mismatches)
3. For promising listings, fetch the full job post URL and extract the description
4. Use Claude to evaluate each job against the professional profile below
5. Compile the best matches into a well-formatted summary email
6. Send that email via Gmail to the user
7. Run silently and exit cleanly if there are no matches — no empty emails

---

## Professional Profile: Giovanni Vocale

**Title:** UX/UI Design Engineer

**Summary:** Giovanni is a hybrid designer-engineer with **20 years of UI design experience** and **10 years of frontend engineering experience**. He doesn't hand off designs to developers — he designs directly in code. He bridges the gap between design and engineering, working fluently in both Figma and React/TypeScript. He builds the things he designs and designs the things he builds.

**Location:** Based in Brooklyn, NY. Open to remote, hybrid, or NYC-based roles.

**Level:** Senior / Staff / Lead / Principal. NOT junior or mid-level.

### Compatible Job Titles

The agent should consider these titles as potentially good fits (and close variations):

- Design Engineer
- UX Engineer
- UI Engineer
- Frontend Engineer (with design focus or design systems focus)
- Creative Technologist
- Design Technologist
- Product Designer (who codes / with engineering responsibilities)
- UI Developer
- Frontend Designer
- Design Systems Engineer
- Interaction Engineer
- Prototyping Engineer
- Staff/Senior/Lead/Principal variants of all the above

### Signals of a GOOD Fit

Look for these signals in job titles, descriptions, and requirements:

- Bridging design and engineering (the #1 signal)
- Design systems work (building, maintaining, scaling component libraries)
- Prototyping in code (not just Figma prototypes — actual code prototypes)
- Component library development
- Working in Figma AND React/TypeScript
- "Design in code" or "code in design" language
- Collaboration between design and engineering teams (as someone who lives in both worlds)
- UI architecture and frontend craft
- Creative coding, interactive experiences, motion design in code
- Accessibility-focused frontend work
- Companies that value the design-engineering intersection
- Startups or product companies where wearing multiple hats is valued
- Design tooling (building tools for designers)
- Frontend platform or frontend infrastructure with a design systems angle

### Signals of a POOR Fit (Reject These)

Reject jobs that are clearly:

- Pure backend engineering (Node.js APIs, databases, microservices — unless there's a clear frontend/design component)
- Pure visual/graphic design (print, branding, illustration — no code)
- DevOps / SRE / Infrastructure
- Machine Learning / Data Science / AI Engineering (unless it's about AI-powered design tools)
- Mobile-only native development (Swift/Kotlin) — React Native is okay
- Junior or entry-level roles (anything saying 0-2 years, "graduate", "intern", "junior")
- Domains completely unrelated to design/frontend: solar energy infrastructure, pharmaceutical compliance, industrial manufacturing, charging infrastructure, network engineering, VLSI, etc.
- Roles that require 80%+ backend work
- QA / Testing-only roles
- Project management / Scrum master / pure people management roles
- Fashion/industrial/physical product design roles (e.g., "Technical Designer - Handbags")

### Important Evaluation Rules

- **Be generous with inclusion.** When in doubt, include the job. It's better to show a borderline match than to miss a great opportunity. Giovanni can decide for himself.
- **Watch for misleading titles.** A "Frontend Engineer" role might actually be 90% backend API work. A "Product Designer" role might require zero coding. A "Design Engineer" might be pure Figma with no code. Read the actual description.
- **Title isn't everything.** A job titled "Software Engineer" at a design tools company might be an amazing fit. Look at the full picture.
- **Salary matters for context, not filtering.** Include salary info when available but don't filter by salary.
- **Remote matters.** Flag whether the role is remote, hybrid, or onsite.

---

## Complete Workflow

### Step 1: Read Emails from Gmail

- Authenticate with Gmail API using OAuth2 (credentials.json + token.json)
- Query for emails with the label `_job-hunting` received in the last 24 hours
- Extract from each email:
  - Subject line
  - Sender
  - Plain text and/or HTML body
  - Any URLs in the body (especially links to job postings)
- Handle pagination if there are many emails

### Step 2: Triage by Title and Metadata (Fast Pass)

Before making any LLM calls or fetching URLs, do a quick triage:

- Extract individual job listings from each email (LinkedIn alert emails often contain 3-6 listings each)
- If the job title is an obvious mismatch (e.g., "Senior DevOps Engineer", "Junior QA Analyst", "Solar Engineering Lead", "VLSI Consultant", "Technical Designer - Handbags"), skip it immediately
- This is a heuristic/keyword-based filter to save API calls
- When in doubt, let it through to the LLM evaluation step
- Use a simple keyword blocklist for fast rejection (e.g., "devops", "SRE", "data scientist", "machine learning engineer", "QA engineer", "sales", "pharmaceutical", "solar", "intern", "junior", "network engineer", "VLSI", "firmware", "embedded")
- And a positive keyword list for fast-track inclusion (e.g., "design engineer", "UX engineer", "design systems", "creative technologist", "UI engineer", "frontend designer")
- **Deduplicate** — the same job may appear in multiple alert emails. Track unique jobs by job title + company name.

### Step 3: Fetch Job Post URLs

For listings that pass the triage step:

- Extract the primary job posting URL from the email body (LinkedIn URLs, Greenhouse, Lever, Ashby, Workday, company career pages, etc.)
- Fetch the page content using httpx
- Parse the HTML with BeautifulSoup to extract the main job description text
- For LinkedIn pages specifically, look for the job description in elements with class names containing "description" or "show-more-less-html"
- Handle failures gracefully (404, timeout, bot protection) — if you can't fetch the URL, still evaluate based on the email content alone
- Set reasonable timeouts (10 seconds) and a User-Agent header
- Rate limit yourself — don't blast 50 requests in parallel. Process sequentially or with a small concurrency limit (3-5)
- Truncate very long descriptions to ~4000 characters to avoid wasting tokens

### Step 4: Evaluate with LLM (Claude API)

For each candidate job, send the following to Claude via the Anthropic API:

- The professional profile (as system context)
- The job title, company, and description (from email + fetched URL content)
- Ask Claude to evaluate the fit and return a structured response

**LLM System Prompt:**

```
You are a job-matching assistant. You evaluate job listings against a specific professional profile and determine fit.

The candidate is Giovanni Vocale, a UX/UI Design Engineer with 20 years of UI design experience and 10 years of frontend engineering experience. He designs directly in code, bridging design and engineering. He works in Figma, React, and TypeScript. He is senior/staff level.

Good fits: roles that bridge design and engineering, design systems, prototyping in code, component libraries, creative technology, frontend with design focus.

Poor fits: pure backend, pure visual design with no code, DevOps, ML, junior roles, unrelated domains.

Be generous — when in doubt, include the job.
```

**LLM User Message:**

```
Evaluate this job listing:

Title: {title}
Company: {company}
Location: {location}
Salary: {salary if available, otherwise "Not specified"}

Description:
{description text}

Respond in this exact JSON format:
{
  "is_match": true/false,
  "confidence": "high" | "medium" | "low",
  "match_reason": "One or two sentences explaining why this is or isn't a good fit",
  "brief_summary": "2-3 sentence summary of the role and what makes it interesting or not",
  "remote_status": "remote" | "hybrid" | "onsite" | "unclear",
  "salary_info": "extracted salary info or 'Not specified'",
  "role_title": "cleaned up job title",
  "company_name": "company name",
  "location": "location info"
}
```

- Use `claude-sonnet-4-20250514` as the model
- Set max_tokens to 1024
- Parse the JSON response from Claude. If parsing fails, try extracting JSON from markdown code blocks. If that also fails, log the error and skip the listing.
- Include jobs where `is_match` is `true` regardless of confidence level

### Step 5: Compile Results

- Collect all matched jobs
- Sort by confidence: high → medium → low
- Deduplicate by job title + company
- If zero matches, exit silently — do NOT send an empty email

### Step 6: Send Summary Email via Gmail

Send an email to `gvocale@gmail.com` via the Gmail API.

**Subject:** `🎯 Job Opportunities — {Month DD, YYYY}`

**Body (HTML):**

```html
<h2>🎯 Job Opportunities — {Month DD, YYYY}</h2>
<p>Found {N} potential matches from today's job alerts.</p>
<hr />

<!-- Repeat for each job: -->
<h3>{Job Title} — {Company}</h3>
<p>
  📍 {Location} &nbsp; | &nbsp; 💰 {Salary or "Not specified"} &nbsp; | &nbsp;
  🏠 {Remote/Hybrid/Onsite}<br />
  🔗 <a href="{url}">View Job Posting</a>
</p>
<p><strong>Why it's a fit:</strong> {match_reason}</p>
<p>{brief_summary}</p>
<hr />

<!-- End repeat -->

<p style="color: #888; font-size: 12px;">
  This email was generated by your Job Opportunity Scout. {total_emails_scanned}
  emails scanned, {total_listings_found} listings found, {total_passed_triage}
  passed triage, {N} matched.
</p>
```

---

## Technical Architecture

### Project Structure

```
job-hunting-agent/
├── main.py                  # Entry point — run this via cron
├── gmail_client.py          # Gmail API authentication and operations
├── job_parser.py            # Email parsing, URL extraction, triage logic
├── web_fetcher.py           # Fetch and parse job posting URLs
├── llm_evaluator.py         # Claude API integration for job evaluation
├── email_composer.py        # Compose the summary email HTML
├── config.py                # Configuration, constants, profile data
├── requirements.txt         # Python dependencies
├── Dockerfile               # For containerized deployment
├── .env.example             # Example environment variables
├── credentials.json         # Gmail OAuth credentials (not in git)
├── token.json               # Gmail OAuth token (generated on first run, not in git)
├── .gitignore
└── README.md                # Setup and deployment instructions
```

### Dependencies (requirements.txt)

```
google-auth>=2.0.0
google-auth-oauthlib>=1.0.0
google-auth-httplib2>=0.2.0
google-api-python-client>=2.0.0
anthropic>=0.39.0
httpx>=0.27.0
beautifulsoup4>=4.12.0
python-dotenv>=1.0.0
```

### Environment Variables (.env.example)

```
ANTHROPIC_API_KEY=sk-ant-...
GMAIL_SENDER_EMAIL=gvocale@gmail.com
LOG_LEVEL=INFO

# Optional: for containerized deployment where files aren't available
# Base64-encode your credentials.json and token.json content
# GMAIL_CREDENTIALS_JSON=base64-encoded-content
# GMAIL_TOKEN_JSON=base64-encoded-content
```

### Gmail API Setup

The project needs to use the Gmail API with OAuth2 for a personal Google account.

**Setup instructions to include in README.md:**

1. Go to https://console.cloud.google.com/
2. Create a new project (or use existing)
3. Enable the Gmail API
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client IDs"
5. Application type: "Desktop app"
6. Download the credentials JSON file and save it as `credentials.json` in the project root
7. On first run, the app will open a browser for OAuth consent. After authorizing, it saves `token.json` for subsequent runs.
8. Required Gmail API scopes:
   - `https://www.googleapis.com/auth/gmail.readonly` (read emails)
   - `https://www.googleapis.com/auth/gmail.send` (send summary email)
   - `https://www.googleapis.com/auth/gmail.labels` (read labels)

**Token refresh handling:** The OAuth token expires. The code should handle automatic token refresh using the refresh token stored in token.json. If the refresh token is also expired, log a clear error message telling the user to re-run the auth flow.

### Gmail Client Implementation Notes

- Use `googleapiclient.discovery.build('gmail', 'v1', credentials=creds)` to create the service
- To find the label ID for `_job-hunting`: call `service.users().labels().list(userId='me')` and find the label by name
- To query emails: `service.users().messages().list(userId='me', labelIds=[label_id], q=f'after:{timestamp}')` where timestamp is 24 hours ago as a Unix timestamp
- To get email content: `service.users().messages().get(userId='me', id=msg_id, format='full')`
- Parse email parts for text/plain and text/html content
- To send email: construct a MIME message and use `service.users().messages().send(userId='me', body={'raw': base64_encoded_message})`

### Web Fetcher Implementation Notes

- Use httpx with a 10-second timeout
- Set a realistic User-Agent header (e.g., `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36`)
- Parse HTML with BeautifulSoup
- For LinkedIn job pages, look for content in elements with class containing "show-more-less-html" or "description"
- For common job boards (Greenhouse, Lever, Ashby), try to extract the main content area (often in a `<div>` with class containing "job-description", "posting-description", "content", etc.)
- Strip all HTML tags and return clean text
- Truncate very long descriptions to ~4000 characters to avoid wasting tokens
- If fetching fails, return None and let the evaluator work with email content only

### LLM Evaluator Implementation Notes

- Use the `anthropic` Python SDK
- `client = anthropic.Anthropic()` (reads ANTHROPIC_API_KEY from env)
- Use `client.messages.create(model="claude-sonnet-4-20250514", ...)`
- Parse the JSON response from Claude. Use a try/except around JSON parsing.
- If Claude returns a non-JSON response, try to extract JSON from markdown code blocks (regex for `json...`)
- If that also fails, log and skip

### main.py Entry Point

```python
"""
Job Hunting Agent — Main Entry Point
Run this script on a schedule (cron, Railway, etc.) to get daily job match emails.
"""

# The main function should:
# 1. Load environment variables from .env
# 2. Configure logging
# 3. Authenticate with Gmail
# 4. Fetch emails from last 24 hours with _job-hunting label
# 5. Parse emails to extract individual job listings
# 6. Triage jobs by title (keyword-based fast filter)
# 7. Deduplicate by title + company
# 8. Fetch URLs for promising jobs
# 9. Evaluate each with Claude
# 10. Compile matches
# 11. Send email (if matches > 0)
# 12. Log summary to stdout
```

It should handle all errors gracefully and never crash silently. Use the `logging` module, not print statements. Log: total emails found, listings extracted, passed triage, URLs fetched, matches found, email sent status.

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

### .gitignore

```
credentials.json
token.json
.env
__pycache__/
*.pyc
.venv/
```

---

## Deployment Options

Include instructions in README.md for all of these:

### Option 1: Local Cron Job

```bash
# Run every day at 8:00 AM
0 8 * * * cd /path/to/job-hunting-agent && /path/to/python main.py >> /var/log/job-agent.log 2>&1
```

### Option 2: Docker

```bash
docker build -t job-hunting-agent .
docker run --env-file .env job-hunting-agent
```

For scheduled Docker runs, use the host's cron to trigger the container.

### Option 3: Railway / Render / Fly.io

- Use the Dockerfile for deployment
- Set environment variables in the platform's dashboard
- For Gmail credentials in containerized environments: store credentials.json and token.json content as base64-encoded environment variables. The app should detect this and decode them at startup.
- Use the platform's cron job or scheduled task feature

---

## Error Handling Requirements

- **Gmail auth failure:** Log clearly, suggest re-running OAuth flow. Exit with code 1.
- **Label not found:** Log that `_job-hunting` label doesn't exist. Exit with code 1.
- **No emails found:** Log "No emails with \_job-hunting label in last 24 hours." Exit with code 0.
- **URL fetch failure:** Log the URL and error. Continue with email content only.
- **Claude API failure:** Log the error. If it's a rate limit, wait and retry once. If persistent, skip that job.
- **Claude returns bad JSON:** Log the raw response. Skip that job.
- **Gmail send failure:** Log the error. Exit with code 1.
- **No matches after evaluation:** Log "No matches found today." Exit with code 0. Do NOT send email.
- All errors should be logged with enough context to debug (email subject, URL, error message).

---

## What to Build

Build the complete project. Every file. Working code. README with full setup and deployment instructions. The whole thing.

Do NOT use placeholder code or `# TODO` comments. Every function should be fully implemented and working.

Do NOT ask me questions. Make reasonable decisions and document any assumptions in the README.

Test the code mentally for common edge cases: empty emails, malformed HTML, missing fields, API errors, duplicate listings across emails, LinkedIn emails with multiple job listings, etc.

The end result should be a project I can clone, add my credentials, and run immediately.
