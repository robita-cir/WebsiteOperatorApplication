"""A file keeps its own line endings when a change is written, and a restore gives back the exact bytes."""

from pathlib import Path

import pytest

from site_agent.apply import apply_plan, restore_run
from site_agent.config import SiteSettings
from site_agent.frontmatter import parse_document, set_body, set_frontmatter_values
from site_agent.records import SPECS
from site_agent.repository import Repository
from site_agent.site import Site

NEWS = "src/content/news/next-up.md"
RAW = {"title": "Next up", "kind": "news", "date": "2026-02-20", "summary": "A new summary.", "body": ""}


@pytest.fixture
def site(site_dir: Path) -> Site:
    return Site(SiteSettings(root=site_dir))


def _as_crlf(site_dir: Path, rel: str = NEWS) -> bytes:
    path = site_dir / rel
    data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    path.write_bytes(data)
    return data


def _form_for(site: Site) -> dict:
    record = Repository(site).load(SPECS["news"], "next-up")
    return {**RAW, "body": record.body}


def test_read_returns_the_text_as_it_is_on_disk(site, site_dir):
    original = _as_crlf(site_dir)
    assert site.read(NEWS) == original.decode("utf-8")
    assert "\r\n" in site.read(NEWS)


def test_write_does_not_convert_endings(site, site_dir):
    site.write(NEWS, "a\r\nb\nc\r\n")
    assert (site_dir / NEWS).read_bytes() == b"a\r\nb\nc\r\n"


def test_a_crlf_file_edited_through_the_repository_keeps_crlf_on_disk(site, site_dir):
    original = _as_crlf(site_dir)
    repo = Repository(site)
    outcome = repo.update(SPECS["news"], "next-up", {**_form_for(site), "summary": "A new summary."})
    assert outcome.plan is not None
    after = outcome.plan.changes[0].after
    assert after is not None and after.count("\r\n") == after.count("\n")  # every line break is CRLF

    apply_plan(site, outcome.plan, command="test", model="m")
    written = (site_dir / NEWS).read_bytes()
    assert b'summary: "A new summary."' in written
    assert written.count(b"\r\n") == written.count(b"\n") and written.count(b"\r\n") > 0
    assert written != original


def test_a_changed_body_in_a_crlf_file_is_written_with_crlf_even_from_a_browser_text_box(site, site_dir):
    _as_crlf(site_dir)
    form = {**_form_for(site), "body": "First line.\r\n\r\nSecond line."}  # a browser sends CRLF in a text box
    outcome = Repository(site).update(SPECS["news"], "next-up", form)
    assert outcome.plan is not None
    apply_plan(site, outcome.plan, command="test", model="m")
    written = (site_dir / NEWS).read_bytes()
    assert b"\r\r" not in written
    assert written.count(b"\r\n") == written.count(b"\n")
    assert written.endswith(b"First line.\r\n\r\nSecond line.\r\n")


def test_the_backup_of_a_crlf_file_restores_the_original_bytes(site, site_dir):
    original = _as_crlf(site_dir)
    outcome = Repository(site).update(SPECS["news"], "next-up", {**_form_for(site), "summary": "A new summary."})
    assert outcome.plan is not None
    result = apply_plan(site, outcome.plan, command="test", model="m")
    assert (site_dir / NEWS).read_bytes() != original
    assert (result.backup_dir / NEWS).read_bytes() == original

    restore_run(site, result.run_id)
    assert (site_dir / NEWS).read_bytes() == original


def test_the_file_check_in_apply_still_matches_a_crlf_file(site, site_dir):
    _as_crlf(site_dir)
    outcome = Repository(site).update(SPECS["news"], "next-up", {**_form_for(site), "summary": "Changed."})
    assert outcome.plan is not None
    assert outcome.plan.changes[0].before == site.read(NEWS)
    apply_plan(site, outcome.plan, command="test", model="m")  # raises if the before text did not match


def test_an_unchanged_crlf_file_is_reported_as_nothing_to_save(site, site_dir):
    _as_crlf(site_dir)
    outcome = Repository(site).update(
        SPECS["news"], "next-up", _form_for(site) | {"summary": "The next workshop is almost here."}
    )
    assert outcome.plan is None
    assert any("Nothing has changed" in w for w in outcome.warnings)


def test_an_lf_file_stays_lf(site, site_dir):
    original = (site_dir / NEWS).read_bytes()
    assert b"\r" not in original
    outcome = Repository(site).update(SPECS["news"], "next-up", {**_form_for(site), "summary": "A new summary."})
    assert outcome.plan is not None
    apply_plan(site, outcome.plan, command="test", model="m")
    written = (site_dir / NEWS).read_bytes()
    assert b'summary: "A new summary."' in written and b"\r" not in written


def test_a_new_file_is_written_with_lf(site, site_dir):
    raw = {
        "title": "Fresh",
        "kind": "news",
        "date": "2026-03-01",
        "summary": "Summary.",
        "body": "Line one.\r\nLine two.",
    }
    outcome = Repository(site).create(SPECS["news"], raw)
    assert outcome.plan is not None
    apply_plan(site, outcome.plan, command="test", model="m")
    assert b"\r" not in (site_dir / "src/content/news/fresh.md").read_bytes()


def test_frontmatter_functions_accept_crlf_text_and_return_it_in_crlf():
    text = '---\r\ntitle: "A"\r\nkind: "news"\r\n---\r\n\r\nBody.\r\n'
    doc = parse_document(text)
    assert doc.data["title"] == "A" and doc.body == "Body.\n"
    changed = set_frontmatter_values(text, {"title": "B"})
    assert changed == '---\r\ntitle: "B"\r\nkind: "news"\r\n---\r\n\r\nBody.\r\n'
    assert set_frontmatter_values(text, {}) == text
    assert set_body(text, "New body.") == '---\r\ntitle: "A"\r\nkind: "news"\r\n---\r\n\r\nNew body.\r\n'
    assert set_body(text, "Body.") == text
