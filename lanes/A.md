# Lane A: simulator, grader, sandbox (coordinator)

Port `scratchpad/arena/candidate-3/headroom_probe.py` into `flex/world.py` and `flex/sim.py`, using the shapes in `flex/contract.py`. Prices are real CAISO NP15 day-ahead LMPs in `data/`. Fetch Apr 1 to Jun 30, 2026 from OASIS (PRC_LMP, DAM, TH_NP15_GEN-APND, at most 31 days per request) and merge them into one file keyed by the ISO hour.

- `sandbox.compile_policy` runs the version's code with restricted builtins (no `__import__`, `open`, or `eval`) and the granted helper tools injected. It clamps the returned fraction to [0, `guardrails.max_train_frac`]. The sim enforces `zero_during_event` and the event cap, whatever the code says.
- The sim passes only `version.context_fields` from `Obs` to `decide`.
- Misses: a `late` miss for each job-hour past its deadline, `over_cap` when the site is over `event_cap_kw` during an event, and `missed_event` once per event that wasn't honored.
- `policies/v0.py` is `decide = 0 if event_now or price > 60 else 1`, with context fields `["price", "event_now"]`.

Check: `uv run python -m flex.sim --version v0 --split test` must print net $16,188 with 0 late hours and 0 missed events. That's the probe's measured number for this window, with seed 7 for test. `tests/test_sim.py` asserts a literal cost on a fixed 48-hour world.
