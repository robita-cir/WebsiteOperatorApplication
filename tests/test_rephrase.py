"""The rewrite button: the model rewrites the text using only the facts, and the harness checks the result again."""

import hashlib
import html
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from helpers import FakeLLM
from test_web import csrf, person_form

from site_agent.web.app import create_app

FACTS = "Studies grasping."
INVENTED = "Ravi joined in 2019 and studies grasping."


def site_snapshot(root: Path) -> dict[str, str]:
    """Every file of the site except the app's own state folder, so a write to the site would show."""
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


def draft_then_form(client: TestClient) -> tuple[str, str]:
    """Drafts the body (the model invents a year), and returns the form page and the draft id."""
    response = client.post(
        "/c/people/new",
        data={"csrf": csrf(client), **person_form(body="", facts=FACTS, action="draft:body")},
        follow_redirects=False,
    )
    done = client.get(response.headers["location"], follow_redirects=False)
    return client.get(done.headers["location"]).text, done.headers["location"].split("draft=")[1]


def rewrite(client: TestClient, draft_id: str, **overrides) -> str:
    fields = {"body": INVENTED, "facts": FACTS, "draft_id": draft_id, "action": "rephrase:body", **overrides}
    response = client.post(
        "/c/people/new", data={"csrf": csrf(client), **person_form(**fields)}, follow_redirects=False
    )
    done = client.get(response.headers["location"], follow_redirects=False)
    assert done.status_code == 303 and "draft=" in done.headers["location"]
    return client.get(done.headers["location"]).text


def test_the_rewrite_button_appears_only_when_the_draft_has_items_not_in_the_facts(client_for):
    client, _ = client_for(INVENTED)
    form, _ = draft_then_form(client)
    assert "Rewrite with only your facts" in form and 'value="rephrase:body"' in form

    clean_client, _ = client_for("Ravi studies grasping.")
    clean_form, _ = draft_then_form(clean_client)
    assert "Rewrite with only your facts" not in clean_form


def test_a_rewrite_without_the_invented_year_clears_the_banner(client_for, site_dir):
    client, llm = client_for(INVENTED, "Ravi studies grasping.")
    _, draft_id = draft_then_form(client)
    before = site_snapshot(site_dir)

    form = rewrite(client, draft_id)

    assert "Not in your facts" not in form
    assert "Rewrite with only your facts" not in form
    assert "Ravi studies grasping." in html.unescape(form)
    sent = llm.calls[-1][0]
    assert FACTS in sent[1].content and INVENTED in sent[1].content  # the model got the facts and the current text
    assert site_snapshot(site_dir) == before  # nothing reaches the website


def test_a_rewrite_that_keeps_an_invented_number_still_shows_the_banner(client_for, site_dir):
    client, _ = client_for(INVENTED, "Ravi studies grasping since 2019 with 12 labs.")
    _, draft_id = draft_then_form(client)
    before = site_snapshot(site_dir)

    form = rewrite(client, draft_id)

    assert "Not in your facts" in form
    assert '"2019"' in html.unescape(form) and '"12"' in html.unescape(form)
    assert "Rewrite with only your facts" in form  # it can be tried again
    assert site_snapshot(site_dir) == before


def test_a_rewrite_that_is_still_unsupported_cannot_be_saved(client_for):
    client, _ = client_for(INVENTED, "Ravi studies grasping since 2019.")
    _, draft_id = draft_then_form(client)
    form = rewrite(client, draft_id)
    assert "Ravi studies grasping since 2019." in html.unescape(form)
    blocked = client.post(
        "/c/people/new",
        data={
            "csrf": csrf(client),
            **person_form(body="Ravi studies grasping since 2019.", facts=FACTS, draft_id=draft_id),
        },
    )
    assert blocked.status_code == 422 and 'mentions "2019"' in html.unescape(blocked.text)


def test_a_rewrite_keeps_the_facts_and_other_fields_the_operator_typed(client_for):
    client, _ = client_for(INVENTED, "Ravi studies grasping.")
    _, draft_id = draft_then_form(client)
    form = rewrite(client, draft_id, role="Typed role")
    assert "Typed role" in form and FACTS in form


def test_a_rewrite_works_for_a_record_being_edited(client_for, site_dir):
    client, _ = client_for("Jane studies robots.")
    before = site_snapshot(site_dir)
    response = client.post(
        "/c/people/jane-doe",
        data={
            "csrf": csrf(client),
            **person_form(body="Jane joined in 2001.", facts="Studies robots.", action="rephrase:body"),
        },
        follow_redirects=False,
    )
    done = client.get(response.headers["location"], follow_redirects=False)
    assert response.headers["location"].startswith("/jobs/")
    assert done.headers["location"].startswith("/c/people/jane-doe?draft=")
    assert "Jane studies robots." in client.get(done.headers["location"]).text
    assert site_snapshot(site_dir) == before


def test_a_rewrite_with_no_text_is_refused_without_asking_the_model(client_for, site_dir):
    client, llm = client_for()
    before = site_snapshot(site_dir)
    no_text = client.post(
        "/c/people/new",
        data={"csrf": csrf(client), **person_form(body="", facts=FACTS, action="rephrase:body")},
        follow_redirects=False,
    )
    assert no_text.headers["location"].startswith("/c/people/new?err=")
    assert llm.calls == [] and site_snapshot(site_dir) == before


def test_rephrase_draft_needs_facts_and_flags_what_remains():
    from site_agent.drafting import rephrase_draft
    from site_agent.errors import SiteAgentError
    from site_agent.records import SPECS

    spec = SPECS["people"]
    with pytest.raises(SiteAgentError):
        rephrase_draft(FakeLLM(), spec, "text", INVENTED, "  ")
    result = rephrase_draft(FakeLLM('"Studies grasping since 2019."'), spec, "text", INVENTED, FACTS)
    assert result == {"text": "Studies grasping since 2019.", "unsupported": ["2019"]}
