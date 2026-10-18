import datetime as dt

import pytest
from pydantic import ValidationError

from site_agent.frontmatter import parse_document
from site_agent.schemas import Event, describe_errors

VALID = {"title": "Talk", "kind": "talk", "date": dt.date(2026, 5, 6)}


def test_template_style_event_is_accepted():
    event = Event.model_validate(
        parse_document('---\ntitle: "Event 1"\nkind: "talk"\ndate: 2020-09-06\nvenue: "Venue name, City"\n---\n').data
    )
    assert event.kind == "talk"
    assert event.date == dt.date(2020, 9, 6)


def test_end_date_before_date_is_rejected():
    with pytest.raises(ValidationError) as info:
        Event.model_validate({**VALID, "endDate": dt.date(2026, 5, 1)})
    assert "endDate (2026-05-01) must not be earlier than date (2026-05-06)" in describe_errors(info.value)[0]


def test_unknown_kind_is_rejected_and_named():
    with pytest.raises(ValidationError) as info:
        Event.model_validate({**VALID, "kind": "seminar"})
    assert describe_errors(info.value)[0].startswith("kind:")


def test_frontmatter_keeps_template_key_order_and_omits_empty_values():
    event = Event.model_validate({**VALID, "endDate": dt.date(2026, 5, 7), "series": None})
    assert list(event.to_frontmatter()) == ["title", "kind", "date", "endDate"]
    assert "sample" not in event.to_frontmatter()
