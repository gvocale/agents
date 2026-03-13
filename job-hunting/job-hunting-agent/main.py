"""
Job Hunting Agent — Main Entry Point

Run this script on a schedule (cron, Railway, etc.) to get daily job match emails.

Usage:
    python main.py

Exit codes:
    0 — ran successfully (emails may or may not have been sent)
    1 — fatal error (auth failure, send failure, misconfiguration)
"""

import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

# Load .env before importing anything that reads env vars
load_dotenv()

from config import JOB_HUNTING_LABEL, RECIPIENT_EMAIL
from email_composer import compose_email
from gmail_client import authenticate, fetch_emails_since, get_label_ids, send_email
from job_parser import JobListing, deduplicate, parse_email, triage_title
from llm_evaluator import evaluate_listings, sort_matches
from web_fetcher import fetch_descriptions_sequentially


def _configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    _configure_logging()
    logger = logging.getLogger(__name__)

    logger.info("═══════════════════════════════════════════════════════════")
    logger.info("  Job Hunting Agent — %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
    logger.info("═══════════════════════════════════════════════════════════")

    # ── Step 1: Authenticate with Gmail ───────────────────────────────────────
    logger.info("Step 1/6: Authenticating with Gmail …")
    try:
        service = authenticate()
    except (FileNotFoundError, SystemExit) as exc:
        logger.error("Gmail authentication failed: %s", exc)
        sys.exit(1)

    # ── Resolve labels (parent + all children) ────────────────────────────────
    try:
        label_ids = get_label_ids(service, JOB_HUNTING_LABEL)
        label_names = [name for _, name in label_ids]
        logger.info(
            "Watching %d label(s): %s", len(label_ids), ", ".join(label_names)
        )
    except ValueError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    # ── Step 2: Fetch emails from last 24 hours ────────────────────────────────
    since_ts = int((datetime.now(timezone.utc) - timedelta(hours=24)).timestamp())
    logger.info(
        "Step 2/6: Fetching emails since %s …",
        datetime.fromtimestamp(since_ts).strftime("%Y-%m-%d %H:%M"),
    )
    try:
        messages = fetch_emails_since(service, label_ids, since_ts)
    except Exception as exc:
        logger.error("Failed to fetch emails: %s", exc)
        sys.exit(1)

    total_emails_scanned = len(messages)

    if not messages:
        logger.info(
            "No emails with '%s' label in the last 24 hours. Exiting.",
            JOB_HUNTING_LABEL,
        )
        sys.exit(0)

    logger.info("Found %d email(s).", total_emails_scanned)

    # ── Step 3: Parse + triage ─────────────────────────────────────────────────
    logger.info("Step 3/6: Parsing emails and triaging job listings …")
    all_listings: list[JobListing] = []
    for msg in messages:
        all_listings.extend(parse_email(msg))

    total_listings_found = len(all_listings)
    logger.info("Extracted %d total listing(s).", total_listings_found)

    # Deduplicate
    all_listings = deduplicate(all_listings)
    logger.info("After dedup: %d unique listing(s).", len(all_listings))

    # Triage
    candidate_listings: list[JobListing] = []
    for listing in all_listings:
        verdict = triage_title(listing.title)
        if verdict == "block":
            logger.info("  BLOCKED  (fast-reject): %s @ %s", listing.title, listing.company)
        else:
            flag = "ALLOWED (fast-track)" if verdict == "allow" else "UNCERTAIN"
            logger.info("  %s: %s @ %s", flag, listing.title, listing.company)
            candidate_listings.append(listing)

    total_passed_triage = len(candidate_listings)

    if not candidate_listings:
        logger.info("No listings passed triage. Exiting cleanly.")
        sys.exit(0)

    logger.info("%d listing(s) passed triage.", total_passed_triage)

    # ── Step 4: Fetch job post URLs ────────────────────────────────────────────
    logger.info("Step 4/6: Fetching job posting pages …")
    urls_to_fetch = [l.url for l in candidate_listings if l.url]
    unique_urls = list(dict.fromkeys(urls_to_fetch))

    if unique_urls:
        logger.info("Fetching %d URL(s) …", len(unique_urls))
        descriptions = fetch_descriptions_sequentially(unique_urls)
        for listing in candidate_listings:
            if listing.url and listing.url in descriptions:
                desc = descriptions[listing.url]
                if desc:
                    listing.fetched_description = desc
    else:
        logger.info("No URLs to fetch — will evaluate from email content only.")

    # ── Step 5: Evaluate with Gemini ──────────────────────────────────────────
    logger.info("Step 5/6: Evaluating %d listing(s) with Gemini …", len(candidate_listings))
    try:
        matches = evaluate_listings(candidate_listings)
    except EnvironmentError as exc:
        logger.error("LLM setup error: %s", exc)
        sys.exit(1)

    if not matches:
        logger.info("No matches found today. Exiting cleanly — no email sent.")
        sys.exit(0)

    matches = sort_matches(matches)
    # Final dedup (in case LLM results revealed duplicates)
    matches = deduplicate(matches)

    logger.info(
        "Found %d match(es): %s",
        len(matches),
        ", ".join(f"{m.title} @ {m.company}" for m in matches),
    )

    # ── Step 6: Send summary email ─────────────────────────────────────────────
    logger.info("Step 6/6: Composing and sending summary email …")
    subject, html_body = compose_email(
        matches,
        total_emails_scanned=total_emails_scanned,
        total_listings_found=total_listings_found,
        total_passed_triage=total_passed_triage,
    )

    try:
        send_email(service, RECIPIENT_EMAIL, subject, html_body)
    except Exception as exc:
        logger.error("Failed to send summary email: %s", exc)
        sys.exit(1)

    logger.info("═══════════════════════════════════════════════════════════")
    logger.info(
        "  Done.  %d emails scanned → %d listings → %d passed triage → %d matched",
        total_emails_scanned,
        total_listings_found,
        total_passed_triage,
        len(matches),
    )
    logger.info("═══════════════════════════════════════════════════════════")


if __name__ == "__main__":
    main()
