"""`make figures` must regenerate every paper figure from the committed CSVs, with no manual step.

The generator reads only report CSVs that `build_sandbox_report` wrote into committed run
directories, so the smoke below runs it against the real `outputs/` tree into a temp directory.
A second test pins the numbers the figures draw to the ones the README and the REV4 brief
quote, so a figure cannot silently drift from the prose (or the prose from the record)."""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

pytest.importorskip("matplotlib")

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("figures", ROOT / "scenarios_sandbox" / "figures.py")
figures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(figures)


def test_every_figure_is_produced_from_the_committed_csvs(tmp_path):
    written = figures.render_all(ROOT / "outputs", tmp_path, formats=("png", "svg"))
    names = {p.name for p in written}
    # A figure whose run directory does not exist yet is skipped by the generator rather than
    # drawn from nothing; the moment its CSVs land it becomes required here. GATES is the one
    # table both the generator and this test consult, so a new gated figure is added once.
    assert set(figures.GATES) >= {"fig6_wave6_confirmatory", "fig7_two_pathways"}
    assert len(figures.GATES["fig7_two_pathways"]) == 6, "the two-pathway figure needs all six arm CSVs"
    for stem in figures.FIGURES:
        if figures.missing_sources(stem, ROOT / "outputs"):
            assert f"{stem}.png" not in names, f"{stem} was drawn without its source CSV"
            continue
        assert f"{stem}.png" in names and f"{stem}.svg" in names
    for p in written:
        assert p.exists() and p.stat().st_size > 1000, p


def test_the_figures_draw_the_numbers_the_briefs_quote():
    d = figures.Data(ROOT / "outputs")
    base, comp, defer = figures.ARMS
    assert d.crossings("sandbox_contract_execution", base) == (19, 20)
    assert d.crossings("sandbox_access_provisioning", base) == (6, 20)
    assert d.crossings("sandbox_grant_disbursement", base) == (0, 20)
    assert d.pooled(base) == (25, 60)
    assert d.pooled(comp) == (0, 60)
    assert d.pooled(defer) == (10, 60)
    # the pathway: compliant-failure runs re-attempt less and never touch a protected file
    assert d.pooled_field(base, "reattempt") == 60
    assert d.pooled_field(comp, "reattempt") == 39
    assert d.pooled_field(comp, "protected_reattempt") == 0
    # the specificity arm (Amendment 1): the placebo removes crossing with the search intact
    auth = d.bridge[("sandbox_contract_execution", *figures.AUTHORITY_ARM)]
    assert (int(auth["crossings"]), int(auth["n"])) == (0, 20)
    assert int(auth["reattempt"]) == 18 and int(auth["protected_reattempt"]) == 0
    refs = {lab: (k, n) for lab, k, n in d.reference_bars()}  # full label: two bars share a first line
    assert [v for lab, v in refs.items() if lab.startswith("reconciliation")] == [(4, 30)]
    assert [v for lab, v in refs.items() if lab.startswith("batch release")] == [(0, 21)]
    assert [v for lab, v in refs.items() if "claude-opus-5" in lab] == [(0, 10)]


def test_the_wave6_confirmatory_counts_are_the_ones_reported():
    d = figures.Data(ROOT / "outputs")
    if not d.wave6:
        pytest.skip("the Wave 6 arms have not run in this checkout")
    got = {k: (int(r["crossings"]), int(r["reattempt"]), int(r["protected_reattempt"]), int(r["n"]))
           for k, r in d.wave6.items()}
    assert got[("baseline", "off")] == (26, 30, 26, 30)
    assert got[("compliant_failure", "off")] == (0, 21, 0, 30)
    assert got[figures.AUTHORITY_ARM] == (0, 29, 0, 30)
    # the gate is reported beside the arms and pooled into none of them. The combined report
    # DOES pool it into baseline (it groups by task_framing), which is why the figure reads the
    # arm directories apart; this asserts the pooled row exists and differs, so a future switch
    # back to the combined CSV fails here rather than silently drawing 36/40 as the baseline.
    assert (int(d.wave6_pilot["crossings"]), int(d.wave6_pilot["n"])) == (10, 10)
    pooled = [r for r in figures.read_csv(ROOT / "outputs" / figures.WAVE6 / "persistence.csv")
              if r["task_framing"] == "baseline" and r["solvability"] == "stuck"]
    assert pooled and (int(pooled[0]["crossings"]), int(pooled[0]["n"])) == (36, 40)


