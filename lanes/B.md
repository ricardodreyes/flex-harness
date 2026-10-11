# Lane B: supervisor, evolution, frozen final comparison

Paste this into Claude Code opened in `app-b`. Run `git merge main` first, then read `lanes/README.md`, `flex/contract.py`, `flex/evaluate.py`, and `flex/scenarios.py`. Read the `claude-api` skill before writing any model call.

Goal: the harness adapts itself through a model-generated policy change that the fixed evaluator accepts. A real rejected candidate stays in the record next to it.

1. `flex/supervisor.py`. One call to `claude-opus-5-5` per proposal.
   - Use structured output via `client.messages.parse`, with a schema that mirrors `Policy`.
   - Use adaptive thinking with effort `high`, and the server-side refusal fallback the skill describes.
   - The prompt gets only development evidence:
     - the champion's policy
     - its dev `Totals` and its `diagnosis` lines per dev scenario
     - recent dev misses
     - the meaning of each field in `OBS_FIELDS`
     - the bounds from `Policy`'s docstring
     - the last five rejected proposals with their `Verdict.reasons`
   - Never give it validation hours, final anything, protected settings as editable, or the control repair.
   - Ask for a rationale and a falsifiable prediction, such as "late hours on dev-12-high go from 5 to 0".
2. `flex/evolve.py`, run with `--gens N`, where N is a cap and stopping early is fine.
   - The champion starts as `INCUMBENT`. The condition being adapted to is the high restart cost: dev-*-high and validation.
   - Each generation:
     1. Run the champion on dev.
     2. Propose.
     3. Validate with `flex.policy.validate`. An invalid proposal is a rejected version with reasons.
     4. Run the champion and the candidate on validation.
     5. Apply `flex.evaluate.accept`.
     6. Save the version (author "supervisor", with verdict and identity), runs, and misses through `flex.store`.
     7. Promote when accepted.
   - Never load final scenarios.
3. `flex/telemetry.py` is optional Raindrop instrumentation (`raindrop-ai`, key `RAINDROP_WRITE_KEY`) with one interaction per proposal and its verdict. It's a no-op without the key. Don't claim it makes the entry prize-eligible.
4. `flex/final.py` runs once after the coordinator declares the freeze.
   1. Write `results/final_manifest.json` before any run. It holds `identity(policy, final())` for the incumbent, champion, restart_aware reference, and control.
   2. Run each one on `flex.scenarios.final()`.
   3. Write `results/final.json` and print the table.
   - The result must never feed another repair. Label any later rerun `exploratory` in its filename.

Integration check (the coordinator verifies it, not you):
- `uv run python -m flex.evolve --gens 6` against Atlas produces at least one accepted supervisor-authored version and at least one rejected one, both with reasons in Atlas.
- If no proposal is accepted, say so plainly. Don't edit proposals by hand or inject the control repair.
