"""The list search: every word of the query must appear somewhere in the entry, in any order.

Case and accents are ignored, so "jose" finds "José". The fields searched are the ones an operator would use to
recognise an entry; they follow the field names in records.py.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from site_agent.records import Spec

# Fields searched in each collection. A collection that is not listed falls back to its title field only.
SEARCH_FIELDS: dict[str, tuple[str, ...]] = {
    "people": ("name", "role", "dept", "interests"),
    "projects": ("title", "area", "students"),
    "publications": ("title", "authors", "venue"),
    "events": ("title", "venue", "series"),
    "openings": ("title", "type"),
    "partners": ("name", "country"),
    "funding": ("title", "funder", "partner"),
    "facilities": ("name", "kind"),
    "documents": ("title", "kind"),
    "gallery": ("title", "period"),
    "research": ("code", "title"),
    "news": ("title",),
}


def fold(text: str) -> str:
    """Lower case without accents: 'Café' and 'cafe' compare equal."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()


def matches(query: str, values: list[str]) -> bool:
    """True when every word of the query appears in at least one of the values. An empty query matches all."""
    words = fold(query).split()
    if not words:
        return True
    haystack = fold(" ".join(values))
    return all(word in haystack for word in words)


def search_values(spec: Spec, record_values: dict[str, Any]) -> list[str]:
    """The texts of one record that the search looks at, including the labels of choices (so 'PhD' finds 'phd')."""
    names = SEARCH_FIELDS.get(spec.key, (spec.title_field,))
    texts: list[str] = []
    for name in names:
        value = record_values.get(name)
        if value is None or value == "":
            continue
        try:
            choices = spec.field(name).choices
        except KeyError:
            choices = ()
        for item in value if isinstance(value, list) else [value]:
            text = str(item)
            texts.append(text)
            texts.extend(label for stored, label in choices if stored == text)
    return texts
