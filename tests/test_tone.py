"""Tone advice: exclamation marks, shouting and marketing words are pointed out, never blocked."""

import pytest

from site_agent.config import SiteSettings
from site_agent.records import SPECS
from site_agent.repository import Repository
from site_agent.site import Site
from site_agent.style import tone_advice

LONG = "The group will run a workshop on robot arms for visiting students next month"


def test_an_exclamation_mark_in_long_text_is_flagged():
    assert tone_advice(LONG + "!") == ["Exclamation marks are not used on the site. Check it."]


def test_an_exclamation_mark_is_flagged_once():
    assert len(tone_advice(LONG + "! Do come! Really!")) == 1


def test_an_exclamation_mark_in_short_text_is_left_alone():
    assert tone_advice("Join us!") == []


def test_long_text_without_an_exclamation_mark_is_clean():
    assert tone_advice(LONG + ".") == []


def test_not_equals_and_markdown_images_are_not_exclamation_marks():
    assert tone_advice(LONG + " where `a != b` and ![a robot](/images/robot.png) are shown.") == []


@pytest.mark.parametrize("word", ["SHOUT", "ROBOTS", "NEWS"])
def test_a_run_of_four_capitals_is_flagged(word):
    advice = tone_advice(f"Come to the {word} open day.")
    assert advice == [f"'{word}' is in capital letters. Use ordinary capitals unless it is an acronym. Check it."]


@pytest.mark.parametrize(
    "acronym", ["CIR", "IEEE", "PDF", "DOI", "ACM", "UK", "EU", "USA", "NASA", "ROS", "GPU", "CPU"]
)
def test_known_acronyms_are_fine(acronym):
    assert tone_advice(f"Published by {acronym} members and {acronym}") == []


def test_short_capitals_and_mixed_case_are_fine():
    assert tone_advice("The MIT and KCL teams use GPUs and Python.") == []


def test_an_unknown_acronym_of_four_letters_is_flagged_once():
    assert len(tone_advice("The ABCD rig. The ABCD rig again.")) == 1


@pytest.mark.parametrize(
    "word", ["amazing", "world-class", "best-in-class", "revolutionary", "incredible", "stunning", "unbeatable"]
)
def test_a_marketing_word_is_flagged(word):
    assert tone_advice(f"It is a {word} result.") == [
        f"'{word}' sounds like marketing. Say what the work does instead. Check it."
    ]


@pytest.mark.parametrize("word", ["groundbreaking", "game-changing"])
def test_the_other_marketing_words_are_flagged_when_capitalised(word):
    assert tone_advice(f"A {word.capitalize()} idea.") == [
        f"'{word}' sounds like marketing. Say what the work does instead. Check it."
    ]


def test_plain_wording_and_longer_words_are_not_marketing():
    assert tone_advice("The amazingly long cable and a world-classroom.") == []


def test_code_and_addresses_are_not_checked():
    assert tone_advice("See `STOP` and https://example.org/AMAZING/ for details.") == []


@pytest.fixture
def repo(site_dir) -> Repository:
    return Repository(Site(SiteSettings(root=site_dir)))


def _news(body: str) -> dict:
    return {"title": "Fresh", "kind": "news", "date": "2026-03-01", "summary": "Summary.", "body": body}


def test_tone_advice_shows_in_the_preview_and_does_not_block(repo):
    outcome = repo.create(SPECS["news"], _news("An amazing day for the whole group, with a world-class talk."))
    assert outcome.plan is not None and outcome.ok
    assert any("'amazing' sounds like marketing" in w for w in outcome.warnings)
    assert any("'world-class' sounds like marketing" in w for w in outcome.warnings)


def test_spelling_advice_is_still_given_with_tone_advice(repo):
    outcome = repo.create(SPECS["news"], _news("The center held a stunning open day for everyone."))
    assert any("'center' is usually written 'centre'" in w for w in outcome.warnings)
    assert any("'stunning' sounds like marketing" in w for w in outcome.warnings)


def test_an_unchanged_body_does_not_bring_up_old_tone_problems(repo, site_dir):
    path = site_dir / "src/content/news/next-up.md"
    path.write_text(path.read_text(encoding="utf-8") + "\nAn incredible start.\n", encoding="utf-8", newline="")
    record = repo.load(SPECS["news"], "next-up")
    form = {"title": "Next up", "kind": "news", "date": "2026-02-20", "summary": "A new summary.", "body": record.body}
    outcome = repo.update(SPECS["news"], "next-up", form)
    assert outcome.plan is not None
    assert not any("sounds like marketing" in w for w in outcome.warnings)
