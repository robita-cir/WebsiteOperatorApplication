import datetime as dt

from site_agent.text_utils import date_variants, excerpt_lines, matching_lines, slugify, ungrounded_fields


def test_slugify_makes_a_plain_file_name():
    assert slugify("Workshop on Robot Learning!") == "workshop-on-robot-learning"
    assert slugify("Café Día") == "cafe-dia"
    assert slugify("!!!") == ""


def test_date_variants_include_the_spellings_pages_use():
    variants = date_variants(dt.date(2026, 3, 10))
    assert "2026-03-10" in variants
    assert "10 March 2026" in variants
    assert "Mar 10, 2026" in variants


def test_matching_lines_ignores_case_and_extra_spaces():
    text = "first line\nThe  Robot   Learning workshop\nthird"
    assert matching_lines(text, ["robot learning WORKSHOP"]) == [1]


def test_matching_lines_ignores_needles_too_short_to_be_useful():
    assert matching_lines("an A to Z", ["A"]) == []


def test_excerpt_returns_short_files_whole():
    lines = ["a", "b", "c"]
    assert excerpt_lines(lines, [1], radius=1) == "a\nb\nc"


def test_excerpt_keeps_windows_around_hits_and_marks_gaps():
    lines = [f"line {i}" for i in range(100)]
    excerpt = excerpt_lines(lines, [5, 90], radius=2, max_lines=20)
    assert "line 5" in excerpt and "line 90" in excerpt
    assert "line 50" not in excerpt
    assert "[...]" in excerpt


def test_ungrounded_fields_flags_values_missing_from_the_text():
    source = "Workshop on 5 November 2026 in Lab 3."
    warnings = ungrounded_fields(
        {"date": dt.date(2026, 11, 5), "endDate": dt.date(2026, 11, 7), "venue": "Hall Z"}, source
    )
    assert any("endDate 2026-11-07" in w for w in warnings)
    assert any('venue "Hall Z"' in w for w in warnings)
    assert not any(w.startswith("date ") for w in warnings)


def test_whole_phrase_matching_does_not_hit_a_longer_name():
    assert matching_lines("Event 10 is on\nEvent 1 is on", ["Event 1"]) == [1]
