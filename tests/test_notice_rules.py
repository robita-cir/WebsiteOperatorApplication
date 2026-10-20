"""The checks on a model's reading of a notice: retry on an invalid record, input size, quotes, relative dates."""

import datetime as dt
import json

import pytest
from helpers import FakeLLM

from site_agent.cli import main
from site_agent.config import SiteSettings
from site_agent.drafting import extract_from_notice, extract_notice
from site_agent.errors import SiteAgentError
from site_agent.site import Site
from site_agent.workflows import EVENT_SCHEMA, UPDATE_EVENT_SCHEMA, ask_json, plan_add_event, plan_update_event

TODAY = dt.date(2026, 10, 20)  # a Tuesday
NOTICE = "Hands-on Perception Day on 5 November 2026 in Lab 3, Example City. Open to all students."


def reply(**overrides) -> str:
    record = {
        "title": "Hands-on Perception Day",
        "kind": "workshop",
        "series": None,
        "date": "2026-11-05",
        "endDate": None,
        "venue": "Lab 3, Example City",
        "summary": "A day of perception demos.",
        "body": "Open to all students.",
        "date_phrase": None,
        "sources": {"date": "5 November 2026", "endDate": None, "venue": "Lab 3, Example City", "series": None},
    }
    record.update(overrides)
    return json.dumps(record)


class RecordingLLM(FakeLLM):
    """FakeLLM. The base class already keeps the schema each call was given, in `schemas`."""


@pytest.fixture
def site(site_dir):
    return Site(SiteSettings(root=site_dir))


# validation retry, input budget, schema


def test_a_record_that_fails_the_check_is_sent_back_once_with_the_reason(site):
    llm = RecordingLLM(reply(date="soon"), reply())
    plan = plan_add_event(site, llm, NOTICE, today=TODAY)

    assert len(llm.calls) == 2
    retry = llm.calls[1][0]
    assert [m.role for m in retry] == ["system", "user", "assistant", "user"]
    assert retry[-1].content.startswith("That record is not valid: ")
    assert "date:" in retry[-1].content
    assert retry[-1].content.endswith("Reply with the corrected JSON object only.")
    assert plan.failures == []


def test_a_record_that_is_still_invalid_after_the_retry_is_an_error(site):
    llm = FakeLLM(reply(date="soon"), reply(date="later"))
    with pytest.raises(SiteAgentError, match="date:"):
        plan_add_event(site, llm, NOTICE, today=TODAY)
    assert len(llm.calls) == 2


def test_the_schema_is_given_to_the_model_for_both_workflows(site):
    add_llm = RecordingLLM(reply())
    plan_add_event(site, add_llm, NOTICE, today=TODAY)
    assert add_llm.schemas == [EVENT_SCHEMA]
    assert EVENT_SCHEMA["required"] == ["title", "kind", "date"]
    assert EVENT_SCHEMA["properties"]["kind"]["enum"] == ["workshop", "programme", "talk"]
    assert EVENT_SCHEMA["properties"]["date"]["pattern"] == r"^\d{4}-\d{2}-\d{2}$"

    update_llm = RecordingLLM('{"summary": "Now with a poster session."}')
    plan_update_event(site, update_llm, "event-1", "Add a poster session.", today=TODAY)
    assert update_llm.schemas == [UPDATE_EVENT_SCHEMA]
    assert "required" not in UPDATE_EVENT_SCHEMA


def test_the_update_check_runs_on_the_merged_record(site):
    llm = FakeLLM('{"endDate": "2026-01-01"}', '{"endDate": "2026-04-16"}')
    plan_update_event(site, llm, "event-1", "It now ends on 16 April 2026.", today=TODAY)
    assert len(llm.calls) == 2
    assert "endDate" in llm.calls[1][0][-1].content and "earlier than date" in llm.calls[1][0][-1].content


