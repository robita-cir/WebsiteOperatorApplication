import pytest

from site_agent.config import SiteSettings
from site_agent.records import SPECS, normalise_doi, normalise_name
from site_agent.repository import Repository
from site_agent.site import Site


@pytest.fixture
def repo(site_dir):
    return Repository(Site(SiteSettings(root=site_dir)))


def person(name, **extra):
    return {"name": name, "group": "mtech", **extra}


def test_names_are_compared_without_case_accents_punctuation_or_order():
    assert normalise_name("Doe, Jane") == normalise_name("jane  doe") == "jane doe"
    assert normalise_name("José  Núñez") == "jose nunez"
    assert normalise_name("J. Doe") == "j doe"


def test_doi_is_compared_without_prefix_or_case():
    assert normalise_doi("https://doi.org/10.1000/ABC") == "10.1000/abc"
    assert normalise_doi("doi:10.1000/abc") == "10.1000/abc"


@pytest.mark.parametrize("name", ["Doe, Jane", "jane  doe", "JANE DOE"])
def test_second_person_with_the_same_name_is_blocked_on_create(repo, name):
    outcome = repo.create(SPECS["people"], person(name))
    assert not outcome.ok
    assert outcome.plan is None
    assert outcome.blockers == [
        f"A person called {name} is already on the site (jane-doe). Edit that entry instead, or use a different name."
    ]


def test_person_does_not_block_when_editing_themself(repo):
    outcome = repo.update(SPECS["people"], "jane-doe", person("Jane Doe", role="Professor emerita", order="1"))
    assert outcome.ok
    assert not any("already on the site" in b for b in outcome.blockers)


def test_renaming_a_person_to_another_persons_name_is_blocked(repo):
    outcome = repo.update(SPECS["people"], "sam-roe", person("Doe, Jane"))
    assert any("already on the site (jane-doe)" in b for b in outcome.blockers)


def publication(**extra):
    base = {
        "title": "Another paper",
        "authors": ["Jane Doe"],
        "venue": "Somewhere",
        "year": "2025",
        "type": "journal",
    }
    return {**base, **extra}


def test_same_doi_is_blocked_even_when_written_in_capitals(repo):
    outcome = repo.create(SPECS["publications"], publication(doi="10.1000/EXAMPLE.2025.1"))
    assert outcome.blockers == ["A publication with this DOI is already on the site (example-paper)."]


def test_publication_keeps_its_own_doi_when_edited(repo):
    outcome = repo.update(
        SPECS["publications"], "example-paper", publication(title="A small example paper", doi="10.1000/example.2025.1")
    )
    assert outcome.ok


def test_publication_with_a_new_doi_is_not_blocked(repo):
    assert repo.create(SPECS["publications"], publication(doi="10.1000/new.1")).ok


def event(title):
    return {"title": title, "kind": "talk", "date": "2026-11-05"}


def test_event_with_the_same_title_is_only_a_warning(repo):
    outcome = repo.create(SPECS["events"], event("robot learning  workshop"))
    assert outcome.ok
    assert outcome.plan is not None
    assert outcome.warnings == [
        "An event called robot learning  workshop already exists (event-1). Check that this is a new event."
    ]


def test_other_collections_have_no_duplicate_check(repo):
    values = {"title": "Open day", "description": "Another open day."}
    outcome = repo.create(SPECS["gallery"], values)
    assert outcome.ok
    assert outcome.warnings == []


def project(students):
    return {"title": "New project", "area": "other", "students": students}


def test_unknown_student_gets_the_closest_names(repo):
    outcome = repo.create(SPECS["projects"], project(["Jane Do"]))
    [warning] = outcome.warnings
    assert warning.startswith('"Jane Do" is not on the People list, so the name will not link to a profile.')
    assert warning.endswith("Did you mean: Jane Doe?")


def test_unknown_student_with_no_close_name_has_no_hint(repo):
    [warning] = repo.create(SPECS["projects"], project(["Zzzzz Qqqqq"])).warnings
    assert "Did you mean" not in warning


def test_unknown_partner_gets_the_closest_names(repo):
    values = {"title": "Programme", "funder": "A funder", "partner": "Example Universty"}
    [warning] = repo.create(SPECS["funding"], values).warnings
    assert warning == '"Example Universty" is not on the Partners list. Did you mean: Example University?'
