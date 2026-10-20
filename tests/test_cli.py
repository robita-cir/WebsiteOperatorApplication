from pathlib import Path

import pytest
from helpers import FakeLLM

from site_agent.apply import apply_plan
from site_agent.cli import main
from site_agent.config import SiteSettings
from site_agent.plan import FileChange, Plan
from site_agent.site import Site

ADD_REPLY = (
    '{"title": "Hands-on Perception Day", "kind": "workshop", "date": "2026-11-05",'
    ' "venue": "Lab 3, Example City", "summary": "A day of perception demos.", "body": "Open to all students.",'
    ' "sources": {"date": "5 November 2026", "venue": "Lab 3, Example City"}}'
)
NOTICE = "Hands-on Perception Day on 5 November 2026 in Lab 3, Example City. Open to all students."


@pytest.fixture
def notice(tmp_path: Path) -> Path:
    path = tmp_path / "notice.txt"
    path.write_text(NOTICE, encoding="utf-8")
    return path


def test_validate_passes_on_the_example_site(site_dir, capsys):
    assert main(["validate", "--site", str(site_dir)]) == 0
    assert "3 file(s) checked: 0 error(s)" in capsys.readouterr().out


def test_validate_fails_and_names_the_broken_field(site_dir, capsys):
    (site_dir / "src/content/events/event-2.md").write_text(
        '---\ntitle: "T"\nkind: "seminar"\ndate: 2026-05-06\n---\n', encoding="utf-8"
    )
    assert main(["validate", "--site", str(site_dir)]) == 1
    assert "event-2.md: kind:" in capsys.readouterr().out


def test_scan_lists_collections_and_sample_entries(site_dir, capsys):
    assert main(["scan", "--site", str(site_dir)]) == 0
    out = capsys.readouterr().out
    assert "events" in out and "validated" in out
    assert "not supported yet" in out
    assert "Sample entries still marked for replacement in events: 1" in out


def test_find_lists_mentions_and_refuses_very_short_text(site_dir, capsys):
    assert main(["find", "Robot Learning Workshop", "--site", str(site_dir)]) == 0
    out = capsys.readouterr().out
    assert "src/pages/index.astro:6:" in out
    assert "node_modules" not in out
    assert main(["find", "ok", "--site", str(site_dir)]) == 1


def test_add_event_without_apply_only_previews(site_dir, notice, capsys):
    before = sorted(p.name for p in (site_dir / "src/content/events").iterdir())
    code = main(["add-event", "--site", str(site_dir), "--from", str(notice)], client=FakeLLM(ADD_REPLY))
    assert code == 0
    assert "Dry run: nothing was written" in capsys.readouterr().out
    assert sorted(p.name for p in (site_dir / "src/content/events").iterdir()) == before


def test_add_event_with_apply_and_yes_writes_the_file(site_dir, notice, capsys):
    code = main(
        ["add-event", "--site", str(site_dir), "--from", str(notice), "--apply", "--yes"],
        client=FakeLLM(ADD_REPLY),
    )
    assert code == 0
    written = site_dir / "src/content/events/hands-on-perception-day.md"
    assert written.exists()
    assert main(["validate", "--site", str(site_dir)]) == 0
    assert "Written. Run id:" in capsys.readouterr().out


def test_apply_without_yes_or_a_terminal_refuses_to_write(site_dir, notice, capsys):
    code = main(
        ["add-event", "--site", str(site_dir), "--from", str(notice), "--apply"],
        client=FakeLLM(ADD_REPLY),
    )
    assert code == 1
    assert "--yes" in capsys.readouterr().err
    assert not (site_dir / "src/content/events/hands-on-perception-day.md").exists()


def test_update_then_restore_round_trip(site_dir, capsys):
    original = (site_dir / "src/content/news/next-up.md").read_bytes()
    llm = FakeLLM('{"date": "2026-04-14", "endDate": "2026-04-16"}')
    code = main(
        [
            "update-event",
            "robot learning workshop",
            "--site",
            str(site_dir),
            "--instruction",
            "Moved to 14 to 16 April 2026.",
            "--apply",
            "--yes",
        ],
        client=llm,
    )
    assert code == 0
    assert "14 April 2026" in (site_dir / "src/content/news/next-up.md").read_text(encoding="utf-8")

    run_id = next(
        line.split("Run id: ")[1].strip() for line in capsys.readouterr().out.splitlines() if "Run id:" in line
    )
    assert main(["restore", run_id, "--site", str(site_dir)]) == 0
    assert (site_dir / "src/content/news/next-up.md").read_bytes() == original


