import pytest

from site_agent.config import SiteSettings
from site_agent.errors import SiteAgentError
from site_agent.events import find_event, load_event, new_event_path
from site_agent.site import Site


@pytest.fixture
def site(site_dir):
    return Site(SiteSettings(root=site_dir))


def test_find_by_file_name(site):
    assert find_event(site, "event-2") == "src/content/events/event-2.md"


def test_find_by_exact_title_in_any_case(site):
    assert find_event(site, "robot learning WORKSHOP") == "src/content/events/event-1.md"


def test_unknown_event_suggests_close_titles(site):
    with pytest.raises(SiteAgentError, match="Did you mean: src/content/events/event-1.md"):
        find_event(site, "Robot Learning Worksop")


def test_load_event_returns_the_validated_record(site):
    event, text = load_event(site, "src/content/events/event-2.md")
    assert event.title == "Seminar on Assistive Robots"
    assert text.startswith("---")


def test_new_event_path_adds_a_number_when_the_name_is_taken(site):
    assert new_event_path(site, "Event 2") == "src/content/events/event-2-2.md"


def test_explicit_slug_must_be_free_and_well_formed(site):
    with pytest.raises(SiteAgentError, match="already exists"):
        new_event_path(site, "Anything", slug="event-1")
    with pytest.raises(SiteAgentError, match="lower-case"):
        new_event_path(site, "Anything", slug="Bad Slug")