def test_a_notice_over_the_word_limit_is_refused_before_the_model_is_asked():
    llm = FakeLLM()
    long_notice = "word " * 1501
    with pytest.raises(SiteAgentError) as caught:
        ask_json(llm, "system", long_notice)
    assert str(caught.value) == (
        "The notice is 1,501 words long. The helper reads up to 1,500 words at a time. "
        "Paste the part with the event details."
    )
    assert llm.calls == []
    ask_json(FakeLLM("{}"), "system", "word " * 1500)  # exactly at the limit is allowed


# quote grounding


def test_a_date_whose_quote_is_missing_is_a_failure(site):
    plan = plan_add_event(site, FakeLLM(reply(sources={"venue": "Lab 3, Example City"})), NOTICE, today=TODAY)
    assert plan.failures == [
        "date: the notice does not state this date in its own words. Check the notice, or edit the event file by hand."
    ]


def test_a_date_quote_that_is_not_in_the_notice_is_a_failure(site):
    plan = plan_add_event(site, FakeLLM(reply(sources={"date": "on 6 November"})), NOTICE, today=TODAY)
    assert any(failure.startswith("date:") for failure in plan.failures)


def test_an_end_date_without_its_own_quote_is_a_failure(site):
    plan = plan_add_event(site, FakeLLM(reply(endDate="2026-11-06")), NOTICE, today=TODAY)
    assert [f.split(":")[0] for f in plan.failures] == ["endDate"]


def test_an_end_date_with_a_quote_in_the_notice_is_accepted(site):
    notice = "Perception Day, 5 November 2026 to 6 November 2026, in Lab 3, Example City."
    sources = {"date": "5 November 2026", "endDate": "6 November 2026", "venue": "Lab 3, Example City"}
    plan = plan_add_event(site, FakeLLM(reply(endDate="2026-11-06", sources=sources)), notice, today=TODAY)
    assert plan.failures == []
    assert "endDate: 2026-11-06" in plan.changes[0].after


def test_the_cli_refuses_to_write_an_event_with_an_unquoted_date(site_dir, tmp_path, capsys):
    notice = tmp_path / "notice.txt"
    notice.write_text(NOTICE, encoding="utf-8")
    before = sorted(p.name for p in (site_dir / "src/content/events").iterdir())
    code = main(
        ["add-event", "--site", str(site_dir), "--from", str(notice), "--apply", "--yes"],
        client=FakeLLM(reply(sources={})),
    )
    assert code == 1
    assert "date: the notice does not state this date in its own words" in capsys.readouterr().out
    assert sorted(p.name for p in (site_dir / "src/content/events").iterdir()) == before


def test_a_venue_without_a_quote_is_a_note_not_a_failure(site):
    sources = {"date": "5 November 2026", "venue": None}
    plan = plan_add_event(site, FakeLLM(reply(sources=sources)), NOTICE, today=TODAY)
    assert plan.failures == []
    assert 'venue "Lab 3, Example City": the notice does not give this in its own words. Check it.' in plan.notes


def test_a_series_with_a_quote_not_in_the_notice_is_a_note(site):
    sources = {"date": "5 November 2026", "venue": "Lab 3, Example City", "series": "Vision Series"}
    plan = plan_add_event(site, FakeLLM(reply(series="Vision Series", sources=sources)), NOTICE, today=TODAY)
    assert plan.failures == []
    assert any(note.startswith('series "Vision Series": the notice does not give this') for note in plan.notes)


def test_sources_and_date_phrase_never_reach_the_file(site):
    plan = plan_add_event(site, FakeLLM(reply()), NOTICE, today=TODAY)
    assert "sources" not in plan.changes[0].after
    assert "date_phrase" not in plan.changes[0].after


# relative dates


def test_a_relative_date_is_worked_out_by_the_tool_and_a_wrong_model_date_is_noted(site):
    notice = "Perception Day next Monday in Lab 3, Example City."
    wrong = reply(date="2026-10-25", date_phrase="next Monday", sources={"venue": "Lab 3, Example City"})
    plan = plan_add_event(site, FakeLLM(wrong), notice, today=TODAY)

    assert plan.failures == []
    assert "date: 2026-10-26" in plan.changes[0].after
    assert (
        "The notice says 'next Monday': that is 2026-10-26. The model gave 2026-10-25, which was not used."
        in plan.notes
    )


