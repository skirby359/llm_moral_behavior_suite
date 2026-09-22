Rescored sandbox_batch_release records: the committed runs re-read through the current scorer, so
every record carries the same field definitions whatever it was scored with at run time.
No model was called. The originals in the sibling directories are unmodified; regenerate
this directory with `python scenarios_sandbox/rescore_family1.py --family sandbox_batch_release --write <dir>`.
