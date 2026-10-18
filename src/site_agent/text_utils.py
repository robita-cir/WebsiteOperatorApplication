"""Text helpers: slugs, the ways a date is written, and finding lines that mention something."""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from collections.abc import Iterable, Mapping
from typing import Any

MIN_NEEDLE = 3  # shorter search text matches too much to be useful


def slugify(text: str, max_len: int = 60) -> str:
    """'Workshop on Robot Learning!' becomes 'workshop-on-robot-learning'."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug[:max_len].strip("-")


def normalise(text: str) -> str:
    """Lower case with runs of whitespace collapsed, for comparing text loosely."""
    return " ".join(text.casefold().split())


def date_variants(day: dt.date) -> list[str]:
    """The common ways one date is written, so a search finds it whichever style a page uses."""
    return [
        day.isoformat(),
        f"{day.day} {day:%B} {day.year}",
        f"{day:%B} {day.day}, {day.year}",
        f"{day.day} {day:%b} {day.year}",
        f"{day:%b} {day.day}, {day.year}",
    ]


def phrase_pattern(phrase: str) -> re.Pattern[str]:
    """Matches the words of `phrase` in order, ignoring case and spacing, and never inside a longer word.

    So "Event 1" matches "Event 1" and "event  1," but not "Event 10".
    """
    words = [re.escape(word) for word in phrase.split()]
    return re.compile(r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)", re.IGNORECASE)


def matching_lines(text: str, needles: Iterable[str]) -> list[int]:
    """0-based indexes of the lines that contain any needle as a whole phrase."""
    patterns = [phrase_pattern(n) for n in needles if len(n.strip()) >= MIN_NEEDLE]
    if not patterns:
        return []
    return [i for i, line in enumerate(text.split("\n")) if any(p.search(line) for p in patterns)]


def excerpt_lines(lines: list[str], hits: list[int], radius: int, max_lines: int = 250) -> str:
    """The whole file if it is short. Otherwise only the lines near each hit, with '[...]' where lines were left out."""
    if len(lines) <= max_lines:
        return "\n".join(lines)
    keep: set[int] = set()
    for index in hits:
        keep.update(range(max(0, index - radius), min(len(lines), index + radius + 1)))
    out: list[str] = []
    previous = -2
    for index in sorted(keep):
        if index != previous + 1:
            out.append("[...]")
        out.append(lines[index])
        previous = index
    return "\n".join(out)


def ungrounded_fields(fields: Mapping[str, Any], source: str) -> list[str]:
    """Warnings for dates, places and series names that do not appear in the operator's text.

    Small models sometimes invent a venue or work out a date from "next Monday". The operator still reviews the
    preview, so these are warnings, not errors.
    """
    haystack = normalise(source)
    warnings = []
    for key in ("date", "endDate"):
        value = fields.get(key)
        if isinstance(value, dt.date) and not any(normalise(v) in haystack for v in date_variants(value)):
            warnings.append(f"{key} {value.isoformat()} is not written in the text you gave. Check it.")
    for key in ("venue", "series"):
        value = fields.get(key)
        if value and normalise(str(value)) not in haystack:
            warnings.append(f'{key} "{value}" is not written in the text you gave. Check it.')
    return warnings
