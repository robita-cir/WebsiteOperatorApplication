import datetime as dt

import pytest

from site_agent.dates import resolve_relative_date
from site_agent.text_utils import quote_in_text

TUESDAY = dt.date(2026, 10, 20)


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("today", dt.date(2026, 10, 20)),
        ("Tomorrow", dt.date(2026, 10, 21)),
        ("tuesday", dt.date(2026, 10, 20)),  # a bare weekday counts today
        ("this Tuesday", dt.date(2026, 10, 20)),
        ("next Tuesday", dt.date(2026, 10, 27)),  # strictly after today
        ("monday", dt.date(2026, 10, 26)),
        ("This  Monday", dt.date(2026, 10, 26)),
        ("next Monday", dt.date(2026, 10, 26)),
        ("NEXT FRIDAY", dt.date(2026, 10, 23)),
        ("next sunday.", dt.date(2026, 10, 25)),
    ],
)
def test_supported_phrases(phrase, expected):
    assert resolve_relative_date(phrase, TUESDAY) == expected


@pytest.mark.parametrize(
    "phrase",
    ["", "the Monday after next", "in two weeks", "next month", "last Friday", "next", "Monday 5 November", "soon"],
)
def test_unsupported_phrases_return_none(phrase):
    assert resolve_relative_date(phrase, TUESDAY) is None


def test_a_quote_is_found_ignoring_case_spacing_and_look_alike_characters():
    notice = "Join us on  5 November 2026\nin Lab 3."
    assert quote_in_text("5 november 2026", notice)
    assert quote_in_text("November 2026 in lab 3", notice)
    assert quote_in_text("５ November", notice)  # a full-width digit normalises to a plain one


@pytest.mark.parametrize("quote", ["", "   ", "6 November 2026", "Lab 4"])
def test_a_quote_that_is_empty_or_absent_is_not_found(quote):
    assert not quote_in_text(quote, "Join us on 5 November 2026 in Lab 3.")
