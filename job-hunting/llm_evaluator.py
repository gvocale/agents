"""
LLM evaluator — sends job listings to Gemini and parses the structured JSON response.
"""

import json
import logging
import re
import time
from typing import Optional

from google import genai
from google.genai import types

from config import (
    GEMINI_API_KEY,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_SYSTEM_PROMPT,
    LLM_USER_PROMPT_TEMPLATE,
)
from job_parser import JobListing

logger = logging.getLogger(__name__)

# ── JSON schema for structured output ─────────────────────────────────────────
_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "is_match": {"type": "boolean"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "match_reason": {"type": "string"},
        "brief_summary": {"type": "string"},
        "remote_status": {
            "type": "string",
            "enum": ["remote", "hybrid", "onsite", "unclear"],
        },
        "salary_info": {"type": "string"},
        "role_title": {"type": "string"},
        "company_name": {"type": "string"},
        "location": {"type": "string"},
    },
    "required": [
        "is_match",
        "confidence",
        "match_reason",
        "brief_summary",
        "remote_status",
        "salary_info",
        "role_title",
        "company_name",
        "location",
    ],
}


def _build_client() -> genai.Client:
    if not GEMINI_API_KEY:
        raise EnvironmentError(
            "GEMINI_API_KEY environment variable is not set. "
            "Add it to your .env file."
        )
    return genai.Client(api_key=GEMINI_API_KEY)


def _extract_json(text: str) -> Optional[dict]:
    """
    Try to extract a JSON object from the LLM response.
    1. Try parsing the entire text as JSON.
    2. Try extracting from a markdown ```json … ``` block.
    3. Try finding the first {...} in the response.
    """
    # 1. Raw JSON
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 2. Markdown code block
    md_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if md_match:
        try:
            return json.loads(md_match.group(1))
        except json.JSONDecodeError:
            pass

    # 3. First {...} in response
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def evaluate_listing(
    client: genai.Client,
    listing: JobListing,
    retries: int = 1,
) -> Optional[dict]:
    """
    Ask Gemini to evaluate a JobListing. Returns a dict with the evaluation
    fields or None if the call fails or returns unparseable output.
    """
    description = (
        listing.best_description or listing.email_body_text or "No description available."
    )

    user_prompt = LLM_USER_PROMPT_TEMPLATE.format(
        title=listing.title,
        company=listing.company,
        location=listing.location,
        salary=listing.salary,
        description=description,
    )

    for attempt in range(retries + 1):
        try:
            response = client.models.generate_content(
                model=LLM_MODEL,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=LLM_SYSTEM_PROMPT,
                    max_output_tokens=LLM_MAX_TOKENS,
                    temperature=0.3,
                    response_mime_type="application/json",
                    response_json_schema=_RESPONSE_SCHEMA,
                ),
            )
            raw_text = response.text
            logger.debug(
                "LLM raw response for '%s' @ '%s': %s",
                listing.title,
                listing.company,
                raw_text[:200],
            )

            parsed = _extract_json(raw_text)
            if parsed is None:
                logger.warning(
                    "Could not parse JSON from LLM response for '%s' @ '%s'. "
                    "Raw: %s",
                    listing.title,
                    listing.company,
                    raw_text[:500],
                )
                return None

            return parsed

        except Exception as exc:
            error_msg = str(exc).lower()
            # Handle rate limiting
            if "429" in error_msg or "rate" in error_msg or "quota" in error_msg:
                if attempt < retries:
                    wait = 30
                    logger.warning("Rate limit hit; waiting %ds before retry…", wait)
                    time.sleep(wait)
                    continue
                else:
                    logger.error(
                        "Rate limit exceeded for '%s' @ '%s': %s",
                        listing.title,
                        listing.company,
                        exc,
                    )
                    return None

            logger.error(
                "Gemini API error for '%s' @ '%s': %s",
                listing.title,
                listing.company,
                exc,
            )
            return None

    return None


def evaluate_listings(listings: list[JobListing]) -> list[JobListing]:
    """
    Evaluate all listings. Populates `listing.llm_result` and returns those
    where `is_match` is True.
    """
    client = _build_client()
    matches: list[JobListing] = []

    for i, listing in enumerate(listings, 1):
        logger.info(
            "  [%d/%d] Evaluating: %s @ %s …",
            i,
            len(listings),
            listing.title,
            listing.company,
        )
        result = evaluate_listing(client, listing)
        if result is None:
            continue

        listing.llm_result = result

        if result.get("is_match", False):
            matches.append(listing)
            logger.info(
                "    ✅ MATCH  [%s confidence]  %s",
                result.get("confidence", "?"),
                listing.title,
            )
        else:
            logger.info("    ❌ no match — %s", result.get("match_reason", ""))

    return matches


_CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}


def sort_matches(matches: list[JobListing]) -> list[JobListing]:
    """Sort by confidence: high → medium → low."""
    return sorted(
        matches,
        key=lambda j: _CONFIDENCE_ORDER.get(
            j.llm_result.get("confidence", "low"), 3
        ),
    )
