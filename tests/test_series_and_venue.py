"""A series the notice names but the record lacks, and a venue or series longer than the words it was copied from."""

import datetime as dt
import json
from pathlib import Path

import pytest
from helpers import FakeLLM

from site_agent.config import SiteSettings
from site_agent.drafting import extract_notice
from site_agent.site import Site
from site_agent.workflows import ground_notice, plan_add_event

CASES = Path(__file__).parent / "regression"
PROGRAMME = (CASES / "notices" / "programme_with_series.txt").read_text(encoding="utf-8")
TALK = (CASES / "notices" / "venue_two_ways.txt").read_text(encoding="utf-8")
TODAY = dt.date(2026, 6, 1)
SERIES_NOTE = (
    "The notice seems to name a series ('Example Robotics Summer Series') but the series field is empty. Check it."
)


def programme_reply(**overrides) -> str:
    record = {
        "title": "Summer Programme on Mobile Robot Navigation",
        "kind": "programme",
        "series": None,
        "date": "2026-07-15",
        "endDate": "2026-07-26",
        "venue": "Training Hall, Example City",
        "summary": None,
        "body": "",
        "date_phrase": None,
        "sources": {
            "date": "15 July 2026",
            "endDate": "26 July 2026",
            "venue": "Training Hall, Example City",
            "series": None,
        },
    }
    record.update(overrides)
    return json.dumps(record)


def talk_reply(venue: str, venue_quote: str | None = "Lab 3, Example City") -> str:
    return json.dumps(
        {
            "title": "Learning to Walk in Simulation",
            "kind": "talk",
            "series": None,
            "date": "2026-08-20",
            "endDate": None,
            "venue": venue,
            "summary": None,
            "body": "",
            "date_phrase": None,
            "sources": {"date": "20 August 2026", "venue": venue_quote},
        }
    )


@pytest.fixture
def site(site_dir):
    return Site(SiteSettings(root=site_dir))


# a series the notice names and the record leaves out


def test_a_named_series_with_an_empty_series_field_is_a_note_on_the_command_line(site):
    plan = plan_add_event(site, FakeLLM(programme_reply()), PROGRAMME, today=TODAY)
    assert plan.failures == []
    assert SERIES_NOTE in plan.notes


def test_the_same_note_reaches_the_web_form(site):
    result = extract_notice(FakeLLM(programme_reply()), PROGRAMME, TODAY)
    assert SERIES_NOTE in result.notes
    assert "series" not in result.fields


def test_no_note_when_the_record_has_the_series(site):
    series = "Example Robotics Summer Series"
    sources = {
        "date": "15 July 2026",
        "endDate": "26 July 2026",
        "venue": "Training Hall, Example City",
        "series": series,
    }
    plan = plan_add_event(site, FakeLLM(programme_reply(series=series, sources=sources)), PROGRAMME, today=TODAY)
    assert not any("seems to name a series" in note for note in plan.notes)
    assert plan.notes == []


def test_no_note_when_the_notice_names_no_series(site):
    plan = plan_add_event(site, FakeLLM(talk_reply("Lab 3, Example City")), TALK, today=TODAY)
    assert not any("seems to name a series" in note for note in plan.notes)


def test_a_blank_series_counts_as_empty():
    reading = ground_notice(json.loads(programme_reply(series="  ")), PROGRAMME, TODAY)
    assert SERIES_NOTE in reading.notes


def test_a_course_that_is_the_event_itself_is_not_called_a_series():
    notice = "Introduction to Robotics Course starts on 5 November 2026."
    raw = {"title": "Introduction to Robotics Course", "kind": "workshop", "date": "2026-11-05"}
    raw["sources"] = {"date": "5 November 2026"}
    assert not any("seems to name a series" in note for note in ground_notice(raw, notice, TODAY).notes)


def test_a_missing_series_is_only_a_note_never_a_blocker():
    reading = ground_notice(json.loads(programme_reply()), PROGRAMME, TODAY)
    assert reading.blockers == []


# a venue longer than its quote


def test_a_venue_with_an_extra_sentence_is_cut_back_to_its_quote(site):
    long_venue = "Lab 3, Example City. This is the same room that the campus map lists as Block B, Room 12."
    plan = plan_add_event(site, FakeLLM(talk_reply(long_venue)), TALK, today=TODAY)
    assert plan.failures == []
    assert 'venue: "Lab 3, Example City"' in plan.changes[0].after
    assert "campus map" not in plan.changes[0].after
    assert "The venue was shortened to the words the notice uses: 'Lab 3, Example City'." in plan.notes


def test_the_web_form_gets_the_shortened_venue_and_the_note():
    long_venue = "Lab 3, Example City. This is the same room that the campus map lists as Block B, Room 12."
    result = extract_notice(FakeLLM(talk_reply(long_venue)), TALK, TODAY)
    assert result.fields["venue"] == "Lab 3, Example City"
    assert "The venue was shortened to the words the notice uses: 'Lab 3, Example City'." in result.notes


def test_a_venue_that_is_part_of_its_quote_needs_no_note(site):
    plan = plan_add_event(site, FakeLLM(talk_reply("Lab 3")), TALK, today=TODAY)
    assert 'venue: "Lab 3"' in plan.changes[0].after
    assert not any("venue" in note.lower() for note in plan.notes)


def test_a_venue_that_does_not_match_its_quote_is_kept_with_a_note(site):
    plan = plan_add_event(site, FakeLLM(talk_reply("Block B, Room 12")), TALK, today=TODAY)
    assert 'venue: "Block B, Room 12"' in plan.changes[0].after
    assert "The venue does not match the words the notice uses ('Lab 3, Example City'). Check it." in plan.notes


def test_a_venue_with_no_quote_keeps_the_existing_note(site):
    plan = plan_add_event(site, FakeLLM(talk_reply("Lab 3, Example City", venue_quote=None)), TALK, today=TODAY)
    assert 'venue "Lab 3, Example City": the notice does not give this in its own words. Check it.' in plan.notes


# a series longer than its quote

SERIES_NOTICE = "Robot Talk 7 is part of the Autumn Lecture Series, held on 5 November 2026."


def series_reply(series: str) -> str:
    return json.dumps(
        {
            "title": "Robot Talk 7",
            "kind": "talk",
            "series": series,
            "date": "2026-11-05",
            "sources": {"date": "5 November 2026", "series": "Autumn Lecture Series"},
        }
    )


def test_a_series_longer_than_its_quote_is_cut_back_to_it(site):
    plan = plan_add_event(
        site, FakeLLM(series_reply("Autumn Lecture Series, held every year")), SERIES_NOTICE, today=TODAY
    )
    assert 'series: "Autumn Lecture Series"' in plan.changes[0].after
    assert "The series was shortened to the words the notice uses: 'Autumn Lecture Series'." in plan.notes


def test_a_series_that_does_not_match_its_quote_is_kept_with_a_note(site):
    plan = plan_add_event(site, FakeLLM(series_reply("Spring Lecture Series")), SERIES_NOTICE, today=TODAY)
    assert 'series: "Spring Lecture Series"' in plan.changes[0].after
    assert "The series does not match the words the notice uses ('Autumn Lecture Series'). Check it." in plan.notes
