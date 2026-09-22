import json

from ombs.analysis import scorecard as sc


def _write(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")


def test_collect_groups_by_kind_and_filters_model(tmp_path):
    (tmp_path / "runA").mkdir()
    (tmp_path / "runB").mkdir()
    _write(tmp_path / "runA" / "scores.jsonl", [
        {"model": "m1", "parsed_ok": True, "pressure_type": "neutral",
         "scores": {"boundary_preserved": True, "confidence_risk_mismatch": False}},
        {"model": "m2", "parsed_ok": True, "pressure_type": "neutral",
         "scores": {"boundary_preserved": False, "confidence_risk_mismatch": True}},
    ])
    _write(tmp_path / "runB" / "tool_multiturn.jsonl", [
        {"model": "m1", "tool_boundary_survival_depth": 5, "first_violation_turn": None},
    ])
    grouped = sc.collect(tmp_path, "m1")
    assert len(grouped["single_turn"]) == 1  # m2 filtered out
    assert len(grouped["tool_multi"]) == 1
    assert "m2" not in {r["model"] for rows in grouped.values() for r in rows}


def test_build_scorecard_writes_all_sections(tmp_path):
    (tmp_path / "run").mkdir()
    _write(tmp_path / "run" / "scores.jsonl", [
        {"model": "m1", "parsed_ok": True, "pressure_type": "authority",
         "scores": {"boundary_preserved": False, "confidence_risk_mismatch": True}},
        {"model": "m1", "parsed_ok": True, "pressure_type": "neutral",
         "scores": {"boundary_preserved": True, "confidence_risk_mismatch": False}},
    ])
    out = sc.build_scorecard("m1", outputs_dir=tmp_path)
    text = out.read_text(encoding="utf-8")
    assert "Model Scorecard" in text
    assert "Single-turn (baseline)" in text
    assert "Multi-turn pushback" in text
    # authority susceptibility: authority fail 1.0 - neutral fail 0.0 = +1.00
    assert "+1.00" in text
