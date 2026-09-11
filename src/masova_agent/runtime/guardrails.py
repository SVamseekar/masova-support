"""Input/output screening: PII redaction and prompt-injection heuristics.

Fail-open: callers should catch exceptions and pass the message through
unmodified while logging a warning (see spec §10).
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}\b")
_PHONE_RE = re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")

_INJECTION_PATTERNS = [
    re.compile(r"ignore (all )?previous instructions", re.I),
    re.compile(r"reveal (your |the )?system prompt", re.I),
    re.compile(r"disregard (your )?(prior|earlier) rules", re.I),
]

_LEAK_FRAGMENTS = [
    "You are MaSoVa_Support",
    "system prompt:",
]


def luhn_valid(digits: str) -> bool:
    cleaned = re.sub(r"[ -]", "", digits)
    if not cleaned.isdigit() or not (13 <= len(cleaned) <= 19):
        return False
    total = 0
    reverse = cleaned[::-1]
    for i, ch in enumerate(reverse):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def redact_pii(text: str) -> str:
    def _card_sub(match: re.Match) -> str:
        candidate = match.group(0)
        return "[REDACTED_CARD]" if luhn_valid(candidate) else candidate

    text = _CARD_RE.sub(_card_sub, text)
    text = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = _PHONE_RE.sub("[REDACTED_PHONE]", text)
    return text


def screen_input(text: str) -> tuple[str, bool]:
    try:
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(text):
                return text, True
        return redact_pii(text), False
    except Exception:
        logger.warning("guardrails.screen_input failed; passing text through", exc_info=True)
        return text, False


def screen_output(text: str) -> str:
    try:
        for fragment in _LEAK_FRAGMENTS:
            if fragment in text:
                text = text.replace(fragment, "[REDACTED]")
        return redact_pii(text)
    except Exception:
        logger.warning("guardrails.screen_output failed; passing text through", exc_info=True)
        return text
