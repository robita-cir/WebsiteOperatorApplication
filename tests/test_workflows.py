import datetime as dt

import pytest
from helpers import FakeLLM

from site_agent.config import SiteSettings
from site_agent.errors import SiteAgentError
from site_agent.site import Site
from site_agent.workflows import plan_add_event, plan_update_event

TODAY = dt.date(2026, 10, 17)

NOTICE = "Hands-on Perception Day on 5 November 2026 in Lab 3, Example City. Open to all students."
ADD_REPLY = (
    '{"title": "Hands-on Perception Day", "kind": "workshop", "series": null, "date": "2026-11-05",'
    ' "endDate": null, "venue": "Lab 3, Example City", "summary": "A day of perception demos.",'
    ' "body": "Open to all students."}'
)


@pytest.fixture
def site(site_dir):
    return Site(SiteSettings(root=site_dir))


def test_add_event_renders_the_file_from_the_validated_record(site):
    plan = plan_add_event(site, FakeLLM(ADD_REPLY), NOTICE, today=TODAY)
    [change] = plan.changes
    assert change.is_new
    assert change.rel_path == "src/content/events/hands-on-perception-day.md"
    assert change.after == (
        "---\n"
        'title: "Hands-on Perception Day"\n'
        'kind: "workshop"\n'
        "date: 2026-11-05\n"
        'venue: "Lab 3, Example City"\n'
        'summary: "A day of perception demos."\n'
        "---\n"
        "\n"
        "Open to all students.\n"
    )
    assert plan.notes == []


def test_add_event_asks_again_when_the_first_reply_is_not_json(site):
    llm = FakeLLM("Sure, the event is a workshop on 5 November.", ADD_REPLY)
    plan_add_event(site, llm, NOTICE, today=TODAY)
    assert len(llm.calls) == 2
    retry_messages = llm.calls[1][0]
    assert retry_messages[-1].role == "user" and "not a valid JSON" in retry_messages[-1].content


def test_add_event_normalises_the_kind_and_ignores_sample(site):
    reply = ADD_REPLY.replace('"workshop"', '"Workshop"').replace('"body"', '"sample": true, "body"')
    plan = plan_add_event(site, FakeLLM(reply), NOTICE, today=TODAY)
    assert 'kind: "workshop"' in plan.changes[0].after
    assert "sample" not in plan.changes[0].after


def test_add_event_without_a_date_says_which_field_is_missing(site):
    reply = '{"title": "Talk", "kind": "talk", "date": null}'
    with pytest.raises(SiteAgentError, match="date:"):
        plan_add_event(site, FakeLLM(reply), "A talk.", today=TODAY)


def test_add_event_warns_about_values_not_in_the_notice(site):
    reply = ADD_REPLY.replace("Lab 3, Example City", "Atrium Hall")
    plan = plan_add_event(site, FakeLLM(reply), NOTICE, today=TODAY)
    assert any('venue "Atrium Hall"' in note for note in plan.notes)


UPDATE_REPLY = '{"date": "2026-04-14", "endDate": "2026-04-16"}'
UPDATE_INSTRUCTION = "The workshop moved to 14 April 2026 and now ends on 16 April 2026. The venue stays the same."


def test_update_changes_the_event_and_the_page_that_mentions_it(site, site_dir):
    llm = FakeLLM(UPDATE_REPLY)
    plan = plan_update_event(site, llm, "Robot Learning Workshop", UPDATE_INSTRUCTION, today=TODAY)

    assert [c.rel_path for c in plan.changes] == ["src/content/events/event-1.md", "src/content/news/next-up.md"]
    event_after = plan.changes[0].after
    assert "date: 2026-04-14" in event_after and "endDate: 2026-04-16" in event_after
    assert "# Keep this comment" in event_after
    assert "Next up: the Robot Learning Workshop runs from 14 April 2026 in Main Hall" in plan.changes[1].after
    assert plan.failures == []
    assert plan.notes == [
        "src/content/news/next-up.md: changed automatically on line 8, because it names the event. Check it.",
        "These files also show the old details, but the agent may not change them. "
        "Edit them by hand: src/pages/index.astro",
    ]
    assert len(llm.calls) == 1  # the page line names the event, so the tool replaces it without asking the model


SAVE_EDIT = """<<<<<<< SEARCH
Save the date: 10 March 2026
=======
Save the date: 14 April 2026
>>>>>>> REPLACE
"""


def test_by_default_lines_without_the_event_name_are_reported_not_guessed(site, site_dir):
    (site_dir / "src/content/news/deadlines.md").write_text(
        "<p>Proposal deadline: 10 March 2026</p>\n", encoding="utf-8"
    )
    llm = FakeLLM(UPDATE_REPLY)
    plan = plan_update_event(site, llm, "event-1", UPDATE_INSTRUCTION, today=TODAY)
    assert len(llm.calls) == 1
    assert all(c.rel_path != "src/content/news/deadlines.md" for c in plan.changes)
    assert any("src/content/news/deadlines.md: line 1 still show" in n and "--assisted" in n for n in plan.notes)


