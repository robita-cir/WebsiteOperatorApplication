import datetime as dt

import pytest

from site_agent.config import SiteSettings
from site_agent.records import SPECS, validate_values
from site_agent.repository import Repository
from site_agent.site import Site

TODAY = dt.date(2026, 10, 20)


@pytest.fixture
def site(site_dir):
    return Site(SiteSettings(root=site_dir))


@pytest.fixture
def repo(site):
    return Repository(site, today=TODAY)


def publication(**extra):
    base = {"title": "A paper", "authors": ["Jane Doe"], "venue": "Somewhere", "year": "2025", "type": "journal"}
    return {**base, **extra}


@pytest.mark.parametrize("year", ["0042", "1949", "2028"])
def test_year_outside_the_range_is_an_error(repo, year):
    outcome = repo.create(SPECS["publications"], publication(year=year))
    assert outcome.errors == {"year": "Year must be between 1950 and 2027."}
    assert outcome.plan is None


@pytest.mark.parametrize("year", ["1950", "2027"])
def test_year_at_the_edges_is_accepted(repo, year):
    assert repo.create(SPECS["publications"], publication(year=year)).ok


def test_validate_values_takes_the_latest_year_from_the_given_date():
    spec = SPECS["publications"]
    assert validate_values(spec, {"year": 2031}, today=dt.date(2030, 1, 1)) == {}
    assert validate_values(spec, {"year": 2032}, today=dt.date(2030, 1, 1)) == {
        "year": "Year must be between 1950 and 2031."
    }


def test_title_of_121_characters_is_an_error(repo):
    outcome = repo.create(SPECS["publications"], publication(title="x" * 121))
    assert outcome.errors == {"title": "Title is too long (121 characters). Keep it to 120 characters."}


def test_title_of_120_characters_is_accepted(repo):
    assert repo.create(SPECS["publications"], publication(title="x" * 120)).ok


def test_long_title_is_also_refused_on_update(repo):
    outcome = repo.update(SPECS["events"], "event-1", {"title": "y" * 130, "kind": "workshop", "date": "2026-03-10"})
    assert "title" in outcome.errors


def write_project(site, name, featured):
    flag = "featured: true\n" if featured else ""
    site.write(
        f"src/content/projects/{name}.md", f'---\ntitle: "{name}"\narea: "other"\nstudents: ["Jane Doe"]\n{flag}---\n'
    )


def new_project(**extra):
    return {"title": "Fresh project", "area": "other", "students": ["Jane Doe"], **extra}


def test_fifth_featured_project_warns(repo, site):
    # grasp-learning is already featured; three more make four, so one more would be hidden.
    for n in range(3):
        write_project(site, f"extra-{n}", True)
    outcome = repo.create(SPECS["projects"], new_project(featured="on"))
    assert outcome.ok
    assert outcome.warnings == [
        "There are already four featured projects. Unfeature one first, or this one will not be shown on the homepage."
    ]


def test_fourth_featured_project_does_not_warn(repo, site):
    write_project(site, "extra-0", True)
    write_project(site, "extra-1", True)
    assert repo.create(SPECS["projects"], new_project(featured="on")).warnings == []


def test_unfeatured_project_never_warns_about_the_limit(repo, site):
    for n in range(5):
        write_project(site, f"extra-{n}", True)
    assert repo.create(SPECS["projects"], new_project()).warnings == []


def test_editing_a_featured_project_does_not_count_itself(repo, site):
    for n in range(3):
        write_project(site, f"extra-{n}", True)
    outcome = repo.update(SPECS["projects"], "grasp-learning", new_project(featured="on", title="Grasp learning"))
    assert outcome.warnings == []


def write_partner(site, name, featured):
    flag = "featured: true\n" if featured else ""
    site.write(
        f"src/content/partners/{name}.md", f'---\nname: "{name}"\nkind: "academic"\nstatus: "present"\n{flag}---\n'
    )


def test_seventh_featured_partner_warns(repo, site):
    # example-university is already featured; five more make six.
    for n in range(5):
        write_partner(site, f"partner-{n}", True)
    values = {"name": "Newcomer", "kind": "industry", "status": "present", "featured": "on"}
    outcome = repo.create(SPECS["partners"], values)
    assert outcome.warnings == [
        "There are already six featured partners. Unfeature one first, or this one will not be shown on the homepage."
    ]


def test_sixth_featured_partner_does_not_warn(repo, site):
    for n in range(4):
        write_partner(site, f"partner-{n}", True)
    values = {"name": "Newcomer", "kind": "industry", "status": "present", "featured": "on"}
    assert repo.create(SPECS["partners"], values).warnings == []


def opening(**extra):
    return {"title": "Intern", "type": "internship", "status": "open", "summary": "Help us.", **extra}


def test_passed_deadline_warns(repo):
    outcome = repo.create(SPECS["openings"], opening(deadline="2026-10-19"))
    assert outcome.ok
    assert outcome.warnings == ["This deadline has passed (2026-10-19). Check whether the opening should be closed."]


def test_deadline_today_or_later_does_not_warn(repo):
    assert repo.create(SPECS["openings"], opening(deadline="2026-10-20")).warnings == []


def test_passed_deadline_on_a_closed_opening_does_not_warn(repo):
    assert repo.create(SPECS["openings"], opening(deadline="2020-01-01", status="closed")).warnings == []
