import pytest

from site_agent.apply import apply_plan, restore_run
from site_agent.config import SiteSettings
from site_agent.errors import SiteAgentError
from site_agent.plan import FileChange, Plan
from site_agent.site import Site


@pytest.fixture
def site(site_dir):
    return Site(SiteSettings(root=site_dir))


def _plan(site, rel, new_text):
    before = site.read(rel) if site.exists(rel) else None
    return Plan(summary="test", changes=[FileChange(rel, before, new_text)])


def test_apply_writes_backs_up_and_logs_then_restore_undoes_it(site, site_dir):
    original = (site_dir / "src/content/news/next-up.md").read_bytes()
    plan = Plan(
        summary="test",
        changes=[
            FileChange("src/content/news/next-up.md", site.read("src/content/news/next-up.md"), "changed\n"),
            FileChange("src/content/events/new-one.md", None, '---\ntitle: "New"\n---\n'),
        ],
    )
    result = apply_plan(site, plan, command="test", model="m")

    assert (site_dir / "src/content/news/next-up.md").read_text(encoding="utf-8") == "changed\n"
    assert (site_dir / "src/content/events/new-one.md").exists()
    assert (result.backup_dir / "src/content/news/next-up.md").read_bytes() == original
    assert (site_dir / ".site-agent" / "runs" / f"{result.run_id}.json").exists()

    actions = restore_run(site, result.run_id)
    assert set(actions) == {("restored", "src/content/news/next-up.md"), ("removed", "src/content/events/new-one.md")}
    assert (site_dir / "src/content/news/next-up.md").read_bytes() == original
    assert not (site_dir / "src/content/events/new-one.md").exists()


def test_apply_refuses_paths_outside_the_allow_list(site, site_dir):
    plan = _plan(site, "node_modules/left-pad/index.js", "changed")
    with pytest.raises(SiteAgentError, match="not in the paths"):
        apply_plan(site, plan, command="test", model="m")
    assert "Robot Learning" in (site_dir / "node_modules/left-pad/index.js").read_text(encoding="utf-8")


def test_apply_refuses_a_file_that_changed_after_planning(site, site_dir):
    plan = _plan(site, "src/content/news/next-up.md", "changed\n")
    (site_dir / "src/content/news/next-up.md").write_text("someone else edited this\n", encoding="utf-8")
    with pytest.raises(SiteAgentError, match="changed after the plan"):
        apply_plan(site, plan, command="test", model="m")
    assert (site_dir / "src/content/news/next-up.md").read_text(encoding="utf-8") == "someone else edited this\n"


def test_restore_of_an_unknown_run_is_a_clear_error(site):
    with pytest.raises(SiteAgentError, match="no run called"):
        restore_run(site, "19990101-000000")


def test_run_check_reports_success_and_failure(tmp_path):
    import sys

    from site_agent.apply import run_check

    python = f'"{sys.executable}"'
    assert run_check(f"{python} -c \"print('fine')\"", tmp_path).ok
    failed = run_check(f"{python} -c \"import sys; print('broken build'); sys.exit(2)\"", tmp_path)
    assert not failed.ok and "broken build" in failed.output


def test_failed_check_after_apply_says_how_to_undo(site, site_dir, capsys):
    import sys

    from helpers import FakeLLM

    from site_agent.cli import main

    (site_dir / "site-agent.toml").write_text(
        f'[site]\ncheck_command = "\\"{sys.executable}\\" -c \\"import sys; sys.exit(3)\\""\n', encoding="utf-8"
    )
    notice = site_dir.parent / "notice.txt"
    notice.write_text("Talk on 5 November 2026 in Lab 3, Example City.", encoding="utf-8")
    reply = '{"title": "Lab Talk", "kind": "talk", "date": "2026-11-05", "venue": "Lab 3, Example City"}'
    code = main(
        ["add-event", "--site", str(site_dir), "--from", str(notice), "--apply", "--yes"],
        client=FakeLLM(reply),
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "The check failed. The changes are still written." in out
    assert (site_dir / "src/content/events/lab-talk.md").exists()