def test_a_correct_relative_date_needs_no_note(site):
    notice = "Perception Day next Monday in Lab 3, Example City."
    right = reply(date="2026-10-26", date_phrase="next Monday", sources={"venue": "Lab 3, Example City"})
    plan = plan_add_event(site, FakeLLM(right), notice, today=TODAY)
    assert plan.failures == []
    assert not any("The notice says" in note for note in plan.notes)


def test_a_date_phrase_that_is_not_in_the_notice_does_not_excuse_the_date(site):
    notice = "Perception Day soon in Lab 3, Example City."
    made_up = reply(date="2026-10-26", date_phrase="next Monday", sources={"venue": "Lab 3, Example City"})
    plan = plan_add_event(site, FakeLLM(made_up), notice, today=TODAY)
    assert any(failure.startswith("date:") for failure in plan.failures)
    assert "date: 2026-10-26" in plan.changes[0].after  # unchanged: only the failure stops the write


def test_a_phrase_the_tool_cannot_resolve_falls_back_to_the_quote_rule(site):
    notice = "Perception Day the Monday after next in Lab 3, Example City."
    unresolved = reply(date="2026-11-02", date_phrase="the Monday after next", sources={"venue": "Lab 3, Example City"})
    plan = plan_add_event(site, FakeLLM(unresolved), notice, today=TODAY)
    assert any(failure.startswith("date:") for failure in plan.failures)


# the web notice path


def test_extract_notice_returns_fields_and_notes():
    notice = "Perception Day next Monday in Lab 3, Example City."
    wrong = reply(date="2026-10-25", date_phrase="next Monday", sources={"venue": None})
    result = extract_notice(FakeLLM(wrong), notice, "2026-10-20")
    assert result.fields["date"] == "2026-10-26"
    assert result.fields["kind"] == "workshop"
    assert "sources" not in result.fields and "date_phrase" not in result.fields
    assert any("that is 2026-10-26" in note for note in result.notes)
    assert any(note.startswith('venue "Lab 3, Example City": the notice does not give this') for note in result.notes)


def test_extract_notice_lists_an_unquoted_date_but_keeps_it_in_the_form():
    result = extract_notice(FakeLLM(reply(sources={})), NOTICE, TODAY)
    assert result.fields["date"] == "2026-11-05"
    assert any(note.startswith("date: the notice does not state this date") for note in result.notes)


def test_extract_from_notice_still_returns_only_the_fields():
    fields = extract_from_notice(FakeLLM(reply(kind=" Talk ")), NOTICE, "2026-10-20")
    assert fields["kind"] == "talk"
    assert fields["date"] == "2026-11-05"
    assert set(fields) <= {"title", "kind", "series", "date", "endDate", "venue", "summary", "body"}


def test_extract_notice_does_not_force_the_record_checks():
    """The web form lets the operator fill gaps, so a notice with no date is not an error there."""
    llm = FakeLLM('{"title": "Talk", "kind": "talk", "date": null}')
    result = extract_notice(llm, "A talk.", TODAY)
    assert result.fields == {"title": "Talk", "kind": "talk"}
    assert len(llm.calls) == 1


# the body check on the command line


def test_a_body_number_not_in_the_notice_is_a_failure(site):
    plan = plan_add_event(site, FakeLLM(reply(body="Open to all 250 students.")), NOTICE, today=TODAY)
    assert len(plan.failures) == 1
    assert '"250"' in plan.failures[0] and "not in your facts" in plan.failures[0]


def test_a_summary_number_not_in_the_notice_is_a_failure(site):
    plan = plan_add_event(site, FakeLLM(reply(summary="A day with 12 demos.")), NOTICE, today=TODAY)
    assert any('"12"' in failure for failure in plan.failures)


def test_the_event_date_written_another_way_in_the_body_is_supported(site):
    plan = plan_add_event(site, FakeLLM(reply(body="The day runs on November 5, 2026.")), NOTICE, today=TODAY)
    assert plan.failures == []
