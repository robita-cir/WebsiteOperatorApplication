"""Exact replacement of old event details with new ones, done without the model where that is safe.

A date written as "10 March 2026" is swapped for the new date in the same style. A title, venue or series is swapped
for its new value. Replacement happens only on a line that also names the event (the anchor, the old title). A value on
a line without the event's name is not touched, because the same date or venue may belong to something else.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from site_agent.text_utils import date_variants, phrase_pattern

# Fields whose value is replaced on lines that name the event.
MENTION_FIELDS = ("title", "series", "date", "endDate", "venue")
# Values that identify an event by themselves. A venue or series is shared by many events, so it is never searched for
# on its own; it is replaced only on lines that name the event.
IDENTIFYING_FIELDS = ("title", "date", "endDate")


@dataclass(frozen=True)
class Substitution:
    field: str
    old: str
    new: str


def substitutions_for(old_record: dict[str, Any], changes: dict[str, Any]) -> list[Substitution]:
    subs: list[Substitution] = []
    for key in MENTION_FIELDS:
        old_value, new_value = old_record.get(key), changes.get(key)
        if key not in changes or old_value is None or new_value is None:
            continue
        if isinstance(old_value, dt.date):
            subs += [
                Substitution(key, o, n) for o, n in zip(date_variants(old_value), date_variants(new_value), strict=True)
            ]
        else:
            subs.append(Substitution(key, str(old_value), str(new_value)))
    return subs


def search_needles(subs: list[Substitution]) -> list[str]:
    """The old values worth searching the site for: the identifying ones only."""
    return [sub.old for sub in subs if sub.field in IDENTIFYING_FIELDS]


def replace_on_anchor_lines(text: str, subs: list[Substitution], anchor: str | None) -> tuple[str, list[int]]:
    """Applies the substitutions on every line that names the anchor (the event's old title).

    Returns the new text and the 0-based indexes of the lines that changed, so the operator can check them.
    """
    if not anchor:
        return text, []
    named = phrase_pattern(anchor)
    lines = text.split("\n")
    changed: list[int] = []
    for index, line in enumerate(lines):
        if not named.search(line):
            continue
        new_line = line
        for sub in subs:
            new_line = phrase_pattern(sub.old).sub(lambda _match, new=sub.new: new, new_line)
        if new_line != line:
            lines[index] = new_line
            changed.append(index)
    return "\n".join(lines), changed
