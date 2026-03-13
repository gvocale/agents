"""
Gmail API client — authentication, reading emails, and sending the summary.
"""

import base64
import logging
import os
import time
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import GMAIL_SCOPES, JOB_HUNTING_LABEL

logger = logging.getLogger(__name__)

CREDENTIALS_FILE = Path(__file__).parent / "credentials.json"
TOKEN_FILE = Path(__file__).parent / "token.json"


def _load_credentials_from_env() -> bool:
    """
    If credentials.json / token.json are stored as base64 env vars
    (for containerised deployments), decode and write them to disk.
    Returns True if env-based credentials were written.
    """
    creds_b64 = os.getenv("GMAIL_CREDENTIALS_JSON")
    token_b64 = os.getenv("GMAIL_TOKEN_JSON")
    wrote_something = False
    if creds_b64 and not CREDENTIALS_FILE.exists():
        CREDENTIALS_FILE.write_bytes(base64.b64decode(creds_b64))
        logger.info("Decoded GMAIL_CREDENTIALS_JSON from env → credentials.json")
        wrote_something = True
    if token_b64 and not TOKEN_FILE.exists():
        TOKEN_FILE.write_bytes(base64.b64decode(token_b64))
        logger.info("Decoded GMAIL_TOKEN_JSON from env → token.json")
        wrote_something = True
    return wrote_something


def authenticate() -> Any:
    """
    Authenticate with Gmail via OAuth2 and return a Gmail API service object.
    On the very first run this opens a browser for the OAuth consent flow.
    """
    _load_credentials_from_env()

    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            "credentials.json not found. Please follow the Gmail API setup "
            "instructions in README.md to create OAuth2 credentials."
        )

    creds: Credentials | None = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("OAuth2 token refreshed successfully.")
            except Exception as exc:
                logger.error(
                    "Failed to refresh OAuth2 token: %s. "
                    "Delete token.json and re-run to trigger a new OAuth flow.",
                    exc,
                )
                raise SystemExit(1) from exc
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), GMAIL_SCOPES
            )
            creds = flow.run_local_server(port=0)
            logger.info("OAuth2 consent flow completed.")

        TOKEN_FILE.write_text(creds.to_json())
        logger.info("Token saved to token.json.")

    service = build("gmail", "v1", credentials=creds)
    logger.info("Gmail API service created.")
    return service


def get_label_ids(service: Any, label_prefix: str) -> list[tuple[str, str]]:
    """
    Return (label_id, label_name) for the label matching `label_prefix`
    AND all its child labels (e.g. "_Job Hunting" matches
    "_Job Hunting", "_Job Hunting/2025 after Arena", etc.).
    """
    try:
        result = service.users().labels().list(userId="me").execute()
    except HttpError as exc:
        logger.error("Failed to list Gmail labels: %s", exc)
        raise

    labels = result.get("labels", [])
    prefix_lower = label_prefix.lower()
    matches = []
    for label in labels:
        name = label.get("name", "")
        name_lower = name.lower()
        # Match exact name or any child (name starts with prefix + "/")
        if name_lower == prefix_lower or name_lower.startswith(prefix_lower + "/"):
            matches.append((label["id"], name))

    if not matches:
        available = sorted(lbl["name"] for lbl in labels)
        raise ValueError(
            f"No labels matching '{label_prefix}' found in Gmail. "
            f"Available labels: {available}"
        )

    return matches


def fetch_emails_since(
    service: Any,
    label_ids: list[tuple[str, str]],
    since_timestamp: int,
) -> list[dict]:
    """
    Fetch all emails across multiple label IDs that arrived after
    `since_timestamp` (Unix epoch seconds). Deduplicates by message ID.
    Returns a list of full message dicts.
    """
    query = f"after:{since_timestamp}"
    seen_ids: set[str] = set()
    messages: list[dict] = []

    for label_id, label_name in label_ids:
        page_token: str | None = None
        label_count = 0

        while True:
            kwargs: dict = {
                "userId": "me",
                "labelIds": [label_id],
                "q": query,
            }
            if page_token:
                kwargs["pageToken"] = page_token

            try:
                result = service.users().messages().list(**kwargs).execute()
            except HttpError as exc:
                logger.error("Failed to list messages for label '%s': %s", label_name, exc)
                raise

            batch = result.get("messages", [])
            if not batch:
                break

            for msg_stub in batch:
                msg_id = msg_stub["id"]
                if msg_id in seen_ids:
                    continue
                seen_ids.add(msg_id)

                try:
                    full_msg = (
                        service.users()
                        .messages()
                        .get(userId="me", id=msg_id, format="full")
                        .execute()
                    )
                    messages.append(full_msg)
                    label_count += 1
                except HttpError as exc:
                    logger.warning("Could not fetch message %s: %s", msg_id, exc)

            page_token = result.get("nextPageToken")
            if not page_token:
                break

        if label_count:
            logger.info("  Found %d email(s) in '%s'", label_count, label_name)

    logger.info("Fetched %d total emails across %d label(s).", len(messages), len(label_ids))
    return messages


def send_email(service: Any, to: str, subject: str, html_body: str) -> None:
    """Send an HTML email via the Gmail API."""
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = "me"
    message["To"] = to
    message.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    try:
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        logger.info("Summary email sent to %s.", to)
    except HttpError as exc:
        logger.error("Failed to send summary email: %s", exc)
        raise
