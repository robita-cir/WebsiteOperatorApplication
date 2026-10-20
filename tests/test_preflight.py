import json
import os
import sys
from urllib.parse import unquote

import pytest

from site_agent.apply import apply_plan, state_dir
from site_agent.config import SiteSettings
from site_agent.plan import FileChange, Plan
from site_agent.preflight import SKIPPED_REASON, run_preflight
from site_agent.site import Site

# Fails when a file named BAD exists in the folder it runs in, which is how the tests make a check fail.
CHECK = f'"{sys.executable}" -c "import os, sys; sys.exit(1 if os.path.exists(\'BAD\') else 0)"'
# Fails when the file the plan removes is still there.
CHECK_GONE = (
    f'"{sys.executable}" -c "import os, sys; sys.exit(1 if os.path.exists(\'src/content/news/next-up.md\') else 0)"'
)


@pytest.fixture
def site(site_dir):
    return Site(SiteSettings(root=site_dir, writable=["src/content/**/*.md", "BAD"]))


def _add(rel, text="x\n"):
    return Plan(summary="test", changes=[FileChange(rel, None, text)])


def _snapshot(root):
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and ".site-agent" not in p.parts
    }


def test_a_passing_check_on_the_copy_lets_the_change_proceed(site):
    plan = _add("src/content/events/new-one.md", '---\ntitle: "New"\n---\n')
    result = run_preflight(site, plan, CHECK, state_dir(site))
    assert result.status == "passed"
    apply_plan(site, plan, command="test", model="m")
    assert site.exists("src/content/events/new-one.md")


def test_a_failing_check_on_the_copy_is_reported_and_the_real_site_is_unchanged(site, site_dir):
    before = _snapshot(site_dir)
    result = run_preflight(site, _add("BAD"), CHECK, state_dir(site))
    assert result.status == "failed"
    assert _snapshot(site_dir) == before
    assert not (site_dir / "BAD").exists()


def test_the_check_output_is_returned(site):
    command = f'"{sys.executable}" -c "import sys; print(\'broken page\'); sys.exit(1)"'
    result = run_preflight(site, _add("src/content/events/a.md"), command, state_dir(site))
    assert result.status == "failed"
    assert "broken page" in result.output


def test_the_copy_is_removed_afterwards(site):
    run_preflight(site, _add("BAD"), CHECK, state_dir(site))
    run_preflight(site, _add("src/content/events/a.md"), CHECK, state_dir(site))
    assert list((state_dir(site) / "preflight").iterdir()) == []


def test_the_copy_leaves_out_state_and_build_folders(site, site_dir):
    (site_dir / "dist").mkdir()
    (site_dir / "dist" / "old.html").write_text("old", encoding="utf-8")
    (site_dir / ".site-agent").mkdir(exist_ok=True)
    command = (
        f'"{sys.executable}" -c "import os, sys; '
        "sys.exit(1 if any(os.path.exists(p) for p in ('dist', '.site-agent', '.git', '.astro')) else 0)\""
    )
    assert run_preflight(site, _add("src/content/events/a.md"), command, state_dir(site)).status == "passed"


def test_node_modules_is_linked_not_copied_and_the_real_one_survives(site, site_dir):
    modules = site_dir / "node_modules"
    modules.mkdir(exist_ok=True)
    (modules / "pkg.txt").write_text("kept", encoding="utf-8")
    command = f'"{sys.executable}" -c "import os, sys; sys.exit(0 if os.path.islink(\'node_modules\') else 1)"'
    result = run_preflight(site, _add("src/content/events/a.md"), command, state_dir(site))
    assert result.status == "passed"
    assert (modules / "pkg.txt").read_text(encoding="utf-8") == "kept"


def test_a_link_that_cannot_be_made_skips_the_preflight_and_removes_the_copy(site, site_dir, monkeypatch):
    assert (site_dir / "node_modules").is_dir()

    def refuse(*args, **kwargs):
        raise OSError("no symbolic links here")

    monkeypatch.setattr(os, "symlink", refuse)
    result = run_preflight(site, _add("BAD"), CHECK, state_dir(site))
    assert result.status == "skipped"
    assert result.reason == SKIPPED_REASON
    assert list((state_dir(site) / "preflight").iterdir()) == []


