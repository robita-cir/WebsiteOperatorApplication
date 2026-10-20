"""The Suggest button: the model may pick one of a choice field's listed options, and nothing more."""

import hashlib
import html
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from helpers import FakeLLM
from test_web import csrf, person_form

from site_agent.web.app import create_app

PLAIN_REFUSAL = "The helper could not pick one of the listed options. Choose one yourself."


def site_snapshot(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".site-agent" not in p.parts and "node_modules" not in p.parts
    }


@pytest.fixture
def client_for(site_dir: Path):
    def build(*replies: str) -> tuple[TestClient, FakeLLM]:
        llm = FakeLLM(*replies)
        client = TestClient(create_app(site_dir, llm=llm, inline_jobs=True))
        client.get("/")
        return client, llm

    return build


def ask(client: TestClient, url: str = "/c/people/new", **overrides) -> str:
    form = person_form(group="", facts="Ravi is a PhD student.", action="suggest:group", **overrides)
    response = client.post(url, data={"csrf": csrf(client), **form}, follow_redirects=False)
    done = client.get(response.headers["location"], follow_redirects=False)
    assert done.status_code == 303, done.text
    return client.get(done.headers["location"]).text


def selected(page: str) -> str:
    start = page.index('<select id="f-group"')
    block = page[start : page.index("</select>", start)]
    chosen = [part for part in block.split("<option ")[1:] if " selected" in part]
    return chosen[0].split('"')[1] if chosen else ""


def test_a_suggestion_that_is_one_of_the_options_is_selected_but_not_saved(client_for, site_dir):
    client, llm = client_for('{"value": "scholar"}')
    before = site_snapshot(site_dir)

    page = ask(client)

    assert selected(page) == "scholar"
    assert "The helper suggests" in page and "Research scholar" in page
    assert PLAIN_REFUSAL not in page
    # it was asked for the listed options, with the title and the facts
    prompt = llm.calls[0][0]
    assert "- scholar (Research scholar)" in prompt[0].content
    assert "Ravi Kumar" in prompt[1].content and "PhD student" in prompt[1].content
    assert site_snapshot(site_dir) == before


@pytest.mark.parametrize(
    "reply", ['{"value": "professor"}', '{"value": "Research scholar"}', "no idea", '{"value": 3}']
)
def test_a_suggestion_that_is_not_an_option_is_refused_in_plain_words(client_for, site_dir, reply):
    client, _ = client_for(reply)
    before = site_snapshot(site_dir)

    page = ask(client)

    assert selected(page) == ""
    assert PLAIN_REFUSAL in html.unescape(page)
    assert site_snapshot(site_dir) == before


def test_the_suggest_button_shows_only_for_an_empty_choice_field(client_for):
    client, _ = client_for()
    assert 'value="suggest:group"' in client.get("/c/people/new").text  # a new person has no group yet
    assert 'value="suggest:group"' not in client.get("/c/people/jane-doe").text
    assert 'value="suggest:group"' not in ask_page_with_group(client)


def ask_page_with_group(client: TestClient) -> str:
    """A form posted with a group is shown again without the button (a missing name keeps it on screen)."""
    return client.post("/c/people/new", data={"csrf": csrf(client), **person_form(name="")}).text


def test_a_suggestion_works_for_a_record_being_edited(client_for, site_dir):
    client, _ = client_for('{"value": "faculty"}')
    before = site_snapshot(site_dir)
    page = ask(client, url="/c/people/jane-doe")
    assert selected(page) == "faculty"
    assert site_snapshot(site_dir) == before


def test_the_suggestion_is_dropped_when_the_operator_changes_the_field(client_for):
    client, _ = client_for('{"value": "scholar"}')
    page = ask(client)
    draft_id = page.split('name="draft_id" value="')[1].split('"')[0]

    # a missing name keeps the form on screen, so we can see whether the suggestion is still shown
    kept = client.post(
        "/c/people/new", data={"csrf": csrf(client), **person_form(name="", group="scholar", draft_id=draft_id)}
    )
    assert "The helper suggests" in kept.text
    changed = client.post(
        "/c/people/new", data={"csrf": csrf(client), **person_form(name="", group="faculty", draft_id=draft_id)}
    )
    assert "The helper suggests" not in changed.text and "draft_id" not in changed.text


def test_a_suggestion_needs_something_to_go_on(client_for):
    client, llm = client_for()
    # a news item with nothing filled in: no title, no summary and no fact
    response = client.post("/c/news/new", data={"csrf": csrf(client), "action": "suggest:kind"}, follow_redirects=False)
    assert response.status_code == 303 and "err=" in response.headers["location"]
    assert llm.calls == []


def test_a_field_that_is_not_a_choice_cannot_be_suggested(client_for):
    client, _ = client_for()
    response = client.post(
        "/c/people/new",
        data={"csrf": csrf(client), **person_form(action="suggest:role")},
        follow_redirects=False,
    )
    assert response.status_code == 400
