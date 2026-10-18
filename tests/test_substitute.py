import datetime as dt

from site_agent.substitute import Substitution, replace_on_anchor_lines, search_needles, substitutions_for


def test_a_date_change_gives_each_spelling_its_matching_replacement():
    subs = substitutions_for({"date": dt.date(2026, 3, 10)}, {"date": dt.date(2026, 4, 14)})
    assert Substitution("date", "10 March 2026", "14 April 2026") in subs
    assert Substitution("date", "2026-03-10", "2026-04-14") in subs
    assert len(subs) == 5


def test_fields_that_did_not_change_or_were_removed_are_not_substituted():
    subs = substitutions_for({"venue": "Hall A", "title": "T"}, {"venue": None})
    assert subs == []


def test_only_lines_naming_the_event_are_changed():
    text = "Robot Learning Workshop: 10 March 2026\nProposal deadline: 10 March 2026\n"
    subs = [Substitution("date", "10 March 2026", "14 April 2026")]
    result, changed = replace_on_anchor_lines(text, subs, anchor="Robot Learning Workshop")
    assert result == "Robot Learning Workshop: 14 April 2026\nProposal deadline: 10 March 2026\n"
    assert changed == [0]


def test_no_anchor_means_no_change():
    text = "10 March 2026\n"
    assert replace_on_anchor_lines(text, [Substitution("date", "10 March 2026", "1 May 2026")], anchor=None) == (
        text,
        [],
    )


def test_venue_and_series_are_replaced_on_event_lines_but_never_searched_for_alone():
    subs = substitutions_for(
        {"title": "Talk", "venue": "Venue name, City", "date": None},
        {"venue": "Lab 3, Example City"},
    )
    assert search_needles(subs) == []
    assert Substitution("venue", "Venue name, City", "Lab 3, Example City") in subs


def test_replacing_an_event_name_does_not_touch_a_longer_one():
    subs = [Substitution("title", "Event 1", "Hands-on Day")]
    text = "Event 1 is on\nEvent 10 is on"
    result, changed = replace_on_anchor_lines(text, subs, anchor="Event 1")
    assert result == "Hands-on Day is on\nEvent 10 is on"
    assert changed == [0]
