"""Launch readiness checks. Each one matches a rule in the template's own launch check (scripts/launch-check.mjs)."""

from site_agent.appstate import AppState
from site_agent.config import SiteSettings
from site_agent.launch import launch_report
from site_agent.repository import Repository
from site_agent.site import Site


def launch(site_dir):
    site = Site(SiteSettings(root=site_dir))
    return launch_report(site, Repository(site), AppState(site))


def write(site_dir, rel, text):
    path = site_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_missing_social_image_blocks_and_missing_search_index_warns(site_dir):
    report = launch(site_dir)
    assert any("public/og-default.png is missing" in b for b in report.blockers)
    assert any("No search index in dist/" in w for w in report.warnings)


def test_built_search_index_and_social_image_clear_both(site_dir):
    write(site_dir, "public/og-default.png", "not really a picture")
    write(site_dir, "dist/pagefind/pagefind-ui.js", "// built")
    report = launch(site_dir)
    assert not any("og-default.png" in b for b in report.blockers)
    assert not any("search index" in w for w in report.warnings)


def test_styleguide_page_blocks_launch(site_dir):
    write(site_dir, "src/pages/styleguide.astro", "---\n---\n")
    report = launch(site_dir)
    assert "src/pages/styleguide.astro is still present. Delete it before launch." in report.blockers


def test_legal_page_placeholders_are_warnings_and_drafts_block(site_dir):
    write(site_dir, "src/pages/privacy.astro", "Draft for review\nKept for [retention period], updated [date].\n")
    report = launch(site_dir)
    assert any("'Draft for review'" in b and "privacy.astro" in b for b in report.blockers)
    assert any("privacy.astro has 2 bracketed placeholder(s) to complete" in w for w in report.warnings)


def test_club_pointer_to_a_repository_is_a_warning(site_dir):
    write(site_dir, "src/config/site.ts", "export const robita = { url: 'https://github.com/robita-cir' };\n")
    report = launch(site_dir)
    assert any("student club pointer" in w for w in report.warnings)


def test_people_without_a_portrait_are_counted(site_dir):
    jane = site_dir / "src/content/people/jane-doe.md"
    jane.write_text(
        jane.read_text(encoding="utf-8").replace("---\n", '---\nphoto: "/people/jane.jpg"\n', 1), encoding="utf-8"
    )
    write(site_dir, "src/content/people/new-person.md", '---\nname: "New Person"\ngroup: "mtech"\n---\n')
    report = launch(site_dir)
    assert any("2 of 3 people entries have no portrait" in w for w in report.warnings)