def test_a_removal_is_applied_to_the_copy_only(site, site_dir):
    rel = "src/content/news/next-up.md"
    plan = Plan(summary="test", changes=[FileChange(rel, site.read(rel), None)])
    before = _snapshot(site_dir)
    assert run_preflight(site, plan, CHECK_GONE, state_dir(site)).status == "passed"
    assert _snapshot(site_dir) == before
    assert (site_dir / rel).exists()


def test_paths_the_plan_may_not_write_are_not_touched_on_the_copy(site):
    # Page files are never written by the agent, so the copy must not gain one either.
    command = _failing_when("src/pages/extra.astro")
    assert run_preflight(site, _add("src/pages/extra.astro"), command, state_dir(site)).status == "passed"


def _failing_when(rel):
    return f'"{sys.executable}" -c "import os, sys; sys.exit(1 if os.path.exists(\'{rel}\') else 0)"'


def test_the_command_line_refuses_to_write_when_the_check_fails_on_the_copy(site_dir, capsys):
    from helpers import FakeLLM

    from site_agent.cli import main

    rel = "src/content/events/lab-talk.md"
    (site_dir / "site-agent.toml").write_text(
        f"[site]\ncheck_command = {json.dumps(_failing_when(rel))}\n", encoding="utf-8"
    )
    notice = site_dir.parent / "notice.txt"
    notice.write_text("Talk on 5 November 2026 in Lab 3, Example City.", encoding="utf-8")
    reply = '{"title": "Lab Talk", "kind": "talk", "date": "2026-11-05", "venue": "Lab 3, Example City"}'
    code = main(
        ["add-event", "--site", str(site_dir), "--from", str(notice), "--apply", "--yes"], client=FakeLLM(reply)
    )
    assert code == 1
    assert "Not written. The site check failed on a copy with these changes." in capsys.readouterr().out
    assert not (site_dir / rel).exists()
    assert not (site_dir / ".site-agent" / "runs").exists()


def _web_client(site_dir, command):
    from fastapi.testclient import TestClient
    from helpers import FakeLLM

    from site_agent.web.app import create_app

    (site_dir / "site-agent.toml").write_text(f"[site]\ncheck_command = {json.dumps(command)}\n", encoding="utf-8")
    client = TestClient(create_app(site_dir, llm=FakeLLM(), inline_jobs=True))
    client.get("/")
    token = client.cookies.get("sa_csrf", "")
    settings = {"csrf": token, "operator_name": "Pat Operator", "approvers": "Dr Approver | Head"}
    client.post("/settings", data=settings)
    form = {
        "name": "Ravi Kumar",
        "group": "scholar",
        "role": "Research scholar",
        "dept": "",
        "interests": "Grasping",
        "homepage": "",
        "photo": "",
        "order": "100",
        "body": "Ravi studies grasping.",
        "facts": "",
        "action": "preview",
    }
    response = client.post("/c/people/new", data={"csrf": token, **form}, follow_redirects=False)
    pid = response.headers["location"].rsplit("/", 1)[-1]

    def approve():
        data = {"csrf": token, "approver": "Dr Approver", "statement": "on"}
        return client.post(f"/preview/{pid}/approve", data=data, follow_redirects=False)

    return client, approve


def test_the_approve_route_writes_nothing_when_the_check_fails_on_the_copy(site_dir):
    rel = "src/content/people/ravi-kumar.md"
    client, approve = _web_client(site_dir, _failing_when(rel))
    response = approve()
    assert "nothing was written" in unquote(response.headers["location"])
    assert not (site_dir / rel).exists()
    assert not (site_dir / ".site-agent" / "runs").exists()
    assert "failed" in client.get("/check").text.lower()


def test_the_approve_route_writes_when_the_check_passes_on_the_copy(site_dir):
    _, approve = _web_client(site_dir, _failing_when("BAD"))
    response = approve()
    assert response.headers["location"].startswith("/jobs/")
    assert (site_dir / "src/content/people/ravi-kumar.md").exists()
