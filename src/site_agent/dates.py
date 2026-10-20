"""Turning a few relative dates into calendar dates, so the model never has to count days.

Only phrases whose meaning is not in doubt are supported. Anything else returns None and the date must then be
written in the notice itself.
"""

from __future__ import annotations

import datetime as dt

_WEEKDAYS = {
    name: index
    for index, name in enumerate(("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"))
}


def resolve_relative_date(phrase: str, today: dt.date) -> dt.date | None:
    """'today', 'tomorrow', 'this friday' or 'friday' (today counts), 'next friday' (strictly after today)."""
    words = phrase.casefold().strip(" \t\n.,;:!").split()
    if words == ["today"]:
        return today
    if words == ["tomorrow"]:
        return today + dt.timedelta(days=1)
    if len(words) == 1 and words[0] in _WEEKDAYS:
        return _weekday_on_or_after(today, _WEEKDAYS[words[0]])
    if len(words) == 2 and words[1] in _WEEKDAYS:
        if words[0] == "this":
            return _weekday_on_or_after(today, _WEEKDAYS[words[1]])
        if words[0] == "next":
            return _weekday_on_or_after(today + dt.timedelta(days=1), _WEEKDAYS[words[1]])
    return None


def _weekday_on_or_after(start: dt.date, weekday: int) -> dt.date:
    return start + dt.timedelta(days=(weekday - start.weekday()) % 7)
