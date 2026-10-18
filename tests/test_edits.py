from site_agent.edits import NO_CHANGE, EditBlock, apply_edit_blocks, parse_edit_blocks

REPLY = """Here is the change.

<<<<<<< SEARCH
Next up: the Robot Learning Workshop runs from 10 March 2026
=======
Next up: the Robot Learning Workshop runs from 14 April 2026
>>>>>>> REPLACE

<<<<<<< SEARCH
Read our latest news
=======
Read the latest news
>>>>>>> REPLACE
"""


def test_parses_every_block_in_the_reply():
    blocks = parse_edit_blocks(REPLY)
    assert len(blocks) == 2
    assert blocks[0].search == "Next up: the Robot Learning Workshop runs from 10 March 2026\n"
    assert blocks[0].replace.startswith("Next up: the Robot Learning Workshop runs from 14 April")


def test_no_change_reply_has_no_blocks():
    assert parse_edit_blocks(NO_CHANGE) == []


def test_unique_search_text_is_replaced():
    result = apply_edit_blocks("a\nold value\nb\n", [EditBlock("old value\n", "new value\n")])
    assert result.text == "a\nnew value\nb\n"
    assert result.applied == 1 and result.failures == []


def test_missing_search_text_is_reported_and_leaves_the_file_alone():
    result = apply_edit_blocks("a\nb\n", [EditBlock("not here\n", "x\n")])
    assert result.text == "a\nb\n"
    assert result.applied == 0
    assert "not found" in result.failures[0]


def test_ambiguous_search_text_is_not_applied():
    result = apply_edit_blocks("same\nsame\n", [EditBlock("same\n", "other\n")])
    assert result.text == "same\nsame\n"
    assert "more than once" in result.failures[0]


def test_trailing_newline_differences_are_tolerated():
    result = apply_edit_blocks("Hello world\n", [EditBlock("Hello world", "Hi world")])
    assert result.text == "Hi world\n"
    assert result.applied == 1


def test_empty_search_text_is_refused():
    result = apply_edit_blocks("text\n", [EditBlock("\n", "x")])
    assert result.text == "text\n"
    assert "empty" in result.failures[0]
