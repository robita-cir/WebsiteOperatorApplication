import pytest

from site_agent.llm.parsing import extract_json_object, strip_reasoning


def test_plain_json_object():
    assert extract_json_object('{"title": "A"}') == {"title": "A"}


def test_json_inside_a_code_fence():
    assert extract_json_object('```json\n{"title": "A"}\n```') == {"title": "A"}


def test_json_after_chatter():
    assert extract_json_object('Sure! Here it is: {"title": "A"} Hope that helps.') == {"title": "A"}


def test_reasoning_block_with_braces_is_removed_first():
    reply = '<think>maybe {"title": "wrong"}</think>{"title": "right"}'
    assert strip_reasoning(reply) == '{"title": "right"}'
    assert extract_json_object(reply) == {"title": "right"}


def test_reply_without_json_is_an_error():
    with pytest.raises(ValueError, match="no JSON object"):
        extract_json_object("I cannot help with that.")


def test_json_list_is_not_accepted_as_a_record():
    with pytest.raises(ValueError, match="not a JSON object"):
        extract_json_object("[1, 2, 3]")
