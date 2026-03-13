"""
Email composer — builds the HTML summary email body.
"""

from datetime import datetime
from typing import Optional

from job_parser import JobListing


def _remote_label(status: str) -> str:
    mapping = {
        "remote": "Remote",
        "hybrid": "Hybrid",
        "onsite": "Onsite",
    }
    return mapping.get(status, "Unclear")


def _job_card_html(listing: JobListing, job_url: str) -> str:
    result = listing.llm_result
    title = result.get("role_title") or listing.title
    company = result.get("company_name") or listing.company
    location = result.get("location") or listing.location
    salary = result.get("salary_info") or listing.salary or "Not specified"
    remote = _remote_label(result.get("remote_status", "unclear"))
    match_reason = result.get("match_reason", "")
    summary = result.get("brief_summary", "")
    confidence = result.get("confidence", "").upper()

    # Build links line
    links: list[str] = []
    if job_url:
        links.append(
            f'<a href="{job_url}" style="color:#333;text-decoration:underline;">Job posting</a>'
        )
    if listing.gmail_message_id:
        gmail_url = f"https://mail.google.com/mail/u/0/#inbox/{listing.gmail_message_id}"
        links.append(
            f'<a href="{gmail_url}" style="color:#333;text-decoration:underline;">Source email</a>'
        )
    links_html = " · ".join(links)

    return f"""
<tr>
  <td style="padding:16px 0;border-bottom:1px solid #ddd;">
    <div style="font-size:16px;font-weight:600;color:#111;margin-bottom:4px;">
      {title} — {company}
    </div>
    <div style="font-size:13px;color:#666;margin-bottom:8px;">
      {location} | {salary} | {remote} | Confidence: {confidence}
    </div>
    {f'<div style="font-size:13px;margin-bottom:8px;">{links_html}</div>' if links_html else ""}
    <div style="font-size:14px;color:#333;margin-bottom:4px;">
      <strong>Why it fits:</strong> {match_reason}
    </div>
    <div style="font-size:14px;color:#555;">{summary}</div>
  </td>
</tr>
"""


def compose_email(
    matches: list[JobListing],
    total_emails_scanned: int,
    total_listings_found: int,
    total_passed_triage: int,
) -> tuple[str, str]:
    """
    Returns (subject, html_body) for the summary email.
    """
    today = datetime.now().strftime("%B %d, %Y")
    subject = f"Job Opportunities — {today}"
    n = len(matches)

    cards = "".join(
        _job_card_html(listing, listing.url) for listing in matches
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{subject}</title>
</head>
<body style="margin:0;padding:0;background:#fff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#111;">
<div style="max-width:640px;margin:24px auto;padding:0 16px;">

  <h1 style="font-size:22px;font-weight:700;margin:0 0 4px;">Job Opportunities</h1>
  <p style="font-size:14px;color:#666;margin:0 0 24px;">{today} — {n} potential match{"es" if n != 1 else ""}</p>

  <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
    {cards}
  </table>

  <p style="font-size:12px;color:#999;margin-top:24px;padding-top:12px;border-top:1px solid #eee;">
    {total_emails_scanned} emails scanned,
    {total_listings_found} listings found,
    {total_passed_triage} passed triage,
    {n} matched.
  </p>

</div>
</body>
</html>"""

    return subject, html

