"""The claim check: sentences that share no meaningful word with the facts are listed as warnings."""

import html
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from helpers import FakeLLM

from site_agent.drafting import draft_section
from site_agent.factcheck import claim_sentences
from site_agent.records import SPECS
from site_agent.web.app import create_app

FACTS = "Name: Ravi Kumar\nRole: Research scholar\nStudies robot grasping and tactile sensing."
DRAFT = "Ravi studies robot grasping. He won a global prize for pottery."


def test_an_invented_claim_is_flagged_and_the_supported_sentence_is_not():
    assert claim_sentences(DRAFT, FACTS) == ["He won a global prize for pottery."]


def test_matching_ignores_case_and_short_or_common_words():
    assert claim_sentences("TACTILE work with the very best.", FACTS) == []
    # Only stopwords and short words remain, so there is nothing to compare and nothing to flag.
    assert claim_sentences("It was done by us all.", FACTS) == []


def test_sentences_split_on_full_stops_question_marks_and_lines():
    text = "Ravi studies grasping.\nHe loves pottery! Does he swim? Research scholar."
    assert claim_sentences(text, FACTS) == ["He loves pottery!", "Does he swim?"]


def test_draft_section_returns_claims_without_touching_unsupported():
    result = draft_section(FakeLLM(DRAFT), SPECS["people"], "biography", "body", FACTS)
    assert set(result) == {"text", "unsupported", "claims"}
    assert result["claims"] == ["He won a global prize for pottery."]
    assert result["unsupported"] == []


@pytest.fixture
def client(site_dir: Path):
    c = TestClient(create_app(site_dir, llm=FakeLLM(DRAFT), inline_jobs=True))
    c.get("/")
    return c


def person(**overrides) -> dict:
    data = {
        "name": "Ravi Kumar",
        "group": "scholar",
        "role": "Research scholar",
        "dept": "",
        "interests": "Grasping",
        "homepage": "",
        "photo": "",
        "order": "100",
        "body": "",
        "facts": "Studies robot grasping and tactile sensing.",
        "action": "draft:body",
    }
    data.update(overrides)
    return data


def draft_form_url(client: TestClient) -> str:
    csrf = client.cookies.get("sa_csrf", "")
    start = client.post("/c/people/new", data={"csrf": csrf, **person()}, follow_redirects=False)
    return client.get(start.headers["location"], follow_redirects=False).headers["location"]


def test_claims_show_in_the_draft_panel_and_never_block_saving(client, site_dir):
    form_url = draft_form_url(client)
    page = html.unescape(client.get(form_url).text)
    assert "Check this sentence against your facts: He won a global prize for pottery." in page
    assert "Check this sentence against your facts: Ravi studies" not in page

    draft_file = next((site_dir / ".site-agent" / "drafts").glob("*.json"))
    assert json.loads(draft_file.read_text(encoding="utf-8"))["claims"] == ["He won a global prize for pottery."]

    saved = client.post(
        "/c/people/new",
        data={
            "csrf": client.cookies.get("sa_csrf", ""),
            **person(body=DRAFT, action="preview", draft_id=form_url.split("draft=")[1]),
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303 and saved.headers["location"].startswith("/preview/")


def test_a_claim_disappears_from_the_panel_once_its_sentence_is_edited_out(client):
    draft_id = draft_form_url(client).split("draft=")[1]
    # A blank name fails the save, which shows the form again with the draft still attached.
    again = client.post(
        "/c/people/new",
        data={
            "csrf": client.cookies.get("sa_csrf", ""),
            **person(body="Ravi studies robot grasping.", action="preview", name="", draft_id=draft_id),
        },
    )
    assert again.status_code == 422
    assert "Check this sentence against your facts" not in html.unescape(again.text)
