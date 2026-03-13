"""
Email parsing — extract job listings from Gmail messages, triage by title,
deduplicate, and extract URLs.
"""

import base64
import logging
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

from config import ALLOWLIST_KEYWORDS, BLOCKLIST_KEYWORDS

logger = logging.getLogger(__name__)


# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class JobListing:
    title: str
    company: str
    location: str = "Not specified"
    salary: str = "Not specified"
    url: str = ""
    email_body_text: str = ""
    gmail_message_id: str = ""  # For linking back to the source email
    # Populated after web fetch + LLM eval
    fetched_description: str = ""
    llm_result: dict = field(default_factory=dict)

    @property
    def dedup_key(self) -> str:
        return f"{self.title.lower().strip()}|{self.company.lower().strip()}"

    @property
    def best_description(self) -> str:
        """Return whichever description is longer / more informative."""
        if len(self.fetched_description) > len(self.email_body_text):
            return self.fetched_description
        return self.email_body_text


# ── HTML → plain text ──────────────────────────────────────────────────────────

class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts)


def _strip_html(html: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html)
    return re.sub(r"\s+", " ", stripper.get_text()).strip()


# ── Email part extraction ──────────────────────────────────────────────────────

def _decode_part(part: dict) -> str:
    """Decode a Gmail message part body."""
    data = part.get("body", {}).get("data", "")
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    except Exception:
        return ""


def extract_email_body(message: dict) -> tuple[str, str]:
    """
    Walk the MIME tree of a Gmail message and return (plain_text, html_text).
    """
    plain_parts: list[str] = []
    html_parts: list[str] = []

    def _walk(parts: list[dict]) -> None:
        for part in parts:
            mime = part.get("mimeType", "")
            sub_parts = part.get("parts", [])
            if sub_parts:
                _walk(sub_parts)
            elif mime == "text/plain":
                plain_parts.append(_decode_part(part))
            elif mime == "text/html":
                html_parts.append(_decode_part(part))

    payload = message.get("payload", {})
    if payload.get("parts"):
        _walk(payload["parts"])
    else:
        # Single-part message
        mime = payload.get("mimeType", "")
        body = _decode_part(payload)
        if mime == "text/html":
            html_parts.append(body)
        else:
            plain_parts.append(body)

    plain = "\n".join(plain_parts)
    html = "\n".join(html_parts)
    return plain, html


def extract_urls(text: str) -> list[str]:
    """Extract all http/https URLs from a block of text."""
    pattern = r"https?://[^\s\"'<>\]\)]+(?<![.,;!?])"
    return list(dict.fromkeys(re.findall(pattern, text)))  # deduplicated, order kept


# ── LinkedIn alert email parsing ───────────────────────────────────────────────

# Patterns to extract listings from LinkedIn job-alert emails
_LI_JOB_BLOCK_RE = re.compile(
    r"(?P<title>[^\n]+?)\s+at\s+(?P<company>[^\n]+?)\n"
    r"(?P<location>[^\n]+?)\n",
    re.MULTILINE,
)


def _parse_linkedin_jobs(plain: str, html: str) -> list[JobListing]:
    """
    Attempt to extract multiple listings from a LinkedIn job-alert email.
    Returns a list of JobListing objects (may be empty).
    """
    source = plain if plain else _strip_html(html)
    listings: list[JobListing] = []

    # Strategy: look for lines like "<Title> · <Company>" or "<Title> at <Company>"
    # followed by location lines and job links.

    # Pattern 1: "Title · Company\nLocation"
    pattern1 = re.compile(
        r"^(.+?)\s+·\s+(.+?)\s*\n(.+?)(?:\n|$)",
        re.MULTILINE,
    )
    for m in pattern1.finditer(source):
        title, company, location = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        if len(title) < 3 or len(company) < 2:
            continue
        listings.append(JobListing(title=title, company=company, location=location))

    if listings:
        return listings

    # Pattern 2: fallback — look for "X at Y" pairs
    for m in _LI_JOB_BLOCK_RE.finditer(source):
        title = m.group("title").strip()
        company = m.group("company").strip()
        location = m.group("location").strip()
        if len(title) < 3:
            continue
        listings.append(JobListing(title=title, company=company, location=location))

    return listings


# ── Triage ─────────────────────────────────────────────────────────────────────

def _is_allowlisted(title: str) -> bool:
    lower = title.lower()
    return any(kw in lower for kw in ALLOWLIST_KEYWORDS)


def _is_blocklisted(title: str) -> bool:
    lower = f" {title.lower()} "
    return any(kw in lower for kw in BLOCKLIST_KEYWORDS)


def triage_title(title: str) -> str:
    """
    Returns 'allow', 'block', or 'uncertain'.
    'allow'     → fast-track, definitely worth evaluating
    'block'     → obvious mismatch, skip
    'uncertain' → let the LLM decide
    """
    if _is_allowlisted(title):
        return "allow"
    if _is_blocklisted(title):
        return "block"
    return "uncertain"


# ── Main parsing entry point ───────────────────────────────────────────────────

def parse_email(message: dict) -> list[JobListing]:
    """
    Given a full Gmail message dict, return a list of JobListings extracted from it.
    """
    msg_id = message.get("id", "")
    payload = message.get("payload", {})
    headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
    subject = headers.get("Subject", "")
    sender = headers.get("From", "")

    plain, html = extract_email_body(message)
    combined_text = plain or _strip_html(html)

    # Try to extract multiple listings (LinkedIn-style alert emails)
    listings = _parse_linkedin_jobs(plain, html)

    if not listings:
        # Treat the whole email as one listing, using subject as title
        title = subject
        # Try to infer company from sender
        company_match = re.search(r"from\s+(.+?)(?:\s+via|\s*$)", sender, re.IGNORECASE)
        company = company_match.group(1).strip() if company_match else sender.split("<")[0].strip()
        listings = [JobListing(title=title, company=company, email_body_text=combined_text)]

    # Attach body text, message ID, and extract URLs for all listings
    all_urls = extract_urls(combined_text)
    for listing in listings:
        listing.gmail_message_id = msg_id
        if not listing.email_body_text:
            listing.email_body_text = combined_text
        # Assign a URL if none set — pick the first job-board-looking URL
        if not listing.url and all_urls:
            for url in all_urls:
                if any(
                    board in url
                    for board in [
                        "linkedin.com/jobs",
                        "greenhouse.io",
                        "lever.co",
                        "ashbyhq.com",
                        "workday.com",
                        "jobs.",
                        "/jobs/",
                        "/careers/",
                        "smartrecruiters",
                        "bamboohr",
                    ]
                ):
                    listing.url = url
                    break
            if not listing.url:
                listing.url = all_urls[0]

    logger.debug(
        "Parsed email '%s': found %d listing(s).", subject, len(listings)
    )
    return listings


def deduplicate(listings: list[JobListing]) -> list[JobListing]:
    """Remove duplicate listings by title + company, keeping the first seen."""
    seen: set[str] = set()
    unique: list[JobListing] = []
    for listing in listings:
        key = listing.dedup_key
        if key not in seen:
            seen.add(key)
            unique.append(listing)
    return unique
