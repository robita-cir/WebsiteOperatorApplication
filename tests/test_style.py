"""Spelling advice: American spellings are pointed out, never changed, and never block a save."""

import pytest

from site_agent.apply import apply_plan
from site_agent.config import SiteSettings
from site_agent.records import SPECS
from site_agent.repository import Repository
from site_agent.site import Site
from site_agent.style import spelling_advice


@pytest.mark.parametrize(
    ("text", "american", "british"),
    [
        ("We organize a workshop.", "organize", "organise"),  # -ize verb
        ("The organization runs it.", "organization", "organisation"),  # -ization noun
        ("We analyzed the data.", "analyzed", "analysed"),
        ("The center is open.", "center", "centre"),  # -er to -re
        ("A bright color.", "color", "colour"),  # -or to -our
        ("Robot behavior is studied.", "behavior", "behaviour"),
        ("See the catalog.", "catalog", "catalogue"),  # -og to -ogue
        ("Modeling the arm.", "modeling", "modelling"),  # doubled l
        ("The open day program starts at nine.", "program", "programme"),  # event sense
        ("Read the license before use.", "license", "licence"),  # noun sense
    ],
)
def test_a_word_in_each_group_is_flagged_once_with_its_suggestion(text, american, british):
    advice = spelling_advice(text)
    assert len(advice) == 1
    assert advice[0].startswith(f"'{american}' is usually written '{british}' in British English.")


def test_the_sentence_is_plain_and_asks_for_a_check():
    assert spelling_advice("We organize it.") == [
        "'organize' is usually written 'organise' in British English. Check it."
    ]


def test_a_word_is_flagged_once_however_often_and_however_it_is_cased():
    assert len(spelling_advice("Center, center and CENTER.")) == 1
    assert len(spelling_advice("The center and the color.")) == 2


def test_the_advice_follows_the_order_of_the_text():
    advice = spelling_advice("The color of the center.")
    assert "'color'" in advice[0] and "'center'" in advice[1]


def test_words_inside_an_address_a_code_span_or_a_path_are_not_flagged():
    assert spelling_advice("See https://example.org/color-center/organize for details.") == []
    assert spelling_advice("Use `center` and `organize()` in the page.") == []
    assert spelling_advice("```\ncolor = 1\n```") == []
    assert spelling_advice("Download /documents/color-guide.pdf now.") == []
    assert spelling_advice("Write to color@example.org.") == []
    assert len(spelling_advice("Use `center` but the center is open.")) == 1


def test_british_spellings_and_longer_words_are_not_flagged():
    text = "We organise the centre with colour. The programme, the licence, behaviour, analyse, catalogue, modelling."
    assert spelling_advice(text) == []
    assert spelling_advice("The centerpiece and the programmer, a colorado trip, licensed use.") == []


def test_program_for_software_and_license_as_a_verb_are_left_alone():
    assert spelling_advice("The robot program crashed. We license the code. Write a computer program.") == []


def test_a_summary_with_an_american_spelling_warns_and_still_saves_when_ticked(site_dir):
    site = Site(SiteSettings(root=site_dir))
    raw = {"title": "Open day", "kind": "talk", "date": "2026-11-05", "summary": "We organize a visit to the center."}
    outcome = Repository(site).create(SPECS["events"], raw)
    assert outcome.ok and outcome.plan is not None
    assert any("'organize'" in w and "'organise'" in w for w in outcome.warnings)
    assert any("'center'" in w for w in outcome.warnings)

    # A warning does not block: the plan is complete and can be approved and written as it stands.
    apply_plan(site, outcome.plan, command="test", model="m")
    written = (site_dir / "src/content/events/open-day.md").read_text(encoding="utf-8")
    assert "We organize a visit to the center." in written  # advice only, the text is never rewritten


def test_the_body_is_checked_when_it_changes_and_old_text_is_not_checked_again(site_dir):
    site = Site(SiteSettings(root=site_dir))
    repo = Repository(site)
    spec = SPECS["news"]
    path = site_dir / "src/content/news/next-up.md"
    path.write_text(
        path.read_text(encoding="utf-8").split("---\n\n")[0] + "---\n\nThe center is great.\n", encoding="utf-8"
    )
    raw = {
        "title": "Next up",
        "kind": "news",
        "date": "2026-02-20",
        "summary": "A new summary.",
        "body": "The center is great.",
    }

    # The body already says 'center' and is not touched, so only the new summary is looked at.
    assert not any("British English" in w for w in repo.update(spec, "next-up", raw).warnings)

    changed = repo.update(spec, "next-up", {**raw, "body": "The center is great and the colors too."})
    assert any("'colors'" in w for w in changed.warnings)
