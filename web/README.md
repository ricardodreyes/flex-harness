# Flex replay page

The page follows one scheduling problem through simulator diagnosis, ordered policy changes, an evaluator verdict, and matched validation behavior. Every data panel labels its source. The tuned baseline remains visible beside each comparison.

## Export a replay

From the application repository root, run `uv run python web/scripts/export_replay.py`. It reads Atlas through `flex.store.client("reader")` and atomically writes `web/public/replay.json`.

The export retains versions and development/validation run summaries with totals, jobs, and diagnosis. Verdict reasons stay verbatim. Accepted versions have `acceptance: "repair"` when `verdict.fixed` is nonempty, or `acceptance: "cost"` otherwise. Other versions have a null marker. Retired accepted versions remain eligible.

The exporter selects the newest compatible accepted repair with a `val-26-high` run. Its `focus` names that version and scenario. Only the selected repair and compatible incumbent’s hourly streams are exported. Hours and misses must match the attempt referenced by their run summary. Incomplete, duplicate, or incompatible comparison evidence fails without replacing the existing file.

For simulator evidence, run `uv run python web/scripts/export_replay.py --fixture`. This runs the real simulator and current validation evaluator. The proposals are hand-authored controls, never supervisor-generated. The fixture contains all validation summaries and the same bounded hourly comparison. Regenerate it after evaluator changes.

The chart and job table compare the frozen incumbent with the selected proposal. Policy changes and verdicts still refer to the proposal’s actual parent. No reason text or current cost measurement drives selection.

## Run locally

Use Node 22.12 or newer. From `web/`, run `npm ci`, then `npm run dev`. Static replay is the default.

For local live mode, run `npm run live` in a second terminal and open the Vite URL with `?mode=live`. The API binds `127.0.0.1:4174`. It loads the repository root `.env` only on the server and uses `MONGODB_READER_URI`. Production live mode is disabled. Failed live reads do not fall back to fixtures.

## Verify

From `web/`, run `npm run build && npm test`. JavaScript checks generate their own simulator fixture through the repository’s uv environment, so they do not require the public artifact to remain a fixture.

From the repository root, run `uv run python -m unittest discover -s web/tests -p 'test_*.py'`. For an exported simulator fixture, also run `uv run python web/scripts/check_fixture.py`.

For browser checks, generate a fixture, build, and run `npm run preview -- --port 4173 --strictPort`. Run `node scripts/browser_check.mjs` with an installed Playwright and Chrome. On Ricardo’s machine, set `PLAYWRIGHT_PACKAGE=/opt/homebrew/lib/node_modules/@playwright/mcp/package.json`. Screenshots and results go into ignored `web/evidence/`.

## Static deployment boundary

`modelence.config.json` uses `node-22-slim`, resource root `web`, build commands `npm ci` and `npm run build`, and static path `/` from `dist`. The build includes replay data and browser assets. It does not include the reader server, MongoDB client, or credentials.

The config is kept under `web/` as requested. Modelence’s deployment entry expects it at the repository root, so the coordinator must place it there while retaining `root: web` before deployment. See the [official setup instructions](https://docs.modelence.com/deploy/setup.md).

Do not deploy until Ricardo confirms that the final replay is exported. Then follow the requested Modelence skill and let Ricardo confirm in the browser. This lane’s local verification does not deploy anything.
