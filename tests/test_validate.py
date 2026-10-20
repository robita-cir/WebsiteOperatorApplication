from site_agent.config import SiteSettings
from site_agent.plan import FileChange, Plan
from site_agent.site import Site
from site_agent.validate import check_plan


def test_a_plan_that_would_break_an_event_file_is_refused(site_dir):
    site = Site(SiteSettings(root=site_dir))
    broken = '---\ntitle: "Talk"\nkind: "seminar"\ndate: 2026-05-06\n---\n'
    plan = Plan(summary="test", changes=[FileChange("src/content/events/new.md", None, broken)])
    problems = check_plan(site, plan)
    assert problems and problems[0].rel_path == "src/content/events/new.md"
    assert problems[0].message.startswith("kind:")


def test_a_valid_plan_has_no_problems(site_dir):
    site = Site(SiteSettings(root=site_dir))
    good = '---\ntitle: "Talk"\nkind: "talk"\ndate: 2026-05-06\n---\n\nText.\n'
    plan = Plan(summary="test", changes=[FileChange("src/content/events/new.md", None, good)])
    assert check_plan(site, plan) == []


def test_a_change_outside_the_allow_list_is_refused(site_dir):
    site = Site(SiteSettings(root=site_dir))
    plan = Plan(summary="test", changes=[FileChange("public/notes.md", None, "x")])
    assert "not in the paths" in check_plan(site, plan)[0].message


def test_a_plan_that_would_break_a_person_file_is_refused(site_dir):
    site = Site(SiteSettings(root=site_dir))
    rel = "src/content/people/jane-doe.md"
    plan = Plan(summary="test", changes=[FileChange(rel, site.read(rel), '---\nname: "Jane"\ngroup: "wizard"\n---\n')])
    problems = check_plan(site, plan)
    assert problems and problems[0].rel_path == rel
