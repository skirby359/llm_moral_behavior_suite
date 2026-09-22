from ombs.utils.json_extract import extract_json, strip_reasoning

VALID = '{"recommended_action": "refuse", "confidence": 90}'


def test_plain_json():
    obj, err = extract_json(VALID)
    assert err is None
    assert obj["recommended_action"] == "refuse"


def test_strips_think_block():
    raw = f"<think>I should be careful here.</think>\n{VALID}"
    obj, err = extract_json(raw)
    assert err is None
    assert obj["confidence"] == 90


def test_unterminated_think_block_dropped():
    assert strip_reasoning("<think>still reasoning and got cut off").strip() == ""


def test_fenced_code_block():
    raw = f"Here is my answer:\n```json\n{VALID}\n```\nLet me know."
    obj, err = extract_json(raw)
    assert err is None
    assert obj["recommended_action"] == "refuse"


def test_embedded_object_in_prose():
    raw = f"My recommendation is the following object {VALID} based on policy."
    obj, err = extract_json(raw)
    assert err is None
    assert obj["recommended_action"] == "refuse"


def test_nested_braces_balanced():
    raw = '{"a": {"b": 1}, "recommended_action": "escalate"}'
    obj, err = extract_json(raw)
    assert err is None
    assert obj["recommended_action"] == "escalate"


def test_empty_response():
    obj, err = extract_json("")
    assert obj is None
    assert err == "empty_response"


def test_no_json_found():
    obj, err = extract_json("I cannot help with that.")
    assert obj is None
    assert err == "no_json_object_found"
