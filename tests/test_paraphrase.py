from ombs.paraphrase import _extract_json_array, build_paraphrase_prompt


def test_build_paraphrase_prompt_preserves_facts_instruction():
    p = build_paraphrase_prompt("Send the file to dana@x.com", 3)
    assert "JSON array" in p
    assert "do not answer" in p.lower()


def test_extract_plain_array():
    arr = _extract_json_array('["one", "two", "three"]')
    assert arr == ["one", "two", "three"]


def test_extract_array_after_reasoning_and_prose():
    raw = '<think>let me write them</think>\nHere you go:\n["a", "b"]\nhope that helps'
    assert _extract_json_array(raw) == ["a", "b"]


def test_extract_array_drops_empty_strings():
    assert _extract_json_array('["x", "", "y"]') == ["x", "y"]


def test_extract_array_none_when_absent():
    assert _extract_json_array("no array here") is None
