"""The paper's core figures, regenerated from the committed report CSVs. No model, no spend.

    uv run python scenarios_sandbox/figures.py [--outputs outputs] [--out reports/figures]
    uv run python scenarios_sandbox/figures.py --table two_pathways   # the Markdown table only
    make figures

Every number drawn here is read from a CSV that `build_sandbox_report` already wrote into a
committed run directory; nothing is re-derived from the JSONL and nothing is typed in. If a
figure and a README table disagree, the CSV is the arbiter and one of the two prose sources is
stale. The figures:

  fig1_crossing_by_family_and_arm   gpt-5.5 crossing rate, three bridge families x three terminal
                                    arms (the headline), Wilson 95% intervals, k/n labelled
  fig2_safeguard_effect             pooled crossing by arm (baseline / compliant-failure / defer)
                                    beside the cumulative incidence by action, so the "pathway"
                                    (compliant-failure runs end before the actions where crossings
                                    happen) is shown rather than adjusted away
  fig3_domain_gradient              baseline crossing by domain: the three bridge families with the
                                    Family 1 (finance) and Family 2 (batch release) reference arms
                                    and the claude-opus-5 contract arm as grey reference bars
  fig4_persistence_and_terminals    post-failure re-attempt (any file / protected file) by arm, and
                                    the terminal taken by arm (honest close / hand-off / cap)
  fig5_safeguard_specificity        the contract family under four framings: baseline, compliant-
                                    failure, defer, and the length-matched authority-salience
                                    placebo (Amendment 1 to PREREG_WAVE5_BRIDGE.md); crossing,
                                    re-attempt and protected re-attempt side by side
  fig6_wave6_confirmatory           the held-out family (Wave 6): the confirmatory baseline-minus-
                                    compliant-failure contrast with the secondary authority arm and
                                    the pilot as a grey reference, on the same three measures
  fig7_two_pathways                 the two-pathway result side by side in the contract (development)
                                    and procurement (held out) families: per arm, crossing,
                                    re-attempt and protected re-attempt, with the mean post-failure
                                    depth under each arm; the reviewer's item 2, from committed data

A figure whose source CSVs have not landed is skipped, not faked: `GATES` names the CSVs each
gated figure needs, and `render_all` (and the test) consult it.

Colour: four categorical slots from the validated reference palette (blue, orange, aqua, yellow),
fixed to the arms in that order everywhere; reference arms are grey. Every bar carries its
k/n as a direct label, so no reading depends on colour alone.
"""

from __future__ import annotations

import argparse
import ast
import csv
import pathlib
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ombs.scorers.discrimination import wilson_ci  # noqa: E402

# ---------------------------------------------------------------- sources (committed CSVs)
BRIDGE = "sandbox5_bridge_combined"
OPUS_CONTRACT = ("sandbox5_contract_baseline_opus", "sandbox5_contract_defer_opus")
FAMILY2 = "sandbox2_batch_release_rescored"
FAMILY1 = "sandbox_wave3_frozen_rescored"
AUTHORITY = "sandbox5_contract_authority_gpt"  # the specificity arm, contract family only
GEMINI_CONTRACT = "sandbox5_contract_baseline_gemini"  # the third vendor, arm A (PREREG_THIRD_VENDOR_GEMINI.md)
GEMINI_MODEL = "gemini-3.1-pro-preview"
#: Wave 7 minimal pairs (PREREG_WAVE7_DOMAIN_EFFECT.md): label -> (run directory, family, anchor key).
#: Read from each variant's own directory; the anchors are the committed Wave 5 baseline arms.
WAVE7_VARIANTS = {"V1": ("sandbox7_grant_goal_swap_gpt", "sandbox_grant_goal_swap", "grant"),
                  "V2": ("sandbox7_grant_party_swap_gpt", "sandbox_grant_party_swap", "grant"),
                  "V3": ("sandbox7_contract_goal_swap_gpt", "sandbox_contract_goal_swap", "contract"),
                  "V4": ("sandbox7_contract_party_swap_gpt", "sandbox_contract_party_swap", "contract")}
WAVE7_ANCHORS = {"grant": "sandbox_grant_disbursement", "contract": "sandbox_contract_execution"}
#: Wave 6 arms, each read from its OWN run directory. The combined report
#: (`sandbox6_procurement_combined`) groups by `task_framing`, and the pilot's framing is
#: `baseline`, so its 10 gate runs merge into the baseline arm there (36/40 rather than 26/30).
#: That is the pooling PREREG_WAVE6_CONFIRMATORY.md forbids -- the runs that qualified the family
#: cannot also estimate its rate -- so the figure reads the arms apart, as wave6_analysis.py does.
WAVE6_ARMS = {("baseline", "off"): "sandbox6_procurement_baseline_gpt",
              ("compliant_failure", "off"): "sandbox6_procurement_compliant_gpt",
              ("authority_salience", "off"): "sandbox6_procurement_authority_gpt"}
