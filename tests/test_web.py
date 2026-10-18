"""The operator app, end to end, through its HTTP routes. Each test works on a fresh copy of the example site.

The model is a scripted fake, and background work runs inline, so the tests are fast and never need a model server.
"""

import html
import json
import sys
from pathlib import Path
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient
from helpers import FakeLLM

from site_agent.records import SPECS
from site_agent.web.app import create_app

APPROVER = "Dr Example Approver"


@pytest.fixture
def make_client(site_dir: Path):
    def build(llm=None, check_command: str | None = None) -> TestClient:
        if check_command:
            (site_dir / "site-agent.toml").write_text(
                f"[site]\ncheck_command = {json.dumps(check_command)}\n", encoding="utf-8"
            )
        app = create_app(site_dir, llm=llm or FakeLLM(), inline_jobs=True)
        client = TestClient(app)
        client.get("/")  # sets the form token cookie
        return client

    return build


def csrf(client: TestClient) -> str:
    return client.cookies.get("sa_csrf", "")


def set_up_operator(client: TestClient) -> None:
    client.post(
        "/settings",
        data={"csrf": csrf(client), "operator_name": "Pat Operator", "approvers": f"{APPROVER} | Head of centre"},
    )


def person_form(**overrides) -> dict:
    data = {
        "name": "Ravi Kumar",
        "group": "scholar",
        "role": "Research scholar",
        "dept": "",
        "interests": "Grasping\nLearning",
        "homepage": "",
        "photo": "",
        "order": "100",
        "body": "Ravi studies grasping.",
        "facts": "",
        "action": "preview",
    }
    data.update(overrides)
    return data


def preview_id(location: str) -> str:
    assert location.startswith("/preview/"), location
    return location.rsplit("/", 1)[-1]


def test_every_collection_page_renders(make_client):
    client = make_client()
    for key, spec in SPECS.items():
        assert client.get(f"/c/{key}").status_code == 200, key
        if spec.can_add:
            assert client.get(f"/c/{key}/new").status_code == 200, key
    assert client.get("/c/research/new").status_code == 404
    assert client.get("/c/unknown").status_code == 404
    for key in ("people", "events", "projects"):
        ids = [i["id"] for i in client.get(f"/api/{key}").json()]
        assert ids, key
        for rec_id in ids:
            assert client.get(f"/c/{key}/{rec_id}").status_code == 200, (key, rec_id)


def test_add_a_person_is_previewed_approved_written_and_undone(make_client, site_dir):
    client = make_client()
    set_up_operator(client)
    response = client.post("/c/people/new", data={"csrf": csrf(client), **person_form()}, follow_redirects=False)
    assert response.status_code == 303
    pid = preview_id(response.headers["location"])

    page = client.get(f"/preview/{pid}").text
    assert "A new person will be added: Ravi Kumar." in page
    assert "Nothing is saved yet" in page
    target = site_dir / "src/content/people/ravi-kumar.md"
    assert not target.exists()

    refused = client.post(
        f"/preview/{pid}/approve", data={"csrf": csrf(client), "approver": APPROVER}, follow_redirects=False
    )
    assert "Tick the statement" in unquote(refused.headers["location"])
    assert not target.exists()

    approved = client.post(
        f"/preview/{pid}/approve",
        data={"csrf": csrf(client), "approver": APPROVER, "statement": "on"},
        follow_redirects=False,
    )
    assert approved.status_code == 303 and approved.headers["location"].startswith("/history")
    assert target.exists()
    assert 'name: "Ravi Kumar"' in target.read_text(encoding="utf-8")

    history = client.get("/history").text
    assert "Undo this change" in history
    assert APPROVER in history and "Pat Operator" in history
    run_undo = next(line for line in history.splitlines() if "/undo" in line)
    run_id = run_undo.split("/history/")[1].split("/undo")[0]
    client.post(f"/history/{run_id}/undo", data={"csrf": csrf(client)})
    assert not target.exists()


