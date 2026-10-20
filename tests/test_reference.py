"""Filling the publication form from a pasted reference. The model is scripted; the paste checks every value."""

import html
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from helpers import FakeLLM

from site_agent.reference import read_reference
from site_agent.web.app import create_app

PASTE = (
    "Doe, J. and Roe, S. (2023). Learning to grasp  from touch. Journal of Example Robotics, 12(3), 1-10. "
    "https://example.org/grasp-paper"
)


def reply(**overrides) -> str:
    data = {
        "title": "Learning to grasp from touch",
        "authors": ["Doe, J.", "Roe, S."],
        "venue": "Journal of Example Robotics",
        "year": 2023,
        "type": "journal",
        "doi": None,
        "url": "https://example.org/grasp-paper",
    }
    data.update(overrides)
    return json.dumps(data)


def read(text: str = PASTE, **overrides):
    return read_reference(FakeLLM(reply(**overrides)), text, 2026)


def test_a_fully_stated_reference_is_kept_without_notes():
    fields, notes = read()
    assert fields == {
        "title": "Learning to grasp from touch",
        "authors": ["Doe, J.", "Roe, S."],
        "venue": "Journal of Example Robotics",
        "year": 2023,
        "type": "journal",
        "url": "https://example.org/grasp-paper",
    }
    assert notes == []


def test_an_invented_doi_is_blanked_and_noted_but_the_title_stays():
    fields, notes = read(doi="10.1234/invented.2023")
    assert "doi" not in fields
    assert fields["title"] == "Learning to grasp from touch"
    assert notes == ["The text does not state that DOI, so it was left empty."]


def test_a_stated_doi_is_kept_and_its_address_form_is_stripped():
    text = PASTE + " DOI: 10.1000/Grasp.2023.7"
    for written in ("https://doi.org/10.1000/grasp.2023.7", "doi:10.1000/GRASP.2023.7", "DOI:10.1000/grasp.2023.7"):
        fields, notes = read(text, doi=written)
        assert fields["doi"].casefold() == "10.1000/grasp.2023.7", written
        assert notes == []


def test_a_malformed_doi_is_blanked():
    fields, notes = read(PASTE + " 11.5/x", doi="11.5/x")
    assert "doi" not in fields and len(notes) == 1


@pytest.mark.parametrize("year", [1949, 2028, 20231, "soon", True])
def test_a_year_outside_the_range_is_blanked(year):
    fields, notes = read(PASTE + " 1949 2028 20231", year=year)
    assert "year" not in fields
    assert any("year" in n for n in notes)


def test_a_year_the_text_does_not_contain_is_blanked():
    fields, notes = read(year=2021)
    assert "year" not in fields and any("year" in n for n in notes)


def test_next_year_is_allowed_when_the_text_states_it():
    fields, _ = read("Doe (2027). Learning to grasp from touch. Journal of Example Robotics.", year=2027)
    assert fields["year"] == 2027


def test_a_venue_not_in_the_paste_is_blanked_with_the_agreed_note():
    fields, notes = read(venue="International Conference on Invented Things")
    assert "venue" not in fields
    assert "The text does not state the venue, so it was left empty." in notes


def test_a_title_or_author_not_in_the_paste_is_blanked():
    fields, notes = read(title="A different paper", authors=["Doe, J.", "A. Stranger"])
    assert "title" not in fields
    assert fields["authors"] == ["Doe, J."]
    assert any("A. Stranger" in n for n in notes)


def test_matching_ignores_case_and_spacing():
    fields, _ = read(
        "DOE, J. (2023). LEARNING TO GRASP   FROM TOUCH. Journal of Example Robotics.", authors=["Doe, J."]
    )
    assert fields["title"] == "Learning to grasp from touch"
    assert fields["authors"] == ["Doe, J."]


def test_an_unknown_type_is_blanked():
    fields, _ = read(type="monograph")
    assert "type" not in fields


def test_a_link_not_in_the_paste_is_dropped():
    fields, notes = read(url="https://example.org/invented")
    assert "url" not in fields and len(notes) == 1


# --- through the web app --------------------------------------------------------------------------


@pytest.fixture
def make_client(site_dir: Path):
    def build(llm=None) -> TestClient:
        client = TestClient(create_app(site_dir, llm=llm or FakeLLM(), inline_jobs=True))
        client.get("/")
        return client

    return build


def token(client: TestClient) -> str:
    return client.cookies.get("sa_csrf", "")


def test_the_reference_panel_is_only_on_the_publications_form(make_client):
    client = make_client()
    assert 'value="reference"' in client.get("/c/publications/new").text
    for key in ("people", "events", "news", "projects"):
        assert 'value="reference"' not in client.get(f"/c/{key}/new").text, key


def test_the_reference_fills_the_form_and_the_notes_show_in_the_draft_panel(make_client, site_dir):
    client = make_client(FakeLLM(reply(doi="10.1234/invented.2023", venue="Elsewhere")))
    response = client.post(
        "/c/publications/new",
        data={"csrf": token(client), "action": "reference", "reference": PASTE},
        follow_redirects=False,
    )
    page = html.unescape(client.get(response.headers["location"]).text)
    assert 'value="Learning to grasp from touch"' in page
    assert 'value="2023"' in page
    assert "Doe, J.\nRoe, S." in page
    assert '<option value="journal" selected>' in page
    assert "The text does not state the venue, so it was left empty." in page
    assert "The text does not state that DOI, so it was left empty." in page
    draft = json.loads(next((site_dir / ".site-agent" / "drafts").glob("*.json")).read_text(encoding="utf-8"))
    assert draft["kind"] == "reference" and draft["fields"]["year"] == 2023


def test_an_empty_reference_asks_for_a_paste_and_starts_no_job(make_client):
    llm = FakeLLM()
    client = make_client(llm)
    response = client.post(
        "/c/publications/new",
        data={"csrf": token(client), "action": "reference", "reference": "  "},
        follow_redirects=False,
    )
    assert response.headers["location"].startswith("/c/publications/new?err=")
    assert llm.calls == []


def test_a_reference_cannot_be_read_for_other_collections(make_client):
    client = make_client()
    response = client.post(
        "/c/people/new", data={"csrf": token(client), "action": "reference", "reference": PASTE}, follow_redirects=False
    )
    assert response.status_code == 400
