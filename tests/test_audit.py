"""The audit report and the `site-agent audit` command."""

import datetime as dt

from site_agent.audit import run_audit
from site_agent.cli import main
from site_agent.config import SiteSettings
from site_agent.site import Site

NOW = dt.datetime(2026, 10, 20, 9, 30, 5)


def snapshot(site_dir):
    """Every file's bytes except the state folder, so a change to any content file shows."""
    return {
        path.relative_to(site_dir).as_posix(): path.read_bytes()
        for path in sorted(site_dir.rglob("*"))
        if path.is_file() and ".site-agent" not in path.parts
    }


def test_the_audit_writes_a_report_and_changes_no_content_file(site_dir):
    before = snapshot(site_dir)
    result = run_audit(Site(SiteSettings(root=site_dir)), now=NOW)
    assert snapshot(site_dir) == before
    assert result.report_path == site_dir / ".site-agent/audits/20261020-093005.md"
    assert result.report_path.read_text(encoding="utf-8") == result.text
    assert result.exit_code == 0


def test_the_report_says_which_date_it_used(site_dir):
    result = run_audit(Site(SiteSettings(root=site_dir)), now=NOW)
    assert "today's date on this machine: 2026-10-20" in result.text
    assert "| events | 3 | 1 |" in result.text


def test_the_audit_lists_the_reference_warning_for_the_project(site_dir):
    result = run_audit(Site(SiteSettings(root=site_dir)))
    expected = (
        'src/content/projects/grasp-learning.md: "Alex Unknown" is not on the People list, '
        "so the name will not link to a profile."
    )
    assert expected in result.warnings
    assert "Alex Unknown" in result.text


def test_the_audit_lists_the_date_checks_and_placeholders(site_dir):
    result = run_audit(Site(SiteSettings(root=site_dir)), now=NOW)
    assert any("ended on 12 March 2026" in w for w in result.warnings)
    assert any("Next up says it is coming up" in w for w in result.warnings)
    # The sample entries hold placeholders on purpose, so they are listed but are not warnings.
    assert any(is_sample for *_, is_sample in result.placeholders)
    assert not any("events/sample-talk.md" in w and "placeholder wording" in w for w in result.warnings)
    # Wording in an entry that is not marked as a sample is a warning.
    assert any("people/jane-doe.md line 7: placeholder wording (example.org)" in w for w in result.warnings)


def test_a_content_error_gives_exit_code_1(site_dir):
    (site_dir / "src/content/events/event-2.md").write_text(
        '---\ntitle: "T"\nkind: "seminar"\ndate: 2026-05-06\n---\n', encoding="utf-8"
    )
    before = snapshot(site_dir)
    result = run_audit(Site(SiteSettings(root=site_dir)))
    assert result.exit_code == 1
    assert any("event-2.md" in e for e in result.errors)
    assert snapshot(site_dir) == before


def test_a_missing_file_a_record_points_at_is_an_error(site_dir):
    (site_dir / "public/documents/annual-report.pdf").unlink()
    result = run_audit(Site(SiteSettings(root=site_dir)))
    assert result.exit_code == 1


def test_two_audits_in_one_second_keep_both_reports(site_dir):
    site = Site(SiteSettings(root=site_dir))
    first, second = run_audit(site, now=NOW), run_audit(site, now=NOW)
    assert first.report_path != second.report_path
    assert first.report_path.exists() and second.report_path.exists()


def test_the_command_prints_a_summary_and_the_report_path(site_dir, capsys):
    before = snapshot(site_dir)
    assert main(["audit", "--site", str(site_dir)]) == 0
    out = capsys.readouterr().out
    assert "Audit done: 0 error(s)" in out
    assert "Alex Unknown" in out
    assert "Report: " in out and ".site-agent" in out
    assert len(list((site_dir / ".site-agent/audits").glob("*.md"))) == 1
    assert snapshot(site_dir) == before


def test_the_command_exits_1_when_there_are_errors(site_dir, capsys):
    (site_dir / "src/content/events/event-2.md").write_text("no frontmatter", encoding="utf-8")
    assert main(["audit", "--site", str(site_dir)]) == 1
    assert "error" in capsys.readouterr().out
