"""The list search: every word, any order, ignoring case and accents, across the fields that identify an entry."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from helpers import FakeLLM

from site_agent.records import SPECS
from site_agent.search import SEARCH_FIELDS, matches, search_values
from site_agent.web.app import create_app


@pytest.fixture
def client(site_dir: Path) -> TestClient:
    c = TestClient(create_app(site_dir, llm=FakeLLM(), inline_jobs=True))
    c.get("/")
    return c


def test_empty_query_matches_everything():
    assert matches("", ["anything"])
    assert matches("   ", [])


def test_every_word_must_match_in_any_order():
    values = ["Jane Doe", "Professor", "Department of Example"]
    assert matches("professor jane", values)
    assert matches("doe example", values)
    assert not matches("jane smith", values)


def test_case_and_accents_are_ignored():
    assert matches("jose", ["José García"])
    assert matches("GARCÍA jose", ["Jose Garcia"])


def test_words_may_come_from_different_fields():
    assert matches("learning workshop", ["Robot Learning Workshop", "Main Hall"])


def test_every_collection_searches_fields_that_exist():
    assert set(SEARCH_FIELDS) == set(SPECS)
    for key, names in SEARCH_FIELDS.items():
        for name in names:
            SPECS[key].field(name)


def test_search_values_include_lists_and_choice_labels():
    values = search_values(SPECS["openings"], {"title": "Perception", "type": "phd"})
    assert "PhD" in values
    people = search_values(SPECS["people"], {"name": "Jane", "interests": ["Robot learning", "HRI"], "order": 1})
    assert "HRI" in people and "1" not in people


def test_people_are_found_by_role_department_and_interest(client):
    for query in ("professor", "department example", "human-robot jane"):
        page = client.get("/c/people", params={"q": query}).text
        assert "Jane Doe" in page and "Sam Roe" not in page, query


def test_projects_are_found_by_student_and_area(client):
    assert "Learning to grasp" in client.get("/c/projects", params={"q": "roe sam"}).text
    assert "Learning to grasp" in client.get("/c/projects", params={"q": "perception manipulation"}).text
    assert "Learning to grasp" not in client.get("/c/projects", params={"q": "navigation"}).text


def test_publications_are_found_by_author_and_venue(client):
    assert "A small example paper" in client.get("/c/publications", params={"q": "conference doe"}).text


def test_events_and_openings_are_found_by_detail(client):
    assert "Robot Learning Workshop" in client.get("/c/events", params={"q": "main hall workshop"}).text
    assert "PhD position in perception" in client.get("/c/openings", params={"q": "phd"}).text


def test_funding_is_found_by_funder(client):
    assert "Example programme" in client.get("/c/funding", params={"q": "agency"}).text


def test_search_ignores_accents_in_a_real_entry(client, site_dir):
    path = site_dir / "src" / "content" / "people" / "jane-doe.md"
    path.write_text(path.read_text(encoding="utf-8").replace('"Jane Doe"', '"Jané Doe"'), encoding="utf-8")
    assert "Jané Doe" in client.get("/c/people", params={"q": "jane"}).text


def test_samples_filter_still_works_with_a_search(client):
    page = client.get("/c/people", params={"q": "sam", "samples": "1"}).text
    assert "Sam Roe" in page and "Jane Doe" not in page
    page = client.get("/c/people", params={"q": "jane", "samples": "1"}).text
    assert "Jane Doe" not in page


def test_an_unreadable_entry_is_still_found_by_its_name(client, site_dir):
    (site_dir / "src" / "content" / "people" / "broken.md").write_text("no front matter {{", encoding="utf-8")
    assert "broken" in client.get("/c/people", params={"q": "broken"}).text


def test_the_search_hint_describes_the_search(client):
    assert "Search by name, title or detail" in client.get("/c/people").text
