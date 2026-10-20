"""The fact check for written text.

Years, numbers, web addresses and emails in a draft, or in any long text the operator types, must appear in the
operator's facts. Anything else is listed, and saving is blocked while it stays in the text. Long text is never a
source of facts itself: a summary cannot vouch for the numbers it contains.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Mapping
from typing import Any

from site_agent.records import Spec
from site_agent.text_utils import date_variants

_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_NUMBER = re.compile(r"\b\d+(?:[.,]\d+)?\b")
_URL = re.compile(r"https?://[^\s)]+|\b[\w-]+(?:\.[\w-]+)*\.(?:org|com|edu|net|in|uk|ac\.in|ac\.uk)\b", re.IGNORECASE)
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")


def token_in_facts(token: str, facts: str) -> bool:
    """True when the token appears in the facts as a whole item, so '10' is not found inside '2010'."""
    pattern = r"(?<![\w.])" + re.escape(token.casefold()) + r"(?![\w])"
    return re.search(pattern, facts.casefold()) is not None


def unsupported_tokens(text: str, facts: str) -> list[str]:
    """Years, numbers, web addresses and emails in `text` that the facts do not give."""
    found: list[str] = []
    for pattern in (_EMAIL, _URL, _YEAR, _NUMBER):
        for match in pattern.finditer(text):
            token = match.group(0).rstrip(".,;:")
            # A domain inside an address, or a year inside a web address, is reported once, as part of the address.
            inside_found = any(token in other for other in found)
            if token and not inside_found and not token_in_facts(token, facts):
                found.append(token)
    return found


def facts_text(spec: Spec, values: Mapping[str, Any], extra: str) -> str:
    """The facts the model may use: the short fields filled in, plus the facts the operator typed."""
    lines = []
    for f in spec.fields:
        if f.kind == "long":
            continue
        value = values.get(f.name)
        if value in (None, "", []) or isinstance(value, bool):
            continue
        if isinstance(value, dt.date):
            shown = "; ".join(date_variants(value))  # so "5 November 2026" in a draft is supported by the date field
        else:
            shown = ", ".join(value) if isinstance(value, list) else str(value)
        lines.append(f"{f.label}: {shown}")
    lines += [line.strip() for line in extra.splitlines() if line.strip()]
    return "\n".join(lines)


def fact_problems(
    spec: Spec,
    values: Mapping[str, Any],
    body: str,
    facts: str,
    previous: Mapping[str, Any] | None = None,
    previous_body: str = "",
) -> list[str]:
    """What the new text mentions that the facts do not give. Only text that changed is checked.

    `previous` holds the saved values of a record being edited. Text that was already there and is unchanged is left
    alone, so an old record is not blocked by the rule for new text.
    """
    previous = previous or {}
    facts_now = facts_text(spec, values, facts)
    texts: list[tuple[str, str]] = []
    if body and body != previous_body:
        texts.append((spec.body_label or "text", body))
    for f in spec.fields:
        if f.kind != "long":
            continue
        value = str(values.get(f.name) or "")
        if value and value != str(previous.get(f.name) or ""):
            texts.append((f.label, value))
    problems = []
    for label, text in texts:
        for token in unsupported_tokens(text, facts_now):
            problems.append(
                f'The {label.lower()} mentions "{token}", which is not in your facts. '
                "Remove it from the text, or add it to the facts."
            )
    return problems