def test_approval_needs_an_approver_and_the_operator_name(make_client):
    client = make_client()
    response = client.post("/c/people/new", data={"csrf": csrf(client), **person_form()}, follow_redirects=False)
    pid = preview_id(response.headers["location"])
    page = client.get(f"/preview/{pid}").text
    assert "Enter your name in" in page
    assert "No approvers are listed" in page
    result = client.post(
        f"/preview/{pid}/approve",
        data={"csrf": csrf(client), "approver": APPROVER, "statement": "on"},
        follow_redirects=False,
    )
    assert "Enter your name in Settings" in unquote(result.headers["location"])


def test_invalid_input_stays_on_the_form_with_plain_messages(make_client):
    client = make_client()
    response = client.post(
        "/c/people/new",
        data={"csrf": csrf(client), **person_form(homepage="http://example.org/ravi", name="")},
    )
    assert response.status_code == 422
    assert "must start with https://" in response.text
    assert "Name is required." in response.text


def test_a_change_made_after_the_preview_is_refused(make_client, site_dir):
    client = make_client()
    set_up_operator(client)
    response = client.post(
        "/c/people/jane-doe",
        data={"csrf": csrf(client), **person_form(name="Jane Doe", group="faculty", role="Head")},
        follow_redirects=False,
    )
    pid = preview_id(response.headers["location"])
    (site_dir / "src/content/people/jane-doe.md").write_text(
        '---\nname: "Someone else"\ngroup: "faculty"\n---\n', encoding="utf-8"
    )
    result = client.post(
        f"/preview/{pid}/approve",
        data={"csrf": csrf(client), "approver": APPROVER, "statement": "on"},
        follow_redirects=False,
    )
    assert "changed after the plan" in client.get(result.headers["location"]).text
    assert "Someone else" in (site_dir / "src/content/people/jane-doe.md").read_text(encoding="utf-8")


def test_removing_a_person_keeps_a_copy_for_undo_and_undo_restores_it(make_client, site_dir):
    client = make_client()
    set_up_operator(client)
    original = (site_dir / "src/content/people/jane-doe.md").read_bytes()
    response = client.post("/c/people/jane-doe/remove", data={"csrf": csrf(client)}, follow_redirects=False)
    pid = preview_id(response.headers["location"])
    assert "will be removed from the website" in client.get(f"/preview/{pid}").text
    client.post(
        f"/preview/{pid}/approve",
        data={"csrf": csrf(client), "approver": APPROVER, "statement": "on"},
        follow_redirects=False,
    )
    assert not (site_dir / "src/content/people/jane-doe.md").exists()
    run_id = next(
        line.split("/history/")[1].split("/undo")[0]
        for line in client.get("/history").text.splitlines()
        if "/undo" in line
    )
    client.post(f"/history/{run_id}/undo", data={"csrf": csrf(client)})
    assert (site_dir / "src/content/people/jane-doe.md").read_bytes() == original


def test_undo_refuses_when_the_file_was_edited_afterwards(make_client, site_dir):
    client = make_client()
    set_up_operator(client)
    response = client.post(
        "/c/people/jane-doe",
        data={"csrf": csrf(client), **person_form(name="Jane Doe", group="faculty", role="Head")},
        follow_redirects=False,
    )
    pid = preview_id(response.headers["location"])
    client.post(
        f"/preview/{pid}/approve",
        data={"csrf": csrf(client), "approver": APPROVER, "statement": "on"},
        follow_redirects=False,
    )
    (site_dir / "src/content/people/jane-doe.md").write_text('---\nname: "Later edit"\n---\n', encoding="utf-8")
    history = client.get("/history").text
    assert "has been edited since this change" in history
    assert "Undo this change" not in history


def test_an_older_change_cannot_be_undone_before_a_newer_one(make_client, site_dir):
    client = make_client()
    set_up_operator(client)
    for role in ("First role", "Second role"):
        response = client.post(
            "/c/people/jane-doe",
            data={"csrf": csrf(client), **person_form(name="Jane Doe", group="faculty", role=role)},
            follow_redirects=False,
        )
        pid = preview_id(response.headers["location"])
        client.post(
            f"/preview/{pid}/approve",
            data={"csrf": csrf(client), "approver": APPROVER, "statement": "on"},
            follow_redirects=False,
        )
    runs = [
        line.split("/history/")[1].split("/undo")[0]
        for line in client.get("/history").text.splitlines()
        if "/undo" in line
    ]
    assert len(runs) == 1, "only the newest change can be undone"