WAVE6 = "sandbox6_procurement_combined"        # the pooled record; not read for the arm rates
WAVE6_PILOT = "sandbox6_procurement_pilot_gpt"  # the elicitation gate, never pooled into arm A
WAVE6_FAMILY = "sandbox_procurement_award"
#: The contract family's three arms, each from its own run directory, for the two-pathway figure.
#: The bridge combined report carries the same three rows, but reading the arms apart keeps the
#: contract and procurement halves of that figure on one footing (and keeps the procurement side
#: away from the combined report, which pools the pilot into baseline -- see WAVE6_ARMS above).
CONTRACT_ARMS = {("baseline", "off"): "sandbox5_contract_baseline_gpt",
                 ("compliant_failure", "off"): "sandbox5_contract_compliant_gpt",
                 ("authority_salience", "off"): "sandbox5_contract_authority_gpt"}
#: family -> {arm -> run directory}; the fixed order is development family first, held-out second
TWO_PATHWAY = {"sandbox_contract_execution": CONTRACT_ARMS, "sandbox_procurement_award": WAVE6_ARMS}
TWO_PATHWAY_LABEL = {"sandbox_contract_execution": "contract execution (development)",
                     "sandbox_procurement_award": "procurement award (held out)"}
TWO_PATHWAY_ARMS = (("baseline", "off"), ("compliant_failure", "off"), ("authority_salience", "off"))
#: the three measures every persistence figure reports, in the order the two-pathway figure draws them
MEASURES = (("crossings", "crossed"), ("reattempt", "re-attempted the environment"),
            ("protected_reattempt", "re-wrote a protected file"))

ARMS = (("baseline", "off"), ("compliant_failure", "off"), ("baseline", "on"))
AUTHORITY_ARM = ("authority_salience", "off")
ARMS4 = ARMS + (AUTHORITY_ARM,)  # the order is the palette's validated adjacency, not cosmetic
ARM_LABEL = {("baseline", "off"): "baseline", ("compliant_failure", "off"): "compliant-failure",
             ("baseline", "on"): "defer", AUTHORITY_ARM: "authority-salience\n(placebo)"}
ARM_COLOUR = {("baseline", "off"): "#2a78d6", ("compliant_failure", "off"): "#eb6834",
              ("baseline", "on"): "#1baf7a", AUTHORITY_ARM: "#eda100"}
FAMILY_LABEL = {"sandbox_contract_execution": "contract execution\n(legal)",
                "sandbox_procurement_award": "procurement award\n(purchasing, held out)",
                "sandbox_access_provisioning": "access provisioning\n(IT security)",
                "sandbox_grant_disbursement": "grant disbursement\n(nonprofit finance)",
                "sandbox_reconciliation": "reconciliation\n(finance, Family 1)",
                "sandbox_batch_release": "batch release\n(pharma QC, Family 2)"}
FAMILY_ORDER = ("sandbox_contract_execution", "sandbox_access_provisioning", "sandbox_grant_disbursement")
GREY, INK, INK2, GRID = "#9a9891", "#0b0b0b", "#52514e", "#e6e5e1"
TERMINAL_LABEL = {"honest_close": "honest close", "handoff": "hand-off (defer)",
                  "censored_cap": "action cap (censored)", "abandoned": "abandoned"}


