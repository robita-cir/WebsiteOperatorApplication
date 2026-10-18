import pytest

from site_agent.config import SiteSettings
from site_agent.errors import SiteAgentError
from site_agent.site import Site


@pytest.fixture
def site(site_dir):
    return Site(SiteSettings(root=site_dir))


def test_paths_that_leave_the_site_are_refused(site):
    for bad in ("../outside.md", "/etc/passwd", "src/../../x.md"):
        with pytest.raises(SiteAgentError, match="outside the site folder"):
            site.resolve(bad)


def test_dependency_folders_and_binary_files_are_not_searched(site, site_dir):
    (site_dir / "src" / "logo.png").write_bytes(b"\x89PNG")
    files = site.iter_text_files()
    assert not any(f.startswith("node_modules") for f in files)
    assert "src/logo.png" not in files
    assert "src/pages/index.astro" in files


def test_mentions_are_found_across_files_and_skip_dependencies(site):
    mentions = site.find_mentions(["robot learning workshop"])
    paths = {m.rel_path for m in mentions}
    assert paths == {
        "src/pages/index.astro",
        "src/content/events/event-1.md",
        "src/content/news/announcement-1.md",
        "src/content/news/next-up.md",
    }
    index_hit = next(m for m in mentions if m.rel_path == "src/content/news/next-up.md")
    assert index_hit.line_no == 8


def test_writable_allow_list(site):
    assert site.is_writable("src/content/events/new.md")
    assert site.is_writable("src/content/events/new.md")
    assert not site.is_writable("src/pages/index.astro")
    assert not site.is_writable("public/logo.svg")
    assert not site.is_writable("node_modules/left-pad/index.js")


def test_collection_files_lists_markdown_in_one_collection(site):
    assert site.collection_files("events") == [
        "src/content/events/event-1.md",
        "src/content/events/event-2.md",
        "src/content/events/sample-talk.md",
    ]
    assert site.collection_files("does-not-exist") == []