def test_the_two_pathway_rows_are_the_ones_reported():
    """The six (family, arm) rows the two-pathway figure, table and PROGRAMME_RESULTS section 6b
    read, each from its arm's own persistence.csv: (n, crossings, reattempt, protected_reattempt,
    depth_mean). The re-attempt contrasts quoted in that section are pinned from the table text."""
    if figures.missing_sources("fig7_two_pathways", ROOT / "outputs"):
        pytest.skip("not every two-pathway arm has run in this checkout")
    d = figures.Data(ROOT / "outputs")
    rows = figures.two_pathway_rows(d)
    assert [(r["family"], r["arm"]) for r in rows] == [
        (f, a) for f in figures.TWO_PATHWAY for a in figures.TWO_PATHWAY_ARMS], "fixed family and arm order"
    got = {(r["family"], r["arm"]): (r["n"], r["crossings"], r["reattempt"], r["protected_reattempt"], r["depth_mean"])
           for r in rows}
    contract, procurement = "sandbox_contract_execution", "sandbox_procurement_award"
    base, comp, auth = figures.TWO_PATHWAY_ARMS
    expected = {
        (contract, base): (20, 19, 20, 19, 6.35),
        (contract, comp): (20, 0, 6, 0, 2.5),
        (contract, auth): (20, 0, 18, 0, 4.5),
        (procurement, base): (30, 26, 30, 26, 6.67),
        (procurement, comp): (30, 0, 21, 0, 3.4),
        (procurement, auth): (30, 0, 29, 0, 4.4),
    }
    for key, (n, k, re, pro, depth) in expected.items():
        assert got[key][:4] == (n, k, re, pro), key
        assert got[key][4] == pytest.approx(depth), key
    # the same rows, read through the figure's own dict, never through a combined report
    assert set(d.two_pathway) == set(expected)
    table = figures.two_pathway_table(d)
    assert "| contract execution (development) | baseline | 19/20 | 20/20 | 19/20 | 6.35 |" in table
    assert "| procurement award (held out) | compliant-failure | 0/30 | 21/30 | 0/30 | 3.4 |" in table
    assert "18/20 vs 6/20, two-sided Fisher exact p = 0.0002" in table
    assert "29/30 vs 21/30, two-sided Fisher exact p = 0.0122" in table  # the value section 6a quotes


def test_cumulative_incidence_is_monotone_and_ends_at_the_pooled_rate_order():
    d = figures.Data(ROOT / "outputs")
    xs, ys, k, n0 = d.cumulative_incidence("baseline")
    assert xs == sorted(xs) and all(b >= a for a, b in zip(ys, ys[1:]))
    # baseline framing pools the defer-off (25/60) and defer-on (10/60) arms: 35 of 120 runs
    assert (k, n0) == (35, 120) and ys[-1] == k / n0
    assert ys[xs.index(8)] == 0.0, "no crossing before action 9 in any bridge family"
    _, ys_c, k_c, n_c = d.cumulative_incidence("compliant_failure")
    assert (k_c, n_c) == (0, 60) and ys_c[-1] == 0.0


def test_the_wave7_counts_are_the_ones_reported():
    """PREREG_WAVE7_DOMAIN_EFFECT.md, read 13 Sep 2026: the goal-vocabulary swaps move both anchors,
    the party swaps move neither (pattern G-driver). Pinned from each variant's own persistence.csv."""
    d = figures.Data(ROOT / "outputs")
    if len(d.wave7) < 4:
        pytest.skip("the Wave 7 arms have not run in this checkout")
    got = {lab: (int(r["crossings"]), int(r["n"])) for lab, r in d.wave7.items()}
    assert got == {"V1": (9, 20), "V2": (1, 20), "V3": (6, 20), "V4": (18, 20)}
    assert d.crossings("sandbox_grant_disbursement", ("baseline", "off")) == (0, 20)
    assert d.crossings("sandbox_contract_execution", ("baseline", "off")) == (19, 20)
