# Convenience targets. On Windows, run the underlying commands directly if make
# is unavailable (e.g. `uv run pytest`).

.PHONY: test lint smoke report controls figures wave6 wave7

test:
	uv run pytest -q

lint:
	uv run ruff check src tests

smoke:
	uv run ombs run --config configs/run.smoke.yaml

report:
	uv run ombs report --input outputs/smoke_admin_boundary/scores.jsonl

# Every mechanical design control in the repo, in one place. These check the
# claims the scenario READMEs make, rather than trusting their prose -- run them
# after editing any scenario and BEFORE spending money on a run.
controls:
	uv run python scenarios_w2/verify_control.py
	uv run python scenarios_study1/verify_study1.py
	uv run python scenarios_erosion/verify_erosion.py
	uv run python scenarios_sandbox/verify_sandbox.py
	uv run python scenarios_sandbox/rescore_family1.py
	uv run python scenarios_a5/verify_control.py
	uv run python experiments/w3_independence/corpus_xdoc/verify_corpus.py
	uv run python experiments/w3_independence/corpus_xdoc_ext/verify_corpus_ext.py
	uv run python experiments/w3_independence/corpus_xdoc_ext2/verify_corpus_ext2.py
	uv run python experiments/w3_independence/recheck_defect_rules.py
	uv run python scenarios_w2/summarize_w2.py

# The paper's core figures, regenerated from the committed report CSVs (no model, no spend).
# Output: reports/figures/*.png and *.svg. tests/test_figures.py runs the same generator.
figures:
	uv run python scenarios_sandbox/figures.py

# The Wave 6 confirmatory analysis: builds the combined report from the committed arm records and
# prints every pre-registered contrast. Free; re-run it after any arm lands.
wave6:
	uv run python scenarios_sandbox/wave6_analysis.py

# The Wave 7 domain-effect analysis: variants against their anchors' committed Wave 5 arms,
# the preregistered classifier (PREREG_WAVE7_DOMAIN_EFFECT.md). Free.
wave7:
	uv run python scenarios_sandbox/wave7_pairs.py --check
	uv run python scenarios_sandbox/wave7_analysis.py

# The third vendor on the frozen contract family, from the committed arm records
# (PREREG_THIRD_VENDOR_GEMINI.md). Free; re-run after any Gemini arm lands.
gemini:
	uv run python scenarios_sandbox/gemini_contract_analysis.py

# The compliant-failure wording-robustness study: three paraphrases per vendor against each
# vendor's committed baseline and canonical arm (PREREG_WORDING_ROBUSTNESS.md). Free.
wording:
	uv run python scenarios_sandbox/wording_analysis.py
