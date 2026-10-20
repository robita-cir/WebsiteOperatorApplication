"""Reading a pasted reference into the fields of a publication.

The model only reads. Every value it returns is then checked against the pasted text, and anything the text does not
contain is blanked with a note, so a title, author, venue, DOI, year or link that the model made up never reaches the
form. The operator still checks the form, as for any draft.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from site_agent.llm import ChatClient
from site_agent.prompts import load_prompt
from site_agent.records import SPECS
from site_agent.workflows import ask_json

FIRST_YEAR = 1950
_DOI = re.compile(r"^10\.\d{4,9}/\S+$")
_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)


def _plain(text: str) -> str:
    """The form text is compared in: composed characters, one space between words, no case."""
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _in_paste(value: str, paste: str) -> bool:
    return bool(_plain(value)) and _plain(value) in paste


def _text(value: Any) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""


def publication_types() -> list[str]:
    return [stored for stored, _label in SPECS["publications"].field("type").choices]


def read_reference(llm: ChatClient, text: str, today_year: int) -> tuple[dict[str, Any], list[str]]:
    """Reads a pasted reference. Returns (fields for the form, notes for the operator). Nothing is saved."""
    types = publication_types()
    system = load_prompt("extract_reference", types=", ".join(f'"{t}"' for t in types))
    return check_reference(ask_json(llm, system, text), text, today_year)


def check_reference(raw: dict[str, Any], paste: str, today_year: int) -> tuple[dict[str, Any], list[str]]:
    """Keeps only what the pasted text supports. Blanked values leave a note, except a type, which is a plain choice."""
    haystack = _plain(paste)
    fields: dict[str, Any] = {}
    notes: list[str] = []

    for key, label in (("title", "title"), ("venue", "venue")):
        value = _text(raw.get(key))
        if value and _in_paste(value, haystack):
            fields[key] = value
        else:
            notes.append(f"The text does not state the {label}, so it was left empty.")

    authors = raw.get("authors")
    kept = []
    for author in authors if isinstance(authors, list) else []:
        name = _text(author)
        if not name:
            continue
        if _in_paste(name, haystack):
            kept.append(name)
        else:
            notes.append(f'The text does not state the author "{name}", so that name was left out.')
    if kept:
        fields["authors"] = kept
    elif not any("author" in n for n in notes):
        notes.append("The text does not state the authors, so they were left empty.")

    year = _check_year(raw.get("year"), haystack, today_year)
    if year is None:
        notes.append("The text does not state a usable year, so it was left empty.")
    else:
        fields["year"] = year

    kind = _text(raw.get("type")).casefold()
    if kind in publication_types():
        fields["type"] = kind

    doi_raw = _text(raw.get("doi"))
    if doi_raw:
        doi = _DOI_PREFIX.sub("", doi_raw).strip().rstrip(".,;")
        if _DOI.match(doi) and doi.casefold() in paste.casefold():
            fields["doi"] = doi
        else:
            notes.append("The text does not state that DOI, so it was left empty.")

    url = _text(raw.get("url"))
    if url:
        if url in paste:
            fields["url"] = url
        else:
            notes.append("The text does not state that web link, so it was left empty.")

    return fields, notes


def _check_year(value: Any, haystack: str, today_year: int) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if not isinstance(value, int) or not FIRST_YEAR <= value <= today_year + 1:
        return None
    return value if re.search(rf"(?<!\d){value}(?!\d)", haystack) else None
