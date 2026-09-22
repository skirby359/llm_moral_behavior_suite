# configs/frozen — run configs for the closed Family 1 (`sandbox_reconciliation`)

These eleven configs sampled the Wave 3 discovery family between 9 and 10 September 2026. The
family is registered `may_run: false` in `scenarios_sandbox/frozen_families.json`, so none of
them can run without `--allow-frozen`, and that flag exists to characterise the harness, never
to extend a result. They are kept, unedited, because they document what was run: each
`outputs/sandbox_*/config.yaml` is a copy of one of these, and `scenarios_sandbox/README.md`
cites them by name in the Wave 3 results.

Live configs (Family 2 and the Wave 5 bridge families) stay in `configs/`. The guards in
`tests/test_sandbox_configs.py` glob `configs/**/run.sandbox*.yaml`, so moving a config here
does not take it out from under them.
