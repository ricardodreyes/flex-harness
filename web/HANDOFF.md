# Lane D handoff

## Current behavior

The Vite React page renders four sections in order: the parent’s simulator diagnosis, ordered policy and context changes, the evaluator verdict, and matched validation behavior. Each data panel labels its source. The frozen tuned baseline stays beside each comparison with work, deadline, safety, and electricity totals. Rejected proposals remain selectable with their evaluator reasons.

The fixture contains 3 versions, 15 runs, and 10,440 hours. It runs `dev-12-low`, `dev-12-high`, and three validation scenarios through the real simulator. Both proposals are explicitly hand-authored controls. Validation verdicts use validation scenarios only. Every measurement and result comes from the exported records; no current cost or deadline result is built into the UI. No supervisor generation is claimed. Regenerate the fixture after evaluator changes; the measurements in screenshots are one captured run.

Static mode reads `public/replay.json`. Local `?mode=live` reads one fixed Node API endpoint. Only the server loads the repository root `.env` and `MONGODB_READER_URI`. Production live mode is disabled. Failed live reads never fall back to fixtures. The Python exporter calls only `flex.store.client('reader')` and atomically replaces the replay after successful serialization. Missing jobs or diagnosis remain unavailable.

## Changed files

- `src/main.jsx`, `src/style.css`: story, controls, SVG charts, baseline comparisons, job table.
- `src/replay.js`: contract field allowlists, identity validation, and comparison joins. Mismatched operating inputs or workloads cannot become comparisons.
- `scripts/export_replay.py`, `public/replay.json`: fixture generation and recorded replay export.
- `server.js`: localhost reader API with sanitized errors and fixed read operations.
- `tests/replay.test.js`, `scripts/check_fixture.py`, `scripts/browser_check.mjs`: data, physics, and browser checks.
- `package.json`, `package-lock.json`, `vite.config.js`, `index.html`: pinned build configuration.
- `modelence.config.json`: requested static deployment resource and official schema. The coordinator must place this at the repository root, retaining `root: web`, before deployment.
- `README.md`, `HANDOFF.md`, `.gitignore`: commands, evidence, and excluded local artifacts.

## Run and actual verification

From `web/`, run `npm ci && npm run dev`. For the built artifact, run `npm run build && npm run preview -- --port 4173 --strictPort`. Local verification used Node 25.2.1; the Modelence Node 22 image was not run.

Passed:

- `npm ci`, then `npm run build && npm test`: production build succeeded, 11 Node tests passed, dependency audit reported no vulnerabilities.
- From the repository root, `PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT=web/.venv UV_CACHE_DIR=web/.cache/uv uv run --frozen python web/scripts/export_replay.py --fixture`: 3 versions, 15 runs, 10,440 hours exported.
- With the same Python environment, `uv run --frozen python web/scripts/check_fixture.py`: fixture physics and validation verdicts verified for all 15 runs and 10,440 hours.
- `PLAYWRIGHT_PACKAGE=/opt/homebrew/lib/node_modules/@playwright/mcp/package.json FLEX_URL=http://127.0.0.1:4173 node scripts/browser_check.mjs`: production fixture, all source labels, keyboard and scenario controls, rejected reasons, 390px layout, absent jobs/diagnosis, malformed rejected proposals, long text, positive cost changes, empty/loading/error states, and disabled production live mode passed. Normal interactions produced no console warnings or errors. The intentional HTTP failure produced its expected console error.
- The localhost API without a reader URI returned sanitized 503 for `GET /api/replay`; `GET /.env`, `POST /api/replay`, and a query-controlled collection request returned 404.
- `python3 verify_workspace.py` from the hackathon workspace: 8 folders, 32 core documents, sources, deadlines, and local Markdown links passed.
- Independent read-only review found no actionable code or credential-boundary blockers.

Local screenshots, excluded from Git:

- `web/evidence/fixture-projector.png`: 1440×1080 first screen.
- `web/evidence/fixture-desktop.png`: full four-section page.
- `web/evidence/fixture-mobile.png`: 390px viewport.
- `web/evidence/fixture-rejected.png`: rejected proposal.
- `web/evidence/fixture-error.png`: unavailable replay.
- `web/evidence/browser-check.json`: browser check results.

## Incoming contract changes

`retired` versions remain valid as baselines, ancestors, and selectable historical proposals. Reasons are rendered verbatim; structured `accepted`, `fixed`, `regressed`, and `cost_delta_pct` fields drive the UI. Regression tests preserve the new repair, cost, regression, and incomplete-evaluation wording without parsing it. Fixture checks derive scenario lengths and current evaluator verdicts; browser controls derive their expected positions from loaded data.

## Next task and limits

Stopped at the fixture rendering check. `main` remains at `697536f` in this checkout; Lane B/C integration is not present. After those lanes land, export recorded Atlas evaluations and check the same page with real supervisor lineage and rejected proposals. Recorded runs must persist `jobs` and `diagnosis` extensions to populate those sections. Atlas success-path rendering is unverified.

The complete fixture is about 21 MB because it retains the rejected control’s misses. This is test evidence, not a performance claim. The page uses development and validation records only. No final scenario was executed or inspected; the existing evaluator identity hashes the manifest as part of normal identity generation.

No deployment or push was performed. Stop and ask Ricardo for approval and account access before running Modelence deployment.
