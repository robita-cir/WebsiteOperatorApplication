"""Launch readiness checks. Each one matches a rule in the template's own launch check (scripts/launch-check.mjs)."""

from fastapi.testclient import TestClient
from helpers import FakeLLM

from site_agent.appstate import AppState
from site_agent.config import SiteSettings
from site_agent.launch import _MARKER_PATTERNS, launch_report
from site_agent.repository import Repository
from site_agent.site import Site
from site_agent.web.app import create_app


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


def notes(items):
    return {str(item): (item.link, item.owner) for item in items}


def test_note_is_a_string_with_a_link_and_an_owner(site_dir):
    report = launch(site_dir)
    note = next(b for b in report.blockers if "og-default.png" in b)
    assert isinstance(note, str)
    assert note.owner == "technical contact"
    assert note.link is None


def test_each_blocker_and_warning_names_where_and_who(site_dir):
    write(site_dir, "src/pages/styleguide.astro", "---\n---\n")
    write(site_dir, "src/pages/privacy.astro", "Draft for review\nKept for [retention period].\n")
    write(site_dir, "src/config/site.ts", "export const site = { name: 'Institute name' };\n")
    report = launch(site_dir)
    blockers = notes(report.blockers)
    warnings = notes(report.warnings)

    def only(found, text):
        (match,) = [value for key, value in found.items() if text in key]
        return match

    assert only(blockers, "sample entries are still on the site") == ("/samples", "operator")
    assert only(blockers, "styleguide.astro is still present") == (None, "technical contact")
    assert only(blockers, "'Draft for review'") == (None, "institute")
    assert only(blockers, "site settings file still has placeholder") == (None, "technical contact")
    assert only(blockers, "og-default.png is missing") == (None, "technical contact")
    assert only(warnings, "privacy.astro has 1 bracketed") == (None, "institute")
    assert only(warnings, "site check has not been run") == ("/check", "operator")
    assert only(warnings, "No search index") == (None, "technical contact")
    assert only(warnings, "people entries have no portrait") == ("/c/people", "operator")


def test_a_failed_check_links_to_the_check_screen(site_dir):
    AppState(Site(SiteSettings(root=site_dir))).save_check({"ok": False, "time": "now"})
    report = launch(site_dir)
    failed = next(b for b in report.blockers if "last site check did not pass" in b)
    assert (failed.link, failed.owner) == ("/check", "operator")


def test_placeholder_words_in_content_link_to_samples(site_dir):
    write(site_dir, "src/content/people/loose.md", '---\nname: "Loose"\ngroup: "mtech"\n---\nPlaceholder biography.\n')
    report = launch(site_dir)
    loose = next(w for w in report.warnings if "not marked as a sample" in w)
    assert (loose.link, loose.owner) == ("/samples", "operator")


def test_markers_match_regardless_of_case():
    hit_texts = ["partner 7", "COUNTRY NAME", "amount PLACEHOLDER", "facility type", "[sample] title", "Sample Answer"]
    for text in hit_texts:
        assert any(p.search(text) for _, p in _MARKER_PATTERNS), text
    assert not any(p.search('<input placeholder="Search">') for _, p in _MARKER_PATTERNS)
    assert not any(p.search("input::placeholder { color: grey }") for _, p in _MARKER_PATTERNS)


def test_marker_in_a_page_is_a_warning_and_not_a_blocker(site_dir):
    before = launch(site_dir)
    write(site_dir, "src/pages/about.astro", "<p>PLACEHOLDER headline</p>\n<p>Partner 3, country name</p>\n")
    write(site_dir, "src/config/nav.ts", "export const x = 'sample answer';\n")
    report = launch(site_dir)
    page_warning = next(w for w in report.warnings if "in the site pages" in w)
    assert page_warning == "3 placeholder words are in the site pages. The technical contact edits those files."
    assert page_warning.owner == "technical contact"
    assert list(report.blockers) == list(before.blockers)


def test_page_scan_skips_unreadable_files(site_dir):
    (site_dir / "src/pages").mkdir(parents=True, exist_ok=True)
    (site_dir / "src/pages/binary.astro").write_bytes(b"\xff\xfe\x00 placeholder \x80")
    write(site_dir, "src/pages/ok.astro", "<p>fine</p>\n")
    report = launch(site_dir)
    assert not any("in the site pages" in w for w in report.warnings)


def test_a_sample_entry_in_content_still_blocks(site_dir):
    write(
        site_dir,
        "src/content/people/draft.md",
        '---\nname: "Professor 1"\ngroup: "mtech"\nsample: true\n---\nPlaceholder\n',
    )
    report = launch(site_dir)
    assert any("sample entries are still on the site" in b for b in report.blockers)
    assert not any("people/draft.md" in w for w in report.warnings)


def test_launch_page_shows_fix_links_and_owners(site_dir):
    client = TestClient(create_app(site_dir, llm=FakeLLM(), inline_jobs=True))
    page = client.get("/launch").text
    assert 'href="/samples">Fix it</a>' in page
    assert 'href="/check">Fix it</a>' in page
    assert 'href="/c/people">Fix it</a>' in page
    assert "Who fixes it: technical contact." in page
    assert "Who fixes it: operator." in page
