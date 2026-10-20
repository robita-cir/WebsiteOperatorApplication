"""The text rules behind the notice checks: a value kept to its quote, and spotting a series name."""

import pytest

from site_agent.text_utils import limit_to_quote, series_named_in


def test_a_value_equal_to_its_quote_is_left_alone():
    assert limit_to_quote("Lab 3, Example City", "Lab 3, Example City", "venue") == ("Lab 3, Example City", None)


def test_a_value_that_is_part_of_its_quote_is_left_alone():
    assert limit_to_quote("Lab 3", "Lab 3, Example City", "venue") == ("Lab 3", None)


def test_comparison_ignores_case_spacing_and_look_alike_characters():
    spaced = "LAB  3, example city"
    assert limit_to_quote(spaced, "Lab 3, Example City", "venue") == (spaced, None)
    assert limit_to_quote("Ｌａｂ 3", "Lab 3, Example City", "venue")[1] is None  # full-width letters


def test_a_longer_value_that_contains_the_quote_is_cut_back_to_the_quote():
    value, note = limit_to_quote(
        "Lab 3, Example City. The campus map lists it as Block B.", "Lab 3, Example City", "venue"
    )
    assert value == "Lab 3, Example City"
    assert note == "The venue was shortened to the words the notice uses: 'Lab 3, Example City'."


def test_the_quote_is_used_with_its_spaces_collapsed():
    value, _ = limit_to_quote("Venue is Lab  3,\nExample City, ground floor", "Lab  3,\nExample City", "venue")
    assert value == "Lab 3, Example City"


def test_a_value_unrelated_to_its_quote_is_kept_with_a_note():
    value, note = limit_to_quote("Block B, Room 12", "Lab 3, Example City", "venue")
    assert value == "Block B, Room 12"
    assert note == "The venue does not match the words the notice uses ('Lab 3, Example City'). Check it."


def test_the_same_rule_is_worded_for_a_series():
    value, note = limit_to_quote("Summer Series, a long-running programme", "Summer Series", "series")
    assert value == "Summer Series"
    assert note == "The series was shortened to the words the notice uses: 'Summer Series'."
    assert limit_to_quote("Winter Series", "Summer Series", "series") == (
        "Winter Series",
        "The series does not match the words the notice uses ('Summer Series'). Check it.",
    )


@pytest.mark.parametrize(
    "notice, expected",
    [
        ("The Example Robotics Summer Series is pleased to announce its next event.", "Example Robotics Summer Series"),
        ("Part of the Autumn Seminar Series at the centre.", "Autumn Seminar Series"),
        ("An Example Robotics Programme series runs all year.", "Example Robotics Programme series"),
        ("It opens the Spring Season with talks.", "Spring Season"),
        ("Applications for the Example Robotics Course close soon.", "Example Robotics Course"),
        ("A series of talks. The Series ends in June.", None),
        ("No such name here, just a series of events and a course.", None),
        ("Robot Talks\nSeries of events", None),  # a phrase never runs across lines
    ],
)
def test_series_named_in(notice, expected):
    assert series_named_in(notice) == expected
