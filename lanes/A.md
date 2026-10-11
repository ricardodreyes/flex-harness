# Lane A: physics, policy interpreter, evaluator, baselines (coordinator)

Revised at 12:55 p.m. A delegate is building this in `app-a`. The coordinator reviews it before anything merges.

What changed and why:
- The old sim billed requested power even with no queued work. On main, v0 drew 467,600 kWh of training energy for 299,131 kWh of queued work. The old tests asserted that defect, and both they and the $16,188 and $8,746 figures are void.
- Generated Python is gone. Policies are bounded JSON rules read by an interpreter (`flex/policy.py`). There's no `exec`, `eval`, or imports.
- Physical limits, the event cap, restart cost, and workload scale are protected scenario settings that the sim enforces for every policy.

Deliverables: `flex/world.py`, `flex/policy.py`, `flex/sim.py`, `flex/scenarios.py`, `flex/evaluate.py`, `flex/tune.py`, `flex/preflight.py`, `policies/incumbent.py`, `policies/restart_aware.py`, `policies/control_repair.py`, and the three test files listed in `lanes/README.md`.

Checks, run before merging:
- `uv run pytest -q` passes.
- `uv run python -m flex.tune` prints the frozen baseline parameters.
- `uv run python -m flex.preflight` prints PASS or FAIL.

PASS means all four hold:
- The frozen incumbent passes every dev scenario at low restart cost.
- It fails at least 2 of 3 dev scenarios at high restart cost, with diagnoses that name restarts.
- The control repair restores those without changing workload, deadlines, or grader.
- The impossible and over-cap scenarios are reported infeasible for every policy.

A FAIL stops the restart scenario. If it fails, the coordinator recommends a smaller alternative, such as a changed power-cap schedule, and doesn't adjust numbers until the scenario passes.
