"""The fact check: what written text may say, and what the facts must give."""

import datetime as dt

from site_agent.factcheck import fact_problems, facts_text, token_in_facts, unsupported_tokens
from site_agent.records import SPECS


def test_a_number_is_only_supported_as_a_whole_item():
    assert unsupported_tokens("Founded in 2010.", "Founded: 2010") == []
    # "10" sits inside "2010" in the facts, so it is not supported by it.
    assert unsupported_tokens("Ten years, 10 papers.", "Founded: 2010") == ["10"]
    assert token_in_facts("10", "Papers: 10") and not token_in_facts("10", "Founded: 2010")


def test_single_digit_numbers_are_checked():
    assert unsupported_tokens("She wrote 3 papers.", "Papers: 2") == ["3"]
    assert unsupported_tokens("She wrote 3 papers.", "Papers: 3") == []


def test_a_date_field_supports_the_prose_spellings_of_its_date():
    facts = facts_text(SPECS["events"], {"date": dt.date(2026, 11, 5), "venue": "Lab 3, Example City"}, "")
    assert unsupported_tokens("On 5 November 2026 in Lab 3.", facts) == []
    assert unsupported_tokens("On 6 November 2026.", facts) == ["6"]


def test_addresses_and_emails_are_checked():
    text = "See https://example.org/news or write to a.b@example.org."
    found = unsupported_tokens(text, "Contact: nobody")
    assert sorted(found) == ["a.b@example.org", "https://example.org/news"]  # the domain is reported as part of each


def test_long_text_is_never_a_source_of_facts():
    spec = SPECS["projects"]
    values = {"title": "Grasp learning", "summary": "The lab built 12 robots."}
    assert "12" not in facts_text(spec, values, "")
    assert "Grasp learning" in facts_text(spec, values, "")


def test_new_long_text_with_an_unsupported_number_is_a_problem():
    spec = SPECS["projects"]
    values = {"title": "Grasp learning", "summary": "The lab built 12 robots."}
    problems = fact_problems(spec, values, "", facts="Title: Grasp learning")
    assert len(problems) == 1
    assert problems[0].startswith('The summary for the project card mentions "12"')
    assert fact_problems(spec, values, "", facts="Robots built: 12") == []


def test_unchanged_text_on_an_edit_is_not_blocked():
    spec = SPECS["projects"]
    values = {"title": "Grasp learning", "summary": "The lab built 12 robots."}
    previous = {"summary": "The lab built 12 robots."}
    assert fact_problems(spec, values, "", facts="", previous=previous) == []
    changed = {"title": "Grasp learning", "summary": "The lab built 14 robots."}
    problems = fact_problems(spec, changed, "", facts="", previous=previous)
    assert problems and 'mentions "14"' in problems[0]


def test_body_is_checked_against_the_facts_and_the_previous_body():
    spec = SPECS["people"]
    values = {"name": "Ravi Kumar", "group": "mtech"}
    assert 'mentions "2019"' in fact_problems(spec, values, "Ravi joined in 2019.", facts="")[0]
    assert fact_problems(spec, values, "Ravi joined in 2019.", facts="Joined: 2019") == []
    unchanged = fact_problems(spec, values, "Ravi joined in 2019.", "", previous_body="Ravi joined in 2019.")
    assert unchanged == []
