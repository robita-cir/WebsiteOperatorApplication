import datetime as dt

import pytest

from site_agent.frontmatter import parse_document, render_document, set_frontmatter_values

EVENT = """---
title: "Robot Learning Workshop"
kind: "workshop"
series: "Annual workshop"
date: 2026-03-10
# Keep this comment.
venue: "Main Hall, Example City"
---

Body text.
"""


def test_parse_reads_yaml_and_body():
    doc = parse_document(EVENT)
    assert doc.data["title"] == "Robot Learning Workshop"
    assert doc.data["date"] == dt.date(2026, 3, 10)
    assert doc.body == "Body text.\n"


def test_parse_rejects_a_file_without_frontmatter():
    with pytest.raises(ValueError, match="does not start with"):
        parse_document("# just markdown\n")


def test_parse_rejects_an_unclosed_block():
    with pytest.raises(ValueError, match="not closed"):
        parse_document("---\ntitle: x\n")


def test_render_quotes_strings_and_writes_dates_bare():
    text = render_document({"title": 'Say "hi": now', "date": dt.date(2026, 1, 2), "venue": None}, "Hello.\n\n")
    assert text == '---\ntitle: "Say \\"hi\\": now"\ndate: 2026-01-02\n---\n\nHello.\n'


def test_set_values_changes_only_the_named_lines():
    text = set_frontmatter_values(EVENT, {"venue": "Hall B", "date": dt.date(2026, 4, 1)})
    assert 'venue: "Hall B"' in text
    assert "date: 2026-04-01" in text
    assert "# Keep this comment." in text
    assert 'series: "Annual workshop"' in text
    assert text.endswith("Body text.\n")


def test_set_values_removes_a_key_given_none():
    text = set_frontmatter_values(EVENT, {"series": None})
    assert "series:" not in text
    assert 'title: "Robot Learning Workshop"' in text


def test_set_values_adds_a_missing_key_at_the_end_of_the_block():
    text = set_frontmatter_values(EVENT, {"summary": "New line."})
    head, _, _ = text.partition("\n---\n")
    assert head.endswith('summary: "New line."')


def test_set_values_with_no_changes_returns_the_same_text():
    assert set_frontmatter_values(EVENT, {}) == EVENT