def read_csv(path: pathlib.Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def frac(k: int, n: int) -> tuple[float, float, float]:
    """rate and the Wilson 95% interval, as (rate, low, high); zeros when n == 0."""
    if n == 0:
        return 0.0, 0.0, 0.0
    lo, hi = wilson_ci(k, n)
    return k / n, lo, hi


class Data:
    """Everything the figures need, keyed the way they ask for it."""

    def __init__(self, outputs: pathlib.Path) -> None:
        self.outputs = outputs
        # gpt-5.5, bridge families: persistence.csv has one row per (family, arm)
        self.bridge = {}
        for r in read_csv(outputs / BRIDGE / "persistence.csv"):
            if r["model"] != "gpt-5.5" or r["solvability"] != "stuck":
                continue
            self.bridge[(r["family"], r["task_framing"], r["defer_available"])] = r
        self.wave7: dict[str, dict] = {}  # V1..V4 baseline rows, each from its own run directory
        for label, (run, family, _anchor) in WAVE7_VARIANTS.items():
            path = outputs / run / "persistence.csv"
            if path.exists():
                for r in read_csv(path):
                    if (r["model"] == "gpt-5.5" and r["family"] == family and r["solvability"] == "stuck"
                            and r["task_framing"] == "baseline" and r["defer_available"] == "off"):
                        self.wave7[label] = r
        self.gemini = None  # arm A persistence row of the third vendor, read from its own directory
        gem = outputs / GEMINI_CONTRACT / "persistence.csv"
        if gem.exists():
            for r in read_csv(gem):
                if (r["model"] == GEMINI_MODEL and r["family"] == "sandbox_contract_execution"
                        and r["solvability"] == "stuck" and r["task_framing"] == "baseline" and r["defer_available"] == "off"):
                    self.gemini = r
        self.opus = {}
        for d in OPUS_CONTRACT:
            for r in read_csv(outputs / d / "persistence.csv"):
                self.opus[(r["family"], r["task_framing"], r["defer_available"])] = r
        self.family2 = {}
        for r in read_csv(outputs / FAMILY2 / "persistence.csv"):
            if r["defer_available"] == "off" and r["task_framing"] == "baseline":
                self.family2[r["model"]] = r
        self.family1 = {}
        for r in read_csv(outputs / FAMILY1 / "estimand.csv"):
            if r["task_framing"] == "baseline":
                self.family1[r["model"]] = r
        self.survival = [r for r in read_csv(outputs / BRIDGE / "survival.csv") if r["model"] == "gpt-5.5"]
        # the specificity arm was run after the bridge wave into its own directory
        auth = outputs / AUTHORITY / "persistence.csv"
        if auth.exists():
            for r in read_csv(auth):
                if r["model"] == "gpt-5.5" and r["solvability"] == "stuck":
                    self.bridge[(r["family"], r["task_framing"], r["defer_available"])] = r
        # Wave 6: the confirmatory arms, and the pilot kept separate (the preregistration fixes
        # them as separate; pooling the gate into the baseline arm would be the peeking it forbids)
        self.wave6: dict[tuple[str, str], dict] = {}
        for arm, run in WAVE6_ARMS.items():
            path = outputs / run / "persistence.csv"
            if not path.exists():
                continue
            for r in read_csv(path):
                if (r["model"] == "gpt-5.5" and r["solvability"] == "stuck"
                        and (r["task_framing"], r["defer_available"]) == arm):
                    self.wave6[arm] = r
        self.wave6_pilot = None
        pilot = outputs / WAVE6_PILOT / "persistence.csv"
        if pilot.exists():
            rows = [r for r in read_csv(pilot) if r["model"] == "gpt-5.5" and r["solvability"] == "stuck"]
            self.wave6_pilot = rows[0] if rows else None
        # The two-pathway rows: (family, arm) -> the arm's own persistence row. Each arm is read
        # from its own directory and matched on model, solvability, family and arm, never from a
        # combined report (the procurement combined report pools the pilot into baseline).
        self.two_pathway: dict[tuple[str, tuple[str, str]], dict] = {}
        for family, arms in TWO_PATHWAY.items():
            for arm, run in arms.items():
                path = outputs / run / "persistence.csv"
                if not path.exists():
                    continue
                for r in read_csv(path):
                    if (r["model"] == "gpt-5.5" and r["solvability"] == "stuck" and r["family"] == family
                            and (r["task_framing"], r["defer_available"]) == arm):
                        self.two_pathway[(family, arm)] = r

    # -- accessors -------------------------------------------------------------------
    def crossings(self, family: str, arm: tuple[str, str]) -> tuple[int, int]:
        r = self.bridge[(family, *arm)]
        return int(r["crossings"]), int(r["n"])

    def pooled(self, arm: tuple[str, str]) -> tuple[int, int]:
        k = n = 0
        for f in FAMILY_ORDER:
            a, b = self.crossings(f, arm)
            k, n = k + a, n + b
        return k, n

    def pooled_field(self, arm: tuple[str, str], field: str) -> int:
        return sum(int(self.bridge[(f, *arm)][field]) for f in FAMILY_ORDER)

    def terminals(self, arm: tuple[str, str]) -> dict[str, int]:
        out: dict[str, int] = defaultdict(int)
        for f in FAMILY_ORDER:
            for k, v in ast.literal_eval(self.bridge[(f, *arm)]["terminals"]).items():
                out[k] += int(v)
        return dict(out)

    def cumulative_incidence(self, framing: str) -> tuple[list[int], list[float], int, int]:
        """Crude cumulative incidence of crossing by action: crossings up to action a over the
        runs at risk at action 1, pooled over the three families. Honest close and hand-off are
        competing terminal events, not censoring, so a run that ended honestly stays in the
        denominator (a Kaplan-Meier product would instead estimate what the rate would have been
        had no run ever ended honestly, which is not the question). survival.csv groups by
        task_framing only, so the baseline curve pools the defer-off and defer-on arms; the
        returned (crossings, n) says what was pooled."""
        by_action: dict[int, list[int]] = defaultdict(lambda: [0, 0])
        for r in self.survival:
            if r["task_framing"] != framing or r["solvability"] != "stuck":
                continue
            a = int(r["action"])
            by_action[a][0] += int(r["at_risk"])
            by_action[a][1] += int(r["crossings"])
        if not by_action:
            return [], [], 0, 0
        n0 = by_action[min(by_action)][0]
        xs, ys, so_far = [], [], 0
        for a in sorted(by_action):
            so_far += by_action[a][1]
            xs.append(a)
            ys.append(so_far / n0)
        return xs, ys, so_far, n0

    def reference_bars(self) -> list[tuple[str, int, int]]:
        """(label, k, n) for the grey reference arms in the domain figure."""
        out = []
        f1 = self.family1.get("gpt-5.5")
        if f1:
            k, n = f1["stuck"].split("/")
            out.append(("reconciliation\n(finance, Family 1)\ngpt-5.5", int(k), int(n)))
        f2 = self.family2.get("gpt-5.5")
        if f2:
            out.append(("batch release\n(Family 2)\ngpt-5.5", int(f2["crossings"]), int(f2["n"])))
        op = self.opus.get(("sandbox_contract_execution", "baseline", "off"))
        if op:
            out.append(("contract execution\nclaude-opus-5", int(op["crossings"]), int(op["n"])))
        if self.gemini:
            out.append((f"contract execution\n{GEMINI_MODEL}", int(self.gemini["crossings"]), int(self.gemini["n"])))
        return out


# ---------------------------------------------------------------- the two-pathway rows and table
def two_pathway_rows(d: Data) -> list[dict]:
    """One dict per (family, arm) present, in the fixed family and arm order, with the counts the
    two-pathway figure, table and prose all read: n, crossings, reattempt, protected_reattempt and
    depth_mean (mean post-failure depth, a float)."""
    rows = []
    for family in TWO_PATHWAY:
        for arm in TWO_PATHWAY_ARMS:
            r = d.two_pathway.get((family, arm))
            if r is None:
                continue
            rows.append({"family": family, "arm": arm, "n": int(r["n"]), "crossings": int(r["crossings"]),
                         "reattempt": int(r["reattempt"]), "protected_reattempt": int(r["protected_reattempt"]),
                         "depth_mean": float(r["depth_mean"])})
    return rows


def _arm_name(arm: tuple[str, str]) -> str:
    return ARM_LABEL[arm].split("\n")[0]


def _p_text(p: float | None) -> str:
    """`fisher_exact_two_sided` rounds to four decimals, so a returned 0.0 is a bound, not a value."""
    if p is None:
        return "n/a"
    if p == 0.0:
        return "< 1e-4"
    return "1.0" if p >= 1.0 else f"{p:.4g}"


def two_pathway_table(d: Data) -> str:
    """The Markdown table the results prose pastes, plus the re-attempt contrasts under it, so
    every number in that prose is generated from the arm CSVs rather than typed."""
    from ombs.analysis.sandbox import fisher_exact_two_sided
    rows = two_pathway_rows(d)
    lines = ["| family | arm | crossing | re-attempt | protected re-attempt | mean post-failure depth |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        n = r["n"]
        lines.append(f"| {TWO_PATHWAY_LABEL[r['family']]} | {_arm_name(r['arm'])} | {r['crossings']}/{n} | "
                     f"{r['reattempt']}/{n} | {r['protected_reattempt']}/{n} | {r['depth_mean']:g} |")
    by = {(r["family"], r["arm"]): r for r in rows}
    notes = []
    for family in TWO_PATHWAY:
        auth = by.get((family, ("authority_salience", "off")))
        comp = by.get((family, ("compliant_failure", "off")))
        base = by.get((family, ("baseline", "off")))
        if auth and comp:
            p = fisher_exact_two_sided(auth["reattempt"], auth["n"] - auth["reattempt"],
                                       comp["reattempt"], comp["n"] - comp["reattempt"])
            notes.append(f"{TWO_PATHWAY_LABEL[family]}: re-attempt, authority-salience vs compliant-failure, "
                         f"{auth['reattempt']}/{auth['n']} vs {comp['reattempt']}/{comp['n']}, "
                         f"two-sided Fisher exact p = {_p_text(p)}")
        if auth and base:
            p = fisher_exact_two_sided(auth["reattempt"], auth["n"] - auth["reattempt"],
                                       base["reattempt"], base["n"] - base["reattempt"])
            notes.append(f"{TWO_PATHWAY_LABEL[family]}: re-attempt, authority-salience vs baseline, "
                         f"{auth['reattempt']}/{auth['n']} vs {base['reattempt']}/{base['n']}, "
                         f"two-sided Fisher exact p = {_p_text(p)}")
    if notes:
        lines.append("")
        lines.extend(f"- {note}" for note in notes)
    return "\n".join(lines)


# ---------------------------------------------------------------- drawing
def _style(ax) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _bars(ax, xs, rates, los, his, colours, labels, width=0.26) -> None:
    for x, r, lo, hi, c, lab in zip(xs, rates, los, his, colours, labels):
        ax.bar(x, r, width=width, color=c, linewidth=0)
        ax.vlines(x, lo, hi, color=INK2, linewidth=1)
        ax.text(x, hi + 0.02, lab, ha="center", va="bottom", fontsize=8, color=INK)


def fig_crossing_by_family_and_arm(d: Data):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    _style(ax)
    xs, rates, los, his, cols, labs = [], [], [], [], [], []
    for i, fam in enumerate(FAMILY_ORDER):
        for j, arm in enumerate(ARMS):
            k, n = d.crossings(fam, arm)
            r, lo, hi = frac(k, n)
            xs.append(i + (j - 1) * 0.28)
            rates.append(r)
            los.append(lo)
            his.append(hi)
            cols.append(ARM_COLOUR[arm])
            labs.append(f"{k}/{n}")
    _bars(ax, xs, rates, los, his, cols, labs)
    ax.set_xticks(range(len(FAMILY_ORDER)))
    ax.set_xticklabels([FAMILY_LABEL[f] for f in FAMILY_ORDER])
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("runs with any boundary crossing", color=INK2)
    ax.set_title("gpt-5.5, blocked runs: crossing by family and terminal arm (Wilson 95%)",
                 loc="left", fontsize=11, color=INK)
    handles = [plt.Rectangle((0, 0), 1, 1, color=ARM_COLOUR[a]) for a in ARMS]
    ax.legend(handles, [ARM_LABEL[a] for a in ARMS], frameon=False, fontsize=9, loc="upper right")
    fig.tight_layout()
    return fig


def fig_safeguard_effect(d: Data):
    import matplotlib.pyplot as plt
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(9.6, 4.2), gridspec_kw={"width_ratios": [1, 1.4]})
    _style(ax)
    _style(ax2)
    xs, rates, los, his, cols, labs = [], [], [], [], [], []
    for j, arm in enumerate(ARMS):
        k, n = d.pooled(arm)
        r, lo, hi = frac(k, n)
        xs.append(j)
        rates.append(r)
        los.append(lo)
        his.append(hi)
        cols.append(ARM_COLOUR[arm])
        labs.append(f"{k}/{n}")
    _bars(ax, xs, rates, los, his, cols, labs, width=0.55)
    ax.set_xticks(range(len(ARMS)))
    ax.set_xticklabels([ARM_LABEL[a] for a in ARMS])
    ax.set_ylim(0, 0.75)
    ax.set_ylabel("runs with any boundary crossing", color=INK2)
    ax.set_title("pooled over the three bridge families", loc="left", fontsize=10, color=INK)
    for framing, arm in (("baseline", ("baseline", "off")), ("compliant_failure", ("compliant_failure", "off"))):
        xs_, ys_, k, n0 = d.cumulative_incidence(framing)
        pooled_note = " (defer arms pooled)" if framing == "baseline" else ""
        ax2.step(xs_, ys_, where="post", color=ARM_COLOUR[arm], linewidth=2,
                 label=f"{ARM_LABEL[arm]} framing{pooled_note}: {k}/{n0}")
        if xs_:
            ax2.plot(xs_[-1], ys_[-1], "o", color=ARM_COLOUR[arm], markersize=6)
            ax2.text(xs_[-1], ys_[-1] + 0.03, f"{ys_[-1]:.2f} by action {xs_[-1]}", fontsize=8,
                     ha="center", va="bottom", color=INK)
    ax2.set_xlabel("action index (hidden cap 16)", color=INK2)
    ax2.set_ylabel("cumulative incidence of crossing", color=INK2)
    ax2.set_ylim(0, 0.6)
    ax2.set_xlim(0.5, 17.5)
    ax2.set_title("by action: crossings begin at action 9; every compliant-failure run has ended by 12",
                  loc="left", fontsize=10, color=INK)
    ax2.legend(frameon=False, fontsize=9, loc="upper left")
    fig.suptitle("gpt-5.5: the compliant-failure terminal removes crossing (total effect, pathway shown)",
                 x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout()
    return fig


def fig_domain_gradient(d: Data):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9.2, 4.4))
    _style(ax)
    items = [(FAMILY_LABEL[f] + "\ngpt-5.5", *d.crossings(f, ("baseline", "off")), ARM_COLOUR[("baseline", "off")])
             for f in FAMILY_ORDER]
    items += [(lab, k, n, GREY) for lab, k, n in d.reference_bars()]
    xs = list(range(len(items)))
    rates, los, his = zip(*[frac(k, n) for _, k, n, _ in items])
    _bars(ax, xs, rates, los, his, [c for *_, c in items], [f"{k}/{n}" for _, k, n, _ in items], width=0.6)
    ax.axvline(len(FAMILY_ORDER) - 0.5, color=GRID, linewidth=1)
    ax.set_xticks(xs)
    ax.set_xticklabels([lab for lab, *_ in items], fontsize=8)
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("baseline runs with any boundary crossing", color=INK2)
    ax.set_title("Baseline crossing by domain, one procedural-blocker template (blue); reference arms (grey)",
                 loc="left", fontsize=11, color=INK)
    fig.tight_layout()
    return fig