def test_changed_lines_are_listed_for_the_operator_to_check(site):
    plan = plan_update_event(site, FakeLLM(UPDATE_REPLY), "event-1", UPDATE_INSTRUCTION, today=TODAY)
    assert any("src/content/news/next-up.md: changed automatically on line 8" in n for n in plan.notes)


def test_assisted_mode_lets_the_model_handle_leftover_lines(site, site_dir):
    (site_dir / "src/content/news/deadlines.md").write_text("<p>Save the date: 10 March 2026</p>\n", encoding="utf-8")
    llm = FakeLLM(UPDATE_REPLY, SAVE_EDIT)
    plan = plan_update_event(site, llm, "event-1", UPDATE_INSTRUCTION, today=TODAY, assisted=True)

    assert len(llm.calls) == 2
    deadlines = next(c for c in plan.changes if c.rel_path == "src/content/news/deadlines.md")
    assert "Save the date: 14 April 2026" in deadlines.after
    assert plan.failures == []


def test_unrelated_dates_are_left_alone_when_the_model_says_no_change(site, site_dir):
    (site_dir / "src/content/news/deadlines.md").write_text(
        "<p>Proposal deadline: 10 March 2026</p>\n", encoding="utf-8"
    )
    plan = plan_update_event(
        site, FakeLLM(UPDATE_REPLY, "NO_CHANGE"), "event-1", UPDATE_INSTRUCTION, today=TODAY, assisted=True
    )
    assert all(c.rel_path != "src/content/news/deadlines.md" for c in plan.changes)
    assert plan.failures == []


def test_model_edit_that_cannot_be_placed_is_reported_not_applied(site, site_dir):
    (site_dir / "src/content/news/deadlines.md").write_text("<p>Save the date: 10 March 2026</p>\n", encoding="utf-8")
    bad_edit = SAVE_EDIT.replace("Save the date: 10 March 2026\n=======", "Save the date: 1 March 2026\n=======")
    plan = plan_update_event(
        site, FakeLLM(UPDATE_REPLY, bad_edit), "event-1", UPDATE_INSTRUCTION, today=TODAY, assisted=True
    )
    assert any("deadlines.md" in failure and "not found" in failure for failure in plan.failures)
    assert all(c.rel_path != "src/content/news/deadlines.md" for c in plan.changes)


def test_update_keeps_fields_the_model_leaves_out(site):
    llm = FakeLLM('{"summary": "Now with a poster session."}')
    plan = plan_update_event(site, llm, "event-1", "Add a poster session.", today=TODAY)
    text = plan.changes[0].after
    assert 'summary: "Now with a poster session."' in text
    assert 'venue: "Main Hall, Example City"' in text
    assert 'series: "Annual workshop"' in text
    assert "date: 2026-03-10" in text


def test_update_removes_a_field_the_model_sets_to_null(site):
    plan = plan_update_event(site, FakeLLM('{"series": null}'), "event-1", "No longer part of a series.", today=TODAY)
    assert "series:" not in plan.changes[0].after


def test_update_that_only_changes_the_summary_does_not_search_the_site(site):
    llm = FakeLLM('{"summary": "Now with a poster session."}')
    plan = plan_update_event(site, llm, "event-1", "Add that there is a poster session.", today=TODAY)
    assert len(llm.calls) == 1
    assert [c.rel_path for c in plan.changes] == ["src/content/events/event-1.md"]


def test_update_never_edits_a_file_outside_the_allow_list(site, site_dir):
    (site_dir / "public").mkdir(exist_ok=True)
    (site_dir / "public" / "poster.md").write_text("Robot Learning Workshop, 10 March 2026\n", encoding="utf-8")
    plan = plan_update_event(site, FakeLLM(UPDATE_REPLY), "event-1", UPDATE_INSTRUCTION, today=TODAY)
    assert any("public/poster.md" in note for note in plan.notes)
    assert all(c.rel_path != "public/poster.md" for c in plan.changes)


def test_homepage_lines_naming_the_event_are_listed_not_edited(site):
    """Code and page files are never written by the tool, so the homepage line is reported for hand editing."""
    plan = plan_update_event(site, FakeLLM(UPDATE_REPLY), "event-1", UPDATE_INSTRUCTION, today=TODAY)
    assert all(c.rel_path != "src/pages/index.astro" for c in plan.changes)
    assert any("src/pages/index.astro" in note and "by hand" in note for note in plan.notes)


def test_a_venue_change_is_made_on_the_news_line_that_names_the_event(site):
    plan = plan_update_event(
        site, FakeLLM('{"venue": "Lecture Theatre, Example City"}'), "event-1", "Moved.", today=TODAY
    )
    news = next(change for change in plan.changes if change.rel_path == "src/content/news/next-up.md")
    assert "in Lecture Theatre, Example City." in news.after
    assert "Main Hall" not in news.after
    assert any("next-up.md" in note and "changed automatically" in note for note in plan.notes)