def test_draft_items_not_in_the_facts_block_saving_until_resolved(make_client):
    draft_text = "Ravi joined in 2019 and studies grasping."
    client = make_client(llm=FakeLLM(draft_text))
    response = client.post(
        "/c/people/new",
        data={"csrf": csrf(client), **person_form(body="", facts="Studies grasping.", action="draft:body")},
        follow_redirects=False,
    )
    job_page = client.get(response.headers["location"], follow_redirects=False)
    assert job_page.status_code == 303
    form = client.get(job_page.headers["location"]).text
    assert "Not in your facts" in form and "2019" in form
    draft_id = job_page.headers["location"].split("draft=")[1]

    blocked = client.post(
        "/c/people/new",
        data={"csrf": csrf(client), **person_form(body=draft_text, facts="Studies grasping.", draft_id=draft_id)},
    )
    assert blocked.status_code == 422
    assert 'mentions "2019"' in html.unescape(blocked.text)

    cleared = client.post(
        "/c/people/new",
        data={
            "csrf": csrf(client),
            **person_form(body=draft_text, facts="Studies grasping. Joined in 2019.", draft_id=draft_id),
        },
        follow_redirects=False,
    )
    assert cleared.status_code == 303


def test_notice_fills_the_event_form_for_checking(make_client):
    reply = (
        '{"title": "Hands-on Perception Day", "kind": "workshop", "series": null, "date": "2026-11-05",'
        ' "endDate": null, "venue": "Lab 3, Example City", "summary": "A day of demos.", "body": "Open to all."}'
    )
    client = make_client(llm=FakeLLM(reply))
    response = client.post(
        "/c/events/new",
        data={"csrf": csrf(client), "action": "notice", "notice": "Perception day on 5 November 2026 in Lab 3."},
        follow_redirects=False,
    )
    page = client.get(response.headers["location"]).text
    assert 'value="Hands-on Perception Day"' in page
    assert 'value="2026-11-05"' in page
    assert "Open to all." in page


def test_a_missing_photo_or_pdf_is_a_blocker(make_client):
    client = make_client()
    response = client.post(
        "/c/documents/new",
        data={
            "csrf": csrf(client),
            "title": "Policy",
            "kind": "policy",
            "description": "A policy.",
            "file": "/documents/not-uploaded.pdf",
            "order": "100",
            "action": "preview",
        },
    )
    assert response.status_code == 422
    assert "is not in the website's public folder" in html.unescape(response.text)


def test_posting_without_the_form_token_is_refused(make_client):
    client = make_client()
    response = client.post("/c/people/new", data=person_form())
    assert response.status_code == 403


def test_redirects_cannot_leave_the_site(make_client):
    client = make_client()
    response = client.get("/jobs/notajob?next=https://example.com", follow_redirects=False)
    assert response.headers["location"].startswith("/")
    assert "example.com" not in response.headers["location"].split("?")[0]


def test_site_check_runs_and_its_result_is_kept(make_client):
    command = f'"{sys.executable}" -c "print(\'built\')"'
    client = make_client(check_command=command)
    response = client.post("/check/run", data={"csrf": csrf(client)}, follow_redirects=False)
    assert response.status_code == 303
    page = client.get("/check").text
    assert "The check passed." in page
    assert "built" in page


def test_launch_report_lists_samples_and_references(make_client):
    client = make_client()
    page = client.get("/launch").text
    assert "sample entries are still on the site" in page
    assert "Not ready" in page
    assert "site check has not been run yet" in page


def test_references_warn_for_unknown_students_and_partners(site_dir):
    from site_agent.config import SiteSettings
    from site_agent.repository import Repository
    from site_agent.site import Site

    repo = Repository(Site(SiteSettings(root=site_dir)))
    project = SPECS["projects"]
    values = {"students": ["Sam Roe", "Nobody Known"]}
    _, warnings = repo.references(project, values)
    assert any("Nobody Known" in w for w in warnings)
    assert not any("Sam Roe" in w for w in warnings)
    funding = repo.references(SPECS["funding"], {"partner": "Missing Partner"})[1]
    assert any("Missing Partner" in w for w in funding)


