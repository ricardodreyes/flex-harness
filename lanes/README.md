# Lanes

Revised at 12:55 p.m. after the coordinator correction (`../../CLAUDE_RESTART_PROMPT.md`). This replaces the 12:20 version. The 12:20 savings figures came from an accounting defect and are void.

## What Flex is now

Flex adapts a training-power scheduler for an AI data center when operating conditions change. The first scenario raises the simulated cost of pausing and restarting training. A supervisor model reads the run diagnostics and proposes a changed policy: an ordered set of bounded rules plus the observation fields the policy may read. A fixed evaluator that the supervisor can't edit decides whether to accept it.

The tuned scheduler stays as the baseline. Its wins stay visible, and beating it on cost is not required. The problem statement is Recursive Harnessing.

Priorities, in order: physical limits, then deadlines and completed work, then electricity cost. A repair may cost more if it restores deadlines.

## Status

- B, C, and D are paused until the coordinator merges the corrected Lane A into `main` and says go.
- The prerequisite is the deterministic preflight, `uv run python -m flex.preflight`. Its result and the go/no-go are recorded in `../../HANDOFF.md`.

## Ownership

| Lane | Terminal | Worktree, branch | Owns |
| --- | --- | --- | --- |
| A | coordinator | `app-a`, `lane-a` | `flex/contract.py`, `flex/world.py`, `flex/policy.py`, `flex/sim.py`, `flex/scenarios.py`, `flex/evaluate.py`, `flex/tune.py`, `flex/preflight.py`, `policies/`, `data/`, `tests/test_physics.py`, `tests/test_policy.py`, `tests/test_evaluate.py` |
| B | Claude Code 2 | `app-b`, `lane-b` | `flex/supervisor.py`, `flex/evolve.py`, `flex/final.py`, `flex/telemetry.py`, `results/`, `tests/test_evolve.py` |
| C | Claude Code 3 | `app-c`, `lane-c` | `flex/store.py`, `db/`, `README.md`, `DEMO.md`, `SUBMISSION.md` |
| D | Codex | `app-web`, `lane-web` | `web/` |

Edit only what you own. `flex/contract.py` is frozen again. Ask the coordinator to change it rather than editing it yourself.

## Who writes each field

| Shape (`flex/contract.py`) | Written by | Read by |
| --- | --- | --- |
| `Policy` | B: the supervisor's proposal. A: baseline, reference, and control. | A validates and interprets it. C stores it. D shows it. |
| `Scenario`, `ScenarioSettings` (protected) | A, in `flex/scenarios.py` | everyone, read only. A candidate that touches them is rejected. |
| `Totals`, `JobOutcome`, `HourRecord`, `Miss`, `diagnosis` | A, in `flex.sim` | B uses dev runs only. C stores them. D shows them. |
| `Verdict`, `EvalIdentity` | A, in `flex.evaluate` | B records them. C stores them. D shows the reasons. |
| `HarnessVersion` (status candidate, champion, rejected, or retired) | B (author "supervisor"), A (authors "baseline" and "control") | C persists it. D shows the lineage. |
| `Run` | B builds it from A's results | C persists it. D shows it. |
| `champion` pointer | C's `promote`, atomic | B, D |

`author: "control"` marks the hand-authored repair. It proves the scenario is feasible. It is never shown to the supervisor, never stored as a supervisor version, and never presented as agent-generated.

## Data splits

| Split | Prices | Seeds | Used for |
| --- | --- | --- | --- |
| dev | Apr 1 to Jun 30, 2026 | 11, 12, 13 | Baseline tuning and the supervisor's evidence. Diagnosis lines and totals go into the prompt. |
| validation | Jul 1 to Sep 28, 2026. Seeds 24-26 overlap the Aug 30 window that was inspected and published earlier. | 21-26, each at low and high restart cost (12 scenarios, declared at 1:40 p.m. before any results) | The promotion gate. Repeated scoring here is selection feedback. Only the verdict reasons go back to the supervisor. |
| final | Sep 29 to Oct 10, 2026. Nobody had inspected these prices before they were reserved at 12:55 p.m. | 31, 32, 33 | One frozen comparison through `flex.final`. Never fed back into any repair. |

