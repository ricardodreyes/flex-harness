# Lane B: supervisor and evolution loop

Paste this whole file into Claude Code opened in the `app-b` worktree. First read `lanes/README.md` and `flex/contract.py`.

Build the loop that makes the harness rewrite itself.

1. `flex/evolve.py`: `--gens N`. Each generation:
   1. Simulate the champion on `train`.
   2. Write a Haiku post-mortem for each distinct miss.
   3. Ask the supervisor for one edit.
   4. Compile it in the sandbox. A compile failure is a rejected candidate with the error kept.
   5. Score the candidate on `train` and `gate`.
   6. Accept only if `gate.net` improves on the champion's with no more `late_h` or `missed_events`. Otherwise reject.
   7. Save the version, its runs, and its misses, and promote if accepted.

   Never load `test` here.
2. `flex/supervisor.py`: one `claude-opus-5-5` call per generation via `client.messages.parse` with a pydantic or JSON-schema output of `{code, context_fields, guardrails, tools, rationale, predicted}`, using adaptive thinking. Add the server-side fallback beta (`betas=["server-side-fallback-2026-07-01"]`, `fallbacks="default"`). Read the `claude-api` skill before writing this. Its input is:
   - the champion's code and fields
   - the train totals and the top misses with post-mortems
   - `similar_misses` results
   - the full list of `OBS_FIELDS` and tools it may grant
   - the last 5 rejected edits with their reasons

   Post-mortems use `claude-haiku-5-5`, one sentence each.
3. `flex/telemetry.py`: Raindrop Python SDK (`raindrop-ai`, key `RAINDROP_WRITE_KEY`). Log one interaction per generation: input is the supervisor prompt summary, output is the edit, properties are the train and gate deltas, accepted, and the version id. Add a signal on rejected edits. It's a no-op if the key is missing.
4. `flex/final.py`: run v0 and the champion once on `test`, using the grader role for prices. Save the runs and print a table of energy cost, late hours, missed events, and net.

Run every candidate's `simulate` in a child process (`multiprocessing`, spawn context) with a 20 s timeout and an empty environment (`os.environ.clear()` in the child before compiling). A timeout counts as a rejected candidate. The sandbox's restricted builtins don't stop attribute-walking escapes or infinite loops, and the child must never see API keys.

Lane A is already on `main` (`git merge main` gets the real `simulate`, `build_world`, and `local_prices`). Until Lane C merges at 1:30, stub `simulate`, `store`, and `build_world` in your own test file, never in their files. Check by 2:15: `uv run python -m flex.evolve --gens 5` against Atlas accepts at least one edit, and the supervisor's rationale reads like an operator's note.