def test_bad_config_key_is_reported_not_ignored(site_dir, capsys):
    (site_dir / "site-agent.toml").write_text("[llm]\nmodle = 'typo'\n", encoding="utf-8")
    assert main(["scan", "--site", str(site_dir)]) == 1
    assert "unknown setting(s) in [llm]: modle" in capsys.readouterr().err


def test_an_update_with_a_model_edit_that_cannot_be_placed_writes_nothing(site_dir, capsys):
    (site_dir / "src/content/news/deadlines.md").write_text("<p>Save the date: 10 March 2026</p>\n", encoding="utf-8")
    event_before = (site_dir / "src/content/events/event-1.md").read_text(encoding="utf-8")
    deadlines_before = (site_dir / "src/content/news/deadlines.md").read_text(encoding="utf-8")
    bad_edit = "<<<<<<< SEARCH\nSave the date: 1 March 2026\n=======\nSave the date: 2 March 2026\n>>>>>>> REPLACE"
    code = main(
        [
            "update-event",
            "event-1",
            "--instruction",
            "The workshop moved to 14 April 2026 and now ends on 16 April 2026.",
            "--assisted",
            "--apply",
            "--yes",
            "--site",
            str(site_dir),
        ],
        client=FakeLLM('{"date": "2026-04-14", "endDate": "2026-04-16"}', bad_edit),
    )
    assert code == 1
    assert "Not written." in capsys.readouterr().out
    assert (site_dir / "src/content/events/event-1.md").read_text(encoding="utf-8") == event_before
    assert (site_dir / "src/content/news/deadlines.md").read_text(encoding="utf-8") == deadlines_before


def _update_run(site_dir, capsys, date_text):
    code = main(
        [
            "update-event",
            "robot learning workshop",
            "--site",
            str(site_dir),
            "--instruction",
            f"Moved to {date_text}.",
            "--apply",
            "--yes",
        ],
        client=FakeLLM('{"date": "2026-04-14", "endDate": "2026-04-16"}'),
    )
    assert code == 0
    out = capsys.readouterr().out
    return next(line.split("Run id: ")[1].strip() for line in out.splitlines() if "Run id:" in line)


def test_cli_restore_is_refused_when_a_later_run_edited_the_same_file(site_dir, capsys):
    news = site_dir / "src/content/news/next-up.md"
    first = _update_run(site_dir, capsys, "14 to 16 April 2026")
    # A second run on the same file, as a later approved change would be.
    site = Site(SiteSettings(root=site_dir))
    rel = "src/content/news/next-up.md"
    apply_plan(
        site,
        Plan(summary="later", changes=[FileChange(rel, site.read(rel), site.read(rel) + "\nLater note.\n")]),
        command="test",
        model="m",
    )
    after_later = news.read_bytes()

    assert main(["restore", first, "--site", str(site_dir)]) == 1
    err = capsys.readouterr().err
    assert "A later change" in err and "Undo that first" in err
    assert news.read_bytes() == after_later


def test_cli_restore_dry_run_lists_actions_and_changes_nothing(site_dir, capsys):
    news = site_dir / "src/content/news/next-up.md"
    run_id = _update_run(site_dir, capsys, "14 to 16 April 2026")
    written = news.read_bytes()

    assert main(["restore", run_id, "--site", str(site_dir), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "would restored src/content/news/next-up.md" in out
    assert news.read_bytes() == written
    # The run is still undoable afterwards, so the dry run did not mark it undone.
    assert main(["restore", run_id, "--site", str(site_dir)]) == 0


def test_cli_restore_dry_run_gives_the_same_refusal_as_a_real_undo(site_dir, capsys):
    run_id = _update_run(site_dir, capsys, "14 to 16 April 2026")
    (site_dir / "src/content/news/next-up.md").write_text("edited by hand\n", encoding="utf-8")
    assert main(["restore", run_id, "--site", str(site_dir), "--dry-run"]) == 1
    assert "has been edited since this change" in capsys.readouterr().err


def test_cli_restore_with_a_missing_backup_changes_nothing(site_dir, capsys):
    run_id = _update_run(site_dir, capsys, "14 to 16 April 2026")
    written = (site_dir / "src/content/news/next-up.md").read_bytes()
    for backup in (site_dir / ".site-agent" / "backups" / run_id).rglob("*.md"):
        backup.unlink()
    assert main(["restore", run_id, "--site", str(site_dir)]) == 1
    assert "backup" in capsys.readouterr().err
    assert (site_dir / "src/content/news/next-up.md").read_bytes() == written
