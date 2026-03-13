"""
Configuration, constants, and professional profile data for the Job Hunting Agent.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Email ─────────────────────────────────────────────────────────────────────
SENDER_EMAIL = os.getenv("GMAIL_SENDER_EMAIL", "gvocale@gmail.com")
RECIPIENT_EMAIL = "gvocale@gmail.com"
JOB_HUNTING_LABEL = "_Job Hunting"

# ── LLM ───────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LLM_MODEL = "gemini-3.1-flash-lite-preview"
LLM_MAX_TOKENS = 1024

# ── Web fetcher ───────────────────────────────────────────────────────────────
FETCH_TIMEOUT_SECONDS = 10
MAX_JOB_DESCRIPTION_CHARS = 4000
FETCH_CONCURRENCY_LIMIT = 3
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# ── Gmail OAuth scopes ────────────────────────────────────────────────────────
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.labels",
]

# ── Triage keyword lists ──────────────────────────────────────────────────────

# Fast-reject: titles containing any of these (case-insensitive) are skipped
BLOCKLIST_KEYWORDS = [
    "devops",
    "site reliability",
    " sre ",
    "data scientist",
    "machine learning engineer",
    "ml engineer",
    "data engineer",
    "qa engineer",
    "quality assurance",
    "test engineer",
    "sdet",
    "sales engineer",
    "account executive",
    "account manager",
    "pharmaceutical",
    "solar",
    "intern",
    " junior ",
    "jr.",
    "jr ",
    "entry level",
    "entry-level",
    "graduate",
    "network engineer",
    "vlsi",
    "firmware",
    "embedded engineer",
    "embedded systems",
    "scrum master",
    "project manager",
    "program manager",
    "technical recruiter",
    "sales representative",
    "industrial designer",
    "mechanical engineer",
    "electrical engineer",
    "hardware engineer",
    "handbag",
    "apparel",
    "fashion designer",
    "physical product",
    "swift engineer",
    "ios engineer",
    "android engineer",
    "kotlin engineer",
    "database administrator",
    "dba",
    "backend engineer",
    "backend developer",
    "infrastructure engineer",
    "platform engineer",  # only if not design related
    "security engineer",
    "cybersecurity",
    "cloud engineer",
    "charging infrastructure",
    "ev charging",
    "semiconductor",
]

# Fast-track: titles containing any of these are immediately included
ALLOWLIST_KEYWORDS = [
    "design engineer",
    "ux engineer",
    "ui engineer",
    "design systems",
    "creative technologist",
    "design technologist",
    "ui developer",
    "frontend designer",
    "interaction engineer",
    "prototyping engineer",
    "design system",
    "ux/ui",
    "ui/ux",
    "ui engineer",
    "frontend engineer",
    "front-end engineer",
    "front end engineer",
    "product designer",
    "creative engineer",
]

# ── Professional profile (injected into LLM system prompt) ───────────────────
PROFESSIONAL_PROFILE = """
Giovanni Vocale is a UX/UI Design Engineer with 20 years of UI design experience 
and 10 years of frontend engineering experience. He designs directly in code, 
bridging the gap between design and engineering. He works fluently in both Figma 
and React/TypeScript. He builds the things he designs and designs the things he builds.

Location: Based in Brooklyn, NY. Open to remote, hybrid, or NYC-based roles.
Level: Senior / Staff / Lead / Principal. NOT junior or mid-level.

Compatible job titles include: Design Engineer, UX Engineer, UI Engineer, Frontend 
Engineer (with design focus or design systems), Creative Technologist, Design Technologist, 
Product Designer (who codes), UI Developer, Frontend Designer, Design Systems Engineer, 
Interaction Engineer, Prototyping Engineer, and senior/staff/lead/principal variants.

Good fit signals:
- Bridging design and engineering (the #1 signal)
- Design systems work (building, maintaining, scaling component libraries)
- Prototyping in code (actual code prototypes, not just Figma)
- Component library development
- Working in both Figma AND React/TypeScript
- "Design in code" or "code in design" language
- Collaboration between design and engineering teams
- UI architecture and frontend craft
- Creative coding, interactive experiences, motion design in code
- Accessibility-focused frontend work
- Companies that value the design-engineering intersection
- Design tooling (building tools for designers)
- Frontend platform with a design systems angle

Poor fit signals:
- Pure backend engineering
- Pure visual/graphic design with no code
- DevOps / SRE / Infrastructure
- Machine Learning / Data Science
- Mobile-only native development (Swift/Kotlin)
- Junior or entry-level roles
- Completely unrelated domains (solar, pharma, industrial manufacturing, etc.)
- QA / Testing-only roles
- Project management / people management only
- Fashion/industrial/physical product design

Be generous with inclusion. When in doubt, include the job.
"""

LLM_SYSTEM_PROMPT = f"""You are a job-matching assistant. You evaluate job listings against a specific professional profile and determine fit.

{PROFESSIONAL_PROFILE}

Be generous — when in doubt, include the job. It is better to show a borderline match than miss a great opportunity.
"""

LLM_USER_PROMPT_TEMPLATE = """Evaluate this job listing:

Title: {title}
Company: {company}
Location: {location}
Salary: {salary}

Description:
{description}

Respond in this exact JSON format (no markdown, just raw JSON):
{{
  "is_match": true,
  "confidence": "high",
  "match_reason": "One or two sentences explaining why this is or isn't a good fit",
  "brief_summary": "2-3 sentence summary of the role and what makes it interesting or not",
  "remote_status": "remote",
  "salary_info": "extracted salary info or 'Not specified'",
  "role_title": "cleaned up job title",
  "company_name": "company name",
  "location": "location info"
}}

Where:
- is_match: true or false
- confidence: "high", "medium", or "low"
- remote_status: "remote", "hybrid", "onsite", or "unclear"
"""
