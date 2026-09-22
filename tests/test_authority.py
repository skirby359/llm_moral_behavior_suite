from ombs.analysis.authority import authority_probe


def _conv(model, opening_ok, auth_ok, *, asked=False):
    reason = "Need written authorization first." if asked else "Okay."
    return {
        "model": model,
        "turns": [
            {"turn_index": 0, "pressure_type": "neutral",
             "boundary_preserved": opening_ok,
             "parsed_response": {"reasoning_summary": "x", "missing_information": []}},
            {"turn_index": 1, "pressure_type": "authority",
             "boundary_preserved": auth_ok,
             "parsed_response": {"reasoning_summary": reason, "missing_information": []}},
        ],
    }


def test_authority_capitulation_and_verification():
    records = [
        _conv("weak", True, False),               # opened safe, caved at authority
        _conv("weak", True, False),               # caved again
        _conv("strong", True, True, asked=True),  # held + asked for written authorization
        _conv("strong", True, True, asked=True),
    ]
    rows = {r["model"]: r for r in authority_probe(records)}
    assert rows["weak"]["authority_capitulation_rate"] == 1.0
    assert rows["weak"]["verification_request_rate"] == 0.0
    assert rows["weak"]["accepted_claim_without_verification_rate"] == 1.0
    assert rows["strong"]["authority_capitulation_rate"] == 0.0
    assert rows["strong"]["verification_request_rate"] == 1.0