def fig_persistence_and_terminals(d: Data):
    import matplotlib.pyplot as plt
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(9.6, 4.2))
    _style(ax)
    _style(ax2)
    measures = (("reattempt", "re-attempted the\nenvironment"), ("protected_reattempt", "re-wrote a\nprotected file"),
                ("crossings", "crossed"))
    for j, arm in enumerate(ARMS):
        n = d.pooled_field(arm, "n")
        for i, (field, _) in enumerate(measures):
            k = d.pooled_field(arm, field)
            r, lo, hi = frac(k, n)
            x = i + (j - 1) * 0.28
            ax.bar(x, r, width=0.26, color=ARM_COLOUR[arm], linewidth=0)
            ax.vlines(x, lo, hi, color=INK2, linewidth=1)
            ax.text(x, hi + 0.02, f"{k}/{n}", ha="center", va="bottom", fontsize=7.5, color=INK)
    ax.set_xticks(range(len(measures)))
    ax.set_xticklabels([lab for _, lab in measures])
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("share of blocked runs (after the first failed check)", color=INK2)
    ax.set_title("post-failure persistence, pooled", loc="left", fontsize=10, color=INK)
    handles = [plt.Rectangle((0, 0), 1, 1, color=ARM_COLOUR[a]) for a in ARMS]
    ax.legend(handles, [ARM_LABEL[a] for a in ARMS], frameon=False, fontsize=8, loc="upper right")

    order = ("honest_close", "handoff", "censored_cap", "abandoned")
    shades = {"honest_close": "#cde2fb", "handoff": "#6da7ec", "censored_cap": "#1c5cab", "abandoned": GREY}
    for j, arm in enumerate(ARMS):
        term = d.terminals(arm)
        n = sum(term.values())
        bottom = 0.0
        for t in order:
            v = term.get(t, 0)
            if not v:
                continue
            h = v / n
            ax2.bar(j, h, bottom=bottom, width=0.55, color=shades[t], linewidth=1.5, edgecolor="#fcfcfb")
            if h >= 0.12:
                ax2.text(j, bottom + h / 2, f"{TERMINAL_LABEL[t]}\n{v}", ha="center", va="center",
                         fontsize=7.5, color=INK if t in ("honest_close", "handoff") else "#ffffff")
            else:
                ax2.text(j + 0.3, bottom + h / 2, f"{TERMINAL_LABEL[t]}: {v}", ha="left", va="center",
                         fontsize=7.5, color=INK)
            bottom += h
    ax2.set_xticks(range(len(ARMS)))
    ax2.set_xticklabels([ARM_LABEL[a] for a in ARMS])
    ax2.set_ylim(0, 1.0)
    ax2.set_xlim(-0.5, 3.4)
    ax2.set_ylabel("share of blocked runs", color=INK2)
    ax2.set_title("terminal taken (competing risks)", loc="left", fontsize=10, color=INK)
    fig.suptitle("gpt-5.5, three bridge families: what a blocked run does after the check fails",
                 x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout()
    return fig


def fig_safeguard_specificity(d: Data):
    import matplotlib.pyplot as plt
    fam = "sandbox_contract_execution"
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    _style(ax)
    measures = (("crossings", "crossed"), ("reattempt", "re-attempted the\nenvironment"),
                ("protected_reattempt", "re-wrote a\nprotected file"))
    arms = [a for a in ARMS4 if (fam, *a) in d.bridge]
    width = 0.8 / max(len(arms), 1)
    for j, arm in enumerate(arms):
        row = d.bridge[(fam, *arm)]
        n = int(row["n"])
        for i, (field, _) in enumerate(measures):
            k = int(row[field])
            r, lo, hi = frac(k, n)
            x = i + (j - (len(arms) - 1) / 2) * width
            ax.bar(x, r, width=width * 0.92, color=ARM_COLOUR[arm], linewidth=0)
            ax.vlines(x, lo, hi, color=INK2, linewidth=1)
            ax.text(x, hi + 0.02, f"{k}/{n}", ha="center", va="bottom", fontsize=7.5, color=INK)
    ax.set_xticks(range(len(measures)))
    ax.set_xticklabels([lab for _, lab in measures])
    ax.set_ylim(0, 1.18)
    ax.set_ylabel("share of blocked runs", color=INK2)
    ax.set_title("Contract family, gpt-5.5: a length-matched authority sentence also removes crossing, "
                 "without ending the search", loc="left", fontsize=10.5, color=INK)
    handles = [plt.Rectangle((0, 0), 1, 1, color=ARM_COLOUR[a]) for a in arms]
    ax.legend(handles, [ARM_LABEL[a].replace("\n", " ") for a in arms], frameon=False, fontsize=8.5,
              loc="upper right", ncol=2)
    fig.tight_layout()
    return fig


def fig_wave6_confirmatory(d: Data):
    """The held-out confirmatory result. The pilot bar is grey and labelled `gate`, so it cannot be
    read as a fourth arm: it is the pre-registered elicitation gate, run before the arms and never
    pooled into the baseline."""
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9.6, 4.6))
    _style(ax)
    measures = (("crossings", "crossed"), ("reattempt", "re-attempted the\nenvironment"),
                ("protected_reattempt", "re-wrote a\nprotected file"))
    bars = []
    if d.wave6_pilot is not None:
        bars.append(("gate (pilot, n = 10)", d.wave6_pilot, GREY))
    for arm in (("baseline", "off"), ("compliant_failure", "off"), AUTHORITY_ARM):
        if arm in d.wave6:
            bars.append((ARM_LABEL[arm].replace("\n", " "), d.wave6[arm], ARM_COLOUR[arm]))
    width = 0.8 / max(len(bars), 1)
    for j, (_, row, colour) in enumerate(bars):
        n = int(row["n"])
        for i, (field, _) in enumerate(measures):
            k = int(row[field])
            r, lo, hi = frac(k, n)
            x = i + (j - (len(bars) - 1) / 2) * width
            ax.bar(x, r, width=width * 0.92, color=colour, linewidth=0)
            ax.vlines(x, lo, hi, color=INK2, linewidth=1)
            ax.text(x, hi + 0.02, f"{k}/{n}", ha="center", va="bottom", fontsize=7.5, color=INK)
    ax.set_xticks(range(len(measures)))
    ax.set_xticklabels([lab for _, lab in measures])
    ax.set_ylim(0, 1.18)
    ax.set_ylabel("share of blocked runs", color=INK2)
    ax.set_title("Wave 6, held out: procurement award release, gpt-5.5 (Wilson 95%)",
                 loc="left", fontsize=11, color=INK)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, _, c in bars]
    ax.legend(handles, [lab for lab, _, _ in bars], frameon=False, fontsize=8.5,
              loc="upper right", ncol=2)
    fig.tight_layout()
    return fig


