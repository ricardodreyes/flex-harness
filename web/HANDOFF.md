# Lane D handoff

## Current behavior

The recorded exporter reads through `flex.store.client("reader")`. It retains version history and development/validation runs with totals, jobs, and diagnosis. Verdict reasons are preserved verbatim. Accepted versions carry `acceptance: "repair"` when `verdict.fixed` is nonempty, or `acceptance: "cost"` otherwise. Other versions carry null. Retired accepted repairs remain eligible.

The exporter selects the newest compatible accepted repair with a `val-26-high` run and writes `focus: {version, scenario}`. Only that repair and the matching frozen incumbent’s hourly streams are exported. Hours and misses are filtered by the attempt referenced by each run summary. Orphan evidence from a crashed save cannot enter the replay.

Before atomic replacement, the exporter checks run identities, finite totals, diagnosis, complete unique jobs, matching workloads, and complete matched hourly inputs. Missing or incompatible evidence leaves the existing artifact unchanged.

The page opens on the focused repair and scenario. Acceptance labels identify repairs and cost improvements. Charts and job outcomes compare the frozen incumbent against the proposal. Ordered policy changes and evaluator verdicts still refer to the actual parent. Every panel retains its source label. Credentials remain server-side. The production build reads only the static replay and browser assets.

## Merge and changed files

Merged main through `1cd5bff`, including the new evaluator contract and Lane C’s attempt-safe store. Changes authored in this lane remain under `web/`.

- `scripts/export_replay.py` selects, validates, and writes the focused replay.
- `scripts/check_fixture.py` checks exported hourly physics and every validation verdict.
- `src/replay.js` carries acceptance and focus, and joins baseline comparisons.
- `src/main.jsx` opens the focus and labels acceptance and comparison roles.
- `tests/test_export_replay.py` checks reader-only queries, stale attempts, invalid evidence, and preservation of existing output.
- `tests/replay.test.js` checks the replay consumer using an independently generated simulator fixture.
- `scripts/browser_check.mjs` checks the focused page and its failure states.
- `public/replay.json` remains a simulator fixture.
- `README.md` and `HANDOFF.md` record commands and current limits.

`modelence.config.json` was already correct. It remains in `web/` with `node-22-slim`, resource root `web`, commands `npm ci` and `npm run build`, and static path `/` from `dist`. Per Modelence’s setup instructions, the coordinator must put the config at the repository root before deployment while retaining `root: web`.

## Actual verification

- Generated the fixture using `uv run --frozen python web/scripts/export_replay.py --fixture`. It contains 3 versions, 42 run summaries, and exactly 1,392 hourly records for the two focused streams. Controls are explicitly hand-authored.
- `uv run --frozen python -m unittest discover -s web/tests -p 'test_*.py'` passed 15 tests. Missing, truncated, duplicate, or mismatched jobs and missing totals/diagnosis cannot replace an existing replay.
- `uv run --frozen python web/scripts/check_fixture.py` verified the exported hourly physics and all validation verdicts.
- Ran `npm ci && npm run build` under Node 22.23.3. The build succeeded and `dist/index.html` exists. `npm test` passed 13 tests, including the public asset credential boundary. npm reported no dependency vulnerabilities.
- The production browser check passed. It verified initial repair/scenario focus, acceptance labeling, charts, source labels, keyboard controls, mobile layout, rejected proposals, absent data, long text, positive cost changes, empty/loading/error states, and disabled production live mode. Normal interaction produced no console warnings or errors.
- The real Atlas reader connection succeeded. At the check, `flex.harness_versions` was empty and there were zero `val-26-high` runs. The real exporter exited with a sanitized error and preserved the fixture byte-for-byte. No recorded-success claim is made.
- An independent review found the missing-job export guard, which was fixed before commit. A fresh review passed the guard and all 15 Python tests with no further findings.

Python checks used `PYTHONDONTWRITEBYTECODE=1`, `UV_PROJECT_ENVIRONMENT=web/.venv`, and `UV_CACHE_DIR=web/.cache/uv` from the repository root. Browser verification used `PLAYWRIGHT_PACKAGE=/opt/homebrew/lib/node_modules/@playwright/mcp/package.json FLEX_URL=http://127.0.0.1:4173 node scripts/browser_check.mjs` from `web/`.

Local evidence is excluded from Git. `web/evidence/fixture-projector.png` is the first screen. `fixture-desktop.png` shows the complete page. `fixture-mobile.png`, `fixture-rejected.png`, and `fixture-error.png` cover other states. `browser-check.json` and `atlas-export-check.json` record results.

## Run and next step

From `web/`, run `npm ci && npm run dev`. For the static artifact, use `npm run build && npm run preview -- --port 4173 --strictPort`.

The local Modelence static build check is complete. Docker’s daemon was stopped, so the Linux `node-22-slim` image itself was not run. This lane stops here. No deployment, push, or database write was performed.

Ricardo will confirm when the final replay has been exported. Do not deploy before that confirmation. After it, follow `https://modelence.com/skill.md` and let Ricardo confirm the deployment in the browser. The current public artifact is still labeled fixture.
