"""A file with both Windows and Unix line endings is refused, because which style to write back would be a guess."""

import pytest

from site_agent.apply import apply_plan
from site_agent.config import SiteSettings
from site_agent.records import SPECS
from site_agent.repository import MIXED_ENDINGS, Repository
from site_agent.site import Site

NEWS = "src/content/news/next-up.md"
BLOCKER = (
    "This file mixes Windows and Unix line endings, so a change cannot be made safely. "
    "Fix the file's line endings by hand, then try again."
)


@pytest.fixture
def site(site_dir) -> Site:
    return Site(SiteSettings(root=site_dir))


def _form(site: Site, **changes) -> dict:
    record = Repository(site).load(SPECS["news"], "next-up")
    form = {"title": "Next up", "kind": "news", "date": "2026-02-20", "summary": "A new summary.", "body": record.body}
    return form | changes


def _mix(site_dir) -> bytes:
    path = site_dir / NEWS
    data = path.read_bytes().replace(b"\r\n", b"\n")
    first, rest = data.split(b"\n", 1)
    data = first + b"\r\n" + rest  # one Windows ending among Unix ones
    path.write_bytes(data)
    return data


def test_the_blocker_text_is_the_agreed_sentence():
    assert MIXED_ENDINGS == BLOCKER


def test_a_mixed_file_is_refused_and_left_unchanged(site, site_dir):
    mixed = _mix(site_dir)
    outcome = Repository(site).update(SPECS["news"], "next-up", _form(site))
    assert outcome.plan is None and not outcome.ok
    assert outcome.blockers == [BLOCKER]
    assert (site_dir / NEWS).read_bytes() == mixed


def test_a_mixed_file_is_refused_even_when_nothing_else_changes(site, site_dir):
    _mix(site_dir)
    outcome = Repository(site).update(
        SPECS["news"], "next-up", _form(site, summary="The next workshop is almost here.")
    )
    assert BLOCKER in outcome.blockers and outcome.plan is None


def test_a_crlf_file_still_works(site, site_dir):
    path = site_dir / NEWS
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    outcome = Repository(site).update(SPECS["news"], "next-up", _form(site))
    assert outcome.plan is not None and BLOCKER not in outcome.blockers
    apply_plan(site, outcome.plan, command="test", model="m")
    written = path.read_bytes()
    assert written.count(b"\r\n") == written.count(b"\n")


def test_an_lf_file_still_works(site, site_dir):
    assert b"\r" not in (site_dir / NEWS).read_bytes()
    outcome = Repository(site).update(SPECS["news"], "next-up", _form(site))
    assert outcome.plan is not None and BLOCKER not in outcome.blockers


def test_a_new_file_is_not_affected(site):
    raw = {"title": "Fresh", "kind": "news", "date": "2026-03-01", "summary": "Summary.", "body": "A.\r\nB.\nC."}
    outcome = Repository(site).create(SPECS["news"], raw)
    assert outcome.plan is not None and BLOCKER not in outcome.blockers
