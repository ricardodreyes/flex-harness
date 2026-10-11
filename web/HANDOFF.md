# Lane D final replay handoff

## Current behavior

Merged `main` through `ada741e` into `lane-web`. All authored changes remain under `web/`.

The demo is recorded-only. `server.js`, the live npm command, MongoDB JavaScript dependency, Vite API proxy, and live query branch were removed. The browser reads `/replay.json`, including when the URL contains `?mode=live`. Database credentials remain in the local Python export environment.

The Atlas export contains 12 versions, 184 development/validation run summaries, and 1,392 hourly records. Runs retain totals, jobs, and simulator diagnosis. Hours and misses match the attempt referenced by each stored run summary. Expected hour counts, matching inputs/workloads, identities, and complete jobs are checked before replacement. Verdict reasons render verbatim. Acceptance is `repair` when `verdict.fixed` is nonempty and `cost` otherwise.

Every serialized string and key passes the credential-pattern guard before the exporter creates or replaces a file. It rejects Anthropic token prefixes, credential-bearing MongoDB URIs, private-key headers, and `rdk_` prefixes. Errors name only the field path. Canary failures preserve the prior artifact.

The opening uses the ordinary expensive-restart case `dev-13-high`, comparing `v0` with the featured repair. It does not select the capacity-impossible stress case just because that case has more missed deadlines. The before/after panel stays on `v0` versus `g1-289b1a` on `val-26-high`, including after selecting a rejected proposal. Job completion is shown as the end of its last hour of work.

Lineage labels include both evolution run and generation, using checked run membership and the stored parent edges. Run 1 contains five proposals; run 2 contains six. Both `g1-289b1a` and rejected `g4-4a14cc` have featured verbatim reasons.

The scoreboard includes all seven pins from `results/final.json` in source order: five promoted versions and two labeled references. Final identities remain separate from development/validation identities. All seven met every final deadline. The page explicitly identifies the validation verdict as the repair evidence. Baseline `v0` lacks a version identity in Atlas, so the browser validates its final policy hash against its persisted run identities.

## Changed files

- `scripts/export_replay.py`: fail-closed credential boundary, seven final rows, explicit focus and evolution metadata.
- `scripts/check_fixture.py`: checks fresh simulator fixtures in memory without replacing the recorded release.
- `src/replay.js`, `src/main.jsx`, `src/style.css`: validated final scores, both lineages, pinned behavior, completion wording, recorded-only loading.
- `tests/test_credentials.py`, `tests/test_export_replay.py`, `tests/replay.test.js`: canaries, attempt/evidence guards, final metadata, baseline identity regression.
- `scripts/browser_check.mjs`: recorded artifact, source labels, seven scores, lineage, pinned behavior, responsive and failure-state checks.
- `public/replay.json`: actual reader export and frozen final scores.
- `package.json`, `package-lock.json`, `vite.config.js`: remove the live path and database dependency; `server.js` deleted.
- `README.md`, `HANDOFF.md`: run instructions, deployment boundary, verification and handoff.

## Verification

- Reproduced the old export vulnerability: `Before fix: all 14 credential canaries failed — ValueError not raised.`
- Repeated the original export-level canary after the fix: `Fixed: Credential pattern at $["versions"][0]["rationale"]; existing artifact unchanged.`
- Python unittest discovery: 18 tests passed. The credential canaries cover seven pattern variants in nested values and keys.
- Fixture physics check: 42 runs and 1,392 hours passed. It leaves the recorded artifact untouched.
- `uv run python web/scripts/export_replay.py` succeeded against Atlas with the reader client. The exported seven final rows exactly match `results/final.json`, including totals and costs.
- Node 22.23.3: clean `npm ci && npm run build` passed. `npm test` passed 16 tests. The clean install reported zero dependency vulnerabilities.
- Independent review caught the missing baseline identity assumption; it was fixed and regression-tested. Review of the actual recorded artifact then passed with seven rows, two evolution groups, and 696 paired hours.
- Production Chrome checks passed: recorded labels, seven exact scores, both reference labels, complete two-run lineage, verbatim featured reasons, pinned behavior, end-of-hour completion, keyboard slider, 390px layout, no normal console errors/warnings, and empty/loading/error/malformed/missing-evidence states.
- `python3 verify_workspace.py`: passed eight hackathon folders, 32 core documents, sources, deadlines, and local links.

Python commands run from the repository root with `PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT=web/.venv UV_CACHE_DIR=web/.cache/uv`. Browser checks use the installed Chrome and pinned Playwright MCP package.

Screenshots and reports are ignored local evidence under `web/evidence/`: `recorded-projector.png`, `recorded-desktop.png`, `recorded-mobile.png`, `recorded-scoreboard.png`, `recorded-lineage.png`, `recorded-error.png`, and `browser-check.json`.

## Deployment handoff

`modelence.config.json` uses `node-22-slim`, resource root `web`, `npm ci` then `npm run build`, and static `/` from `dist`. Deployment staging contains only this root config and an allowlisted nested frontend directory. Its only public data file is the credential-scanned replay. Environment files, Python code, tests, evidence, caches, and database clients are excluded.

Ricardo confirmed the Modelence browser request. The CLI reported `Deployed successfully.` after the `node-22-slim` cloud build and container startup. The actual uploaded archive contained exactly the nine reviewed files.

Live URL: https://flex-app-mv4dhmmqouu-prod.cloud.modelence.app

Release code commit: `bf8f362`, following canary reproduction commit `04cbc04`. The complete browser suite also passed against the live URL: the served replay exactly equals the exported artifact, all seven rows and both lineages render, and normal interaction has no browser errors or warnings. Screenshots now show the live deployment.

No push was performed. The demo intentionally has no live data mode. Final evaluation was read from the frozen results, not rerun during deployment. No required release work remains.
