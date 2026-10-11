# Lanes

Flex is a power harness for AI data centers. A supervisor (Claude Opus 5.5) reads the site's misses and rewrites the operator's harness: its policy code, its context fields, its guardrails, and its tools. Every rewrite is graded on real CAISO prices and kept only if it wins on a window the agents can't read. The full plan is in `../../ARENA.md` and the approved plan file. The shared shapes are in `flex/contract.py`, which is frozen; ask the coordinator (Lane A) before changing it.

| Lane | Terminal | Worktree | Branch | Owns |
| --- | --- | --- | --- | --- |
| A | Claude Code, coordinator | `app-a` | `lane-a` | `flex/world.py`, `flex/sim.py`, `flex/sandbox.py`, `policies/`, `tests/test_sim.py`, `data/` |
| B | Claude Code 2 | `app-b` | `lane-b` | `flex/supervisor.py`, `flex/evolve.py`, `flex/final.py`, `flex/telemetry.py`, `tests/test_evolve.py` |
| C | Claude Code 3 | `app-c` | `lane-c` | `flex/store.py`, `db/`, `README.md`, `DEMO.md`, `SUBMISSION.md` |
| D | Codex | `app-web` | `lane-web` | `web/` |

Rules for every lane:
- Edit only files you own. If you need something from another lane, code against the function signatures below and stub them locally in your own files.
- Commit to your branch often. The coordinator merges into `main` at 1:30, 2:30, and 3:15 p.m. Don't push to `main`.
- Secrets live only in `.env`, which is gitignored and symlinked to the coordinator's copy. Never print, log, or commit them. The pre-commit hook in `scripts/hooks` blocks keys, certs, and Mongo URIs with passwords.
- Run Python with `uv run`. Add dependencies only after telling the coordinator.
- Keep comments to the non-obvious why. No phase narration.

## Signatures between lanes

Lane A:
- `flex.world.build_world(split: Split, prices: list[float], seed: int) -> World`. Pure: jobs and inference load are synthetic and seeded, and events are the top 10% price days from 16:00 to 20:00.
- `flex.world.local_prices(split) -> list[float]` reads `data/`. Use it only for tests and offline runs.
- `flex.sandbox.compile_policy(code: str, tools: list[str]) -> Callable[[Obs], float]`. Raises `PolicyError`.
- `flex.sim.simulate(world: World, version: HarnessVersion, run_id: str) -> SimResult`.
- `policies.v0.V0: HarnessVersion` is the fixed price threshold that ops teams run today.

Lane C:
- `flex.store.client(role: Literal["admin","operator","grader"])`.
- `load_prices(split) -> list[float]`. `test` needs the grader role.
- `save_version(v)`, `save_run(run: Run, result: SimResult)`, and `promote(version_id)`, which flips statuses and the `champion` pointer in one transaction.
- `champion() -> HarnessVersion`, `versions() -> list[HarnessVersion]`.
- `similar_misses(text: str, k: int) -> list[Miss]`, which uses vector search and falls back to the most recent misses of the same kind.

Lane B:
- `uv run python -m flex.evolve --gens N` and `uv run python -m flex.final`. `final` runs once per test and writes `runs` for v0 and the champion on `test`.
