# Flex replay

The page follows one scheduling problem through diagnosis, an ordered policy diff, the evaluator verdict, and matched validation behavior. Every data panel labels its source. The tuned baseline remains beside each comparison.

The bundled fixture comes from `flex.sim` through `flex.evaluate.run`. It contains the incumbent and two hand-authored controls. None is supervisor-generated. Development runs supply the problem diagnosis. Only validation runs determine the displayed verdict. Verdicts and measurements are recomputed when the fixture is generated. The UI preserves evaluator reasons verbatim and uses structured verdict fields, including for retired versions kept in history.

## Run locally

Use Node 22.12 or newer. From `web/` run `npm ci`, then `npm run dev`. Open the URL printed by Vite. Static replay is the default.

From the application repository root, generate a fixture with `uv run python web/scripts/export_replay.py --fixture`. Export recorded Atlas data with `uv run python web/scripts/export_replay.py`. The latter uses only `flex.store.client('reader')` and needs Lane C's store implementation and reader credentials. Failed exports preserve the existing replay.

For local live mode, run `npm run live` in a second terminal. Open the Vite URL with `?mode=live`. The API binds to `127.0.0.1:4174`. It loads the repository root `.env` on the server and uses only `MONGODB_READER_URI`. It exposes one fixed read-only endpoint. Missing credentials, unavailable Atlas, or malformed records produce an error, never fixture fallback. Production builds reject live mode.

## Verify

Run `npm run build && npm test` from `web/`. The checks require the simulator fixture and production build. Run `uv run python web/scripts/check_fixture.py` from the repository root to check exported physics and validation verdicts. A normal recorded replay can replace the fixture for the page without running the fixture-specific checks.

The browser joins hours by `h` and jobs by `id`. Runs must match scenario, evaluator version, manifest, and scenario coverage. Before/after traces also require identical operating inputs and workload. Missing hourly data, job outcomes, or simulator diagnosis remain explicitly unavailable. Invalid rejected policies retain their evaluator reasons without requiring a renderable rule diff.

## Static deployment boundary

`npm run build` emits `dist/`. The only public data file is `public/replay.json`. The build has no MongoDB client, reader credentials, or server environment. The local API is not part of the static deployment.

`modelence.config.json` follows the requested `root: web` static build. Its schema is `https://cloud.modelence.com/schema/modelence.config.json?version=1`. The coordinator must place this config at the repository root before deployment because this lane can write only inside `web/`. Do not change the resource root to compensate for the temporary config location.

Modelence deployment requires Ricardo's approval and account. No deployment is included here. Atlas replay rendering remains a separate check after Lanes B and C land. The fixture makes no final-evaluation claim.

The browser check targets a production preview with the simulator fixture. Run `npm run preview -- --port 4173 --strictPort`, then `node scripts/browser_check.mjs` with an installed Playwright and Chrome. On Ricardo’s machine, set `PLAYWRIGHT_PACKAGE=/opt/homebrew/lib/node_modules/@playwright/mcp/package.json`. The check saves screenshots and a result log in ignored `web/evidence/`. It covers keyboard controls, mobile overflow, rejected and incomplete records, costly repairs, loading/errors, and disabled production live mode.