The final prices live outside the repo at `~/.config/flex/caiso_np15_dam_2026_final.json` (override with `FLEX_FINAL_PRICES`). Only `evaluate.run` and `evaluate.identity` read them, and only for final scenarios; a test with a file-read spy checks that. They're public CAISO data, and an older copy is in the public git history, so this is held out by procedure and file location, not secrecy. The supervisor model and the policy interpreter can't read files. The Python harness on this laptop can, so this isn't a security boundary. B must never put final data in a prompt. Say exactly that wherever isolation comes up.

## Acceptance rule

`flex.evaluate.accept` applies these in order:
1. An invalid candidate is rejected with the validator's reasons.
2. If the scenario sets differ, the candidate is rejected: "incomplete evaluation: missing X".
3. If any feasible scenario gets worse (more late job-hours, unfinished work, or cap interventions, or fewer completed jobs), the candidate is rejected: "regression on X: ...". Abandoning work can't win.
4. A candidate that passes a scenario the champion failed is accepted as a repair, with the cost change reported even when it costs more.
5. Fewer late hours without a pass is rejected as partial.
6. Otherwise reliability is identical. Accept only if training energy drops by more than 1% of |champion cost| ("cheaper: ..."). Increases read "not cheaper: ...".

Measured at 1:44 p.m.: the incumbent fails val-25-high (1 late job-hour) and val-26-high (4), and passes the other 10. The hand-authored control repair is accepted with "repairs val-25-high, val-26-high; training energy -1.20%". The restart_aware reference is rejected with "regression on val-21-high: late_job_hours 0 -> 1". A zero-power policy is rejected for regression.

A scenario passes with zero late job-hours, zero unfinished work, and zero cap interventions. Scenarios that are capacity-impossible or have infeasible hours are reported and excluded from pass/fail.

## Signatures

Lane A:
- `flex.scenarios.dev()`, `.validation()`, `.final()`, and `.by_id(id)`. `EVALUATOR_VERSION` is "2026-10-11.3".
- `flex.world.build_world(scenario, prices)`, `flex.world.prices(start, hours)`, and `flex.world.final_prices(start, hours)`. Only the final evaluator calls `final_prices`.
- `flex.policy.validate(policy) -> list[str]` and `flex.policy.compile_policy(policy)`.
- `flex.sim.simulate(world, policy, run_id, version_id) -> SimResult`.
- `flex.evaluate.run(policy, scenarios, version_id) -> dict[str, SimResult]`, `.passes(totals)`, `.accept(candidate_policy, champion_results, candidate_results) -> Verdict`, and `.identity(policy, scenarios) -> EvalIdentity`. `identity` hashes the supplied scenarios and only the price files their splits use. The field is still named `manifest_sha256`.
- `policies.incumbent.INCUMBENT`, frozen and tuned at low restart cost.
- `policies.restart_aware.RESTART_AWARE`, a separately retuned reference.
- `policies.control_repair.CONTROL_REPAIR`, the control.

Lane C:
- `flex.store.client(role)`, where role is one of `admin`, `supervisor`, `reader`, or `grader`.
- `save_version(v)`, `save_run(run, result)`, `promote(version_id, verdict)` (one transaction), `champion()`, `versions()`, and `recent_misses(kind=None, k=20)` (dev runs only).

Lane B:
- `uv run python -m flex.evolve --gens N`, where N is a cap and not a target.
- `uv run python -m flex.final`, run once after the freeze.

## Rules for every lane

- Commit to your branch. The coordinator merges into `main` after your lane's check passes. There are no fixed merge times.
- Never `git add -A`. Add explicit paths.
- Secrets live only in `.env`, which is gitignored and symlinked from `app/.env`. Never print, log, or commit them.
- No env template exists in the repo, and the hook blocks any `.env*` file. Variable names are listed in the coordinator's local handoff, not in the repo.
- Run Python with `uv run`. Tell the coordinator before adding a dependency.
- No generated-code execution anywhere: no `exec`, `eval`, or dynamic import of model output.
- Comments explain non-obvious reasons only.

## Restarting a paused lane

Your branch is clean at `0480304`. Start each lane with `git merge main`. That fast-forwards once the coordinator has merged the corrected Lane A. If git reports a conflict, stop and tell the coordinator. Never resolve it by discarding another lane's work.