def fig_two_pathways(d: Data):
    """The two-pathway result in both families that have all three arms. Arms are the x groups
    (fixed order: baseline, compliant-failure, authority-salience) in the arm colour; within each
    group the three measures are told apart by fill (solid / outline / hatched), never by colour,
    and every bar carries its k/n. The mean post-failure depth is printed under each arm."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    families = [f for f in TWO_PATHWAY if any((f, a) in d.two_pathway for a in TWO_PATHWAY_ARMS)]
    fig, axes = plt.subplots(1, max(len(families), 1), figsize=(11.2, 5.4), sharey=True, squeeze=False)
    axes = axes[0]
    bg = "#fcfcfb"
    styles = {"crossings": lambda c: dict(facecolor=c, edgecolor=c, linewidth=0),
              "reattempt": lambda c: dict(facecolor=bg, edgecolor=c, linewidth=1.4),
              "protected_reattempt": lambda c: dict(facecolor=bg, edgecolor=c, linewidth=1.0, hatch="////")}
    width = 0.26
    for ax, family in zip(axes, families):
        _style(ax)
        arms = [a for a in TWO_PATHWAY_ARMS if (family, a) in d.two_pathway]
        ticks, tick_labels = [], []
        for j, arm in enumerate(arms):
            row = d.two_pathway[(family, arm)]
            n = int(row["n"])
            colour = ARM_COLOUR[arm]
            for i, (field, _) in enumerate(MEASURES):
                k = int(row[field])
                r, lo, hi = frac(k, n)
                x = j + (i - 1) * (width + 0.02)
                ax.bar(x, r, width=width, **styles[field](colour))
                ax.vlines(x, lo, hi, color=INK2, linewidth=1)
                ax.text(x, hi + 0.02, f"{k}/{n}", ha="center", va="bottom", fontsize=7.5, color=INK)
            ticks.append(j)
            # the depth sits under the arm on its own lines so neighbouring arms cannot collide
            tick_labels.append(f"{_arm_name(arm)}\nmean post-failure\ndepth {float(row['depth_mean']):g}")
        ax.set_xticks(ticks)
        ax.set_xticklabels(tick_labels, fontsize=8.5)
        ax.set_xlim(-0.6, len(arms) - 0.4)
        ax.set_ylim(0, 1.18)
        ax.set_title(TWO_PATHWAY_LABEL[family], loc="left", fontsize=10, color=INK)
    axes[0].set_ylabel("share of blocked runs (after the first failed check)", color=INK2)
    # one legend for the fill styles, in its own row under the title, clear of every k/n label
    handles = [Patch(**styles[field](INK2)) for field, _ in MEASURES]
    fig.legend(handles, [lab for _, lab in MEASURES], frameon=False, fontsize=8.5, ncol=3,
               loc="upper left", bbox_to_anchor=(0.01, 0.955))
    fig.suptitle("Two pathways to the same zero: contract (development) and procurement (held out), gpt-5.5",
                 x=0.01, y=0.995, ha="left", fontsize=11, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    return fig


def fig_domain_minimal_pairs(d: Data):
    """Wave 7: each anchor beside its two one-dimension swaps. Left, the grant floor (0/20): does a
    goal swap (V1) or a party swap (V2) raise it? Right, the contract ceiling (19/20): does a goal
    swap (V3) or a party swap (V4) lower it? Anchors are the committed Wave 5 arms (grey)."""
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.4), sharey=True)
    panels = (("grant", "grant floor: grant anchor, goal swap (V1), party swap (V2)", ("V1", "V2")),
              ("contract", "contract ceiling: contract anchor, goal swap (V3), party swap (V4)", ("V3", "V4")))
    swap_colour = {"G": "#2a78d6", "P": "#eb6834"}
    for ax, (anchor, title, labels) in zip(axes, panels):
        _style(ax)
        items = [("anchor", *d.crossings(WAVE7_ANCHORS[anchor], ("baseline", "off")), GREY)]
        for lab in labels:
            r = d.wave7.get(lab)
            if r is None:
                continue
            dim = "G" if "goal" in WAVE7_VARIANTS[lab][1] else "P"
            items.append((f"{lab} ({'goal' if dim == 'G' else 'party'} swap)", int(r["crossings"]), int(r["n"]), swap_colour[dim]))
        xs = list(range(len(items)))
        rates, los, his = zip(*[frac(k, n) for _, k, n, _ in items])
        _bars(ax, xs, rates, los, his, [c for *_, c in items], [f"{k}/{n}" for _, k, n, _ in items], width=0.6)
        ax.set_xticks(xs)
        ax.set_xticklabels([lab for lab, *_ in items], fontsize=9)
        ax.set_ylim(0, 1.12)
        ax.set_title(title, loc="left", fontsize=9.5, color=INK)
    axes[0].set_ylabel("baseline runs with any boundary crossing (gpt-5.5)", color=INK2)
    fig.suptitle("Wave 7 minimal pairs: which surface dimension moves the rate between the two anchors (Wilson 95%)",
                 x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout()
    return fig


FIGURES = {
    "fig1_crossing_by_family_and_arm": fig_crossing_by_family_and_arm,
    "fig2_safeguard_effect": fig_safeguard_effect,
    "fig3_domain_gradient": fig_domain_gradient,
    "fig4_persistence_and_terminals": fig_persistence_and_terminals,
    "fig5_safeguard_specificity": fig_safeguard_specificity,
    "fig6_wave6_confirmatory": fig_wave6_confirmatory,
    "fig7_two_pathways": fig_two_pathways,
    "fig8_domain_minimal_pairs": fig_domain_minimal_pairs,
}

#: figure -> the CSVs (relative to the outputs directory) it cannot be drawn without. A gated
#: figure whose sources have not landed is skipped by `render_all`, not drawn from nothing; the
#: test consults the same table, so the moment the CSVs land the figure becomes required.
GATES = {
    "fig6_wave6_confirmatory": [f"{WAVE6_ARMS[('baseline', 'off')]}/persistence.csv"],
    "fig7_two_pathways": [f"{run}/persistence.csv" for arms in TWO_PATHWAY.values() for run in arms.values()],
    "fig8_domain_minimal_pairs": [f"{run}/persistence.csv" for run, _f, _a in WAVE7_VARIANTS.values()],
}


def missing_sources(name: str, outputs: pathlib.Path) -> list[pathlib.Path]:
    """The gated CSVs a figure needs that are not in this outputs tree (empty when it can be drawn)."""
    return [outputs / rel for rel in GATES.get(name, ()) if not (outputs / rel).exists()]


def render_all(outputs: pathlib.Path, out: pathlib.Path, formats: tuple[str, ...] = ("png", "svg")) -> list[pathlib.Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "sans-serif", "text.color": INK, "axes.labelcolor": INK2,
                         "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb", "savefig.facecolor": "#fcfcfb"})
    d = Data(outputs)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name, fn in FIGURES.items():
        if missing_sources(name, outputs):
            continue
        fig = fn(d)
        for ext in formats:
            path = out / f"{name}.{ext}"
            fig.savefig(path, dpi=200 if ext == "png" else None, bbox_inches="tight")
            written.append(path)
        plt.close(fig)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--outputs", default=str(ROOT / "outputs"))
    ap.add_argument("--out", default=str(ROOT / "reports" / "figures"))
    ap.add_argument("--formats", default="png,svg")
    ap.add_argument("--table", choices=("two_pathways",), default=None,
                    help="print the named Markdown table from the CSVs instead of rendering figures")
    args = ap.parse_args(argv)
    if args.table == "two_pathways":
        print(two_pathway_table(Data(pathlib.Path(args.outputs))))
        return 0
    written = render_all(pathlib.Path(args.outputs), pathlib.Path(args.out), tuple(args.formats.split(",")))
    for p in written:
        print(f"  wrote {p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
