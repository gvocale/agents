"""
Web fetcher — download and parse job posting pages for their description text.
"""

import logging
import re
import time
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from config import FETCH_TIMEOUT_SECONDS, MAX_JOB_DESCRIPTION_CHARS, USER_AGENT

logger = logging.getLogger(__name__)

# ── Selector hints per job board ───────────────────────────────────────────────
_BOARD_SELECTORS: dict[str, list[str]] = {
    "linkedin.com": [
        ".show-more-less-html__markup",
        ".description__text",
        "[class*='description']",
    ],
    "greenhouse.io": [
        "#content",
        ".job-post-description",
        "[class*='job-description']",
    ],
    "lever.co": [
        ".section-wrapper.page-full-width",
        ".posting-description",
        ".content",
    ],
    "ashbyhq.com": [
        "[data-testid='job-description']",
        "[class*='job-description']",
        "main",
    ],
    "workday.com": [
        "[data-automation-id='job-posting-details']",
        "[class*='jobPosting']",
        "section",
    ],
    "smartrecruiters.com": [
        ".job-description",
        "[class*='description']",
    ],
    "bamboohr.com": [
        ".ResDesc",
        "[class*='description']",
    ],
}

_GENERIC_SELECTORS = [
    "[class*='job-description']",
    "[class*='jobDescription']",
    "[class*='description']",
    "[class*='posting-description']",
    "[class*='job-details']",
    "article",
    "main",
]


def _get_selectors(url: str) -> list[str]:
    for domain, selectors in _BOARD_SELECTORS.items():
        if domain in url:
            return selectors + _GENERIC_SELECTORS
    return _GENERIC_SELECTORS


def _clean_text(soup_element) -> str:
    """Return clean text from a BeautifulSoup element."""
    return re.sub(r"\s+", " ", soup_element.get_text(separator=" ")).strip()


def fetch_job_description(url: str) -> Optional[str]:
    """
    Fetch `url` and return the main job description text, truncated to
    MAX_JOB_DESCRIPTION_CHARS. Returns None on any failure.
    """
    if not url:
        return None

    headers = {"User-Agent": USER_AGENT}

    try:
        with httpx.Client(
            timeout=FETCH_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            html = response.text
    except httpx.TimeoutException:
        logger.warning("Timeout fetching %s (>%ds)", url, FETCH_TIMEOUT_SECONDS)
        return None
    except httpx.HTTPStatusError as exc:
        logger.warning("HTTP %s for %s", exc.response.status_code, url)
        return None
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Remove noise
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        tag.decompose()

    selectors = _get_selectors(url)
    for selector in selectors:
        el = soup.select_one(selector)
        if el:
            text = _clean_text(el)
            if len(text) > 100:  # sanity check — not an empty/tiny element
                logger.debug("Extracted description (%d chars) from %s", len(text), url)
                return text[:MAX_JOB_DESCRIPTION_CHARS]

    # Last resort: just grab all body text
    body = soup.find("body")
    if body:
        text = _clean_text(body)
        if len(text) > 100:
            logger.debug(
                "Fallback body extraction (%d chars) from %s", len(text), url
            )
            return text[:MAX_JOB_DESCRIPTION_CHARS]

    logger.warning("Could not extract usable text from %s", url)
    return None


def fetch_descriptions_sequentially(
    urls: list[str], delay_seconds: float = 0.5
) -> dict[str, Optional[str]]:
    """
    Fetch a list of URLs sequentially with a small delay between requests.
    Returns a dict mapping url → description (or None).
    """
    results: dict[str, Optional[str]] = {}
    for i, url in enumerate(urls):
        if url in results:
            continue
        results[url] = fetch_job_description(url)
        if i < len(urls) - 1:
            time.sleep(delay_seconds)
    return results