def test_renaming_a_person_warns_about_projects_that_name_them(site_dir):
    from site_agent.config import SiteSettings
    from site_agent.repository import Repository
    from site_agent.site import Site

    repo = Repository(Site(SiteSettings(root=site_dir)))
    dependants = repo.dependants(SPECS["people"], "sam-roe")
    assert dependants and "Learning to grasp" in dependants[0]
    names = repo._rename_warnings(SPECS["people"], "sam-roe", {"name": "Sam Roe"}, {"name": "Samuel Roe"})
    assert names and "Learning to grasp" in names[0]


def test_example_site_files_pass_their_rules(site_dir):
    from site_agent.config import SiteSettings
    from site_agent.records import validate_file_text
    from site_agent.site import Site

    site = Site(SiteSettings(root=site_dir))
    for key, spec in SPECS.items():
        for rel in site.collection_files(key):
            assert validate_file_text(spec, site.read(rel)) == [], rel


def test_a_bad_entry_name_cannot_reach_other_folders(make_client):
    client = make_client()
    assert client.get("/c/people/..%2F..%2Fsettings").status_code == 404
    response = client.post("/c/people/..%2Fsecret/remove", data={"csrf": csrf(client)}, follow_redirects=False)
    assert response.status_code == 404
    assert client.get("/c/people/does-not-exist", follow_redirects=False).status_code == 303


def test_settings_save_and_show_the_approvers(make_client):
    client = make_client()
    client.post(
        "/settings",
        data={"csrf": csrf(client), "operator_name": "Pat Operator", "approvers": "Dr A | Head\n\nDr B"},
        follow_redirects=False,
    )
    page = client.get("/settings").text
    assert 'value="Pat Operator"' in page
    assert "Dr A | Head" in page and "Dr B" in page


def test_approval_with_a_check_command_runs_the_check_and_shows_it(make_client):
    command = f'"{sys.executable}" -c "print(\'fine\')"'
    client = make_client(check_command=command)
    set_up_operator(client)
    response = client.post("/c/people/new", data={"csrf": csrf(client), **person_form()}, follow_redirects=False)
    pid = preview_id(response.headers["location"])
    approved = client.post(
        f"/preview/{pid}/approve",
        data={"csrf": csrf(client), "approver": APPROVER, "statement": "on"},
        follow_redirects=False,
    )
    assert approved.headers["location"].startswith("/jobs/")
    check_page = client.get(approved.headers["location"], follow_redirects=True).text
    assert "The check passed." in check_page


def test_go_back_and_edit_brings_the_values_back(make_client):
    client = make_client()
    response = client.post(
        "/c/people/new", data={"csrf": csrf(client), **person_form(name="Maya Lin")}, follow_redirects=False
    )
    pid = preview_id(response.headers["location"])
    form = client.get(f"/c/people/new?from_preview={pid}").text
    assert 'value="Maya Lin"' in form


def test_a_failed_draft_says_why_and_saves_nothing(make_client):
    class Broken:
        def chat(self, messages, *, json_mode=False):
            raise RuntimeError("the model fell over")

    client = make_client(llm=Broken())
    response = client.post(
        "/c/people/new",
        data={"csrf": csrf(client), **person_form(body="", facts="Studies grasping.", action="draft:body")},
        follow_redirects=False,
    )
    page = client.get(response.headers["location"], follow_redirects=True).text
    assert "Something went wrong" in html.unescape(page)


def test_cancel_discards_a_running_job_result():
    """A background job that is cancelled stores nothing, even though the model eventually answers."""
    import time

    from site_agent.drafting import JobRunner

    def slow_answer() -> str:
        time.sleep(0.3)
        return "a late draft"

    runner = JobRunner()
    job_id = runner.start(slow_answer)
    assert runner.status(job_id)["state"] == "running"
    runner.cancel(job_id)
    time.sleep(0.6)
    status = runner.status(job_id)
    assert status["state"] == "cancelled"
    assert status["result"] is None


def test_list_search_and_sample_filter(make_client):
    client = make_client()
    everything = client.get("/c/people").text
    assert "Jane Doe" in everything and "Sam Roe" in everything
    searched = client.get("/c/people?q=jane").text
    assert "Jane Doe" in searched and "Sam Roe" not in searched
    samples = client.get("/c/people?samples=1").text
    assert "Sam Roe" in samples and "Jane Doe" not in samples
