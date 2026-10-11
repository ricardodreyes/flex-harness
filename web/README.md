# Flex recorded evaluation replay

[Live demo](https://flex-app-mv4dhmmqouu-prod.cloud.modelence.app)

The page follows a scheduler repair through its diagnosis, policy change, validation verdict, and hourly behavior. Every panel labels its evidence source. The seven pinned final scores come from `results/final.json`; references are labeled separately. Every pinned version met every final deadline, so the repair evidence is the validation verdict, not the final scores.

The lineage groups all proposals by evolution run while retaining their actual parent relationships. The featured repair is `g1-289b1a`; the featured rejection is `g4-4a14cc`. The behavior panel stays on `v0` versus `g1-289b1a` on `val-26-high`. A job's `done_h` is its last hour with work: completion occurs at the end of that hour.

The opening summary reports the recorded 30× restart-energy change and 10/12 → 12/12 validation repair. Four native links jump to the repair, policy, rejected proposal, and results. The policy link selects `g1-289b1a`. The rejection link and a fresh `#rejection` URL select `g4-4a14cc`.

The ablation beneath the seven-row scoreboard is labeled exploratory and after the freeze. `src/keepwarm-ablation.json` is an exact build-time copy of `results/exploratory-keepwarm-ablation.json`. The test checks byte equality and the displayed costs, completion counts, and reductions against the frozen baseline. Neither the frozen replay nor the final results are regenerated for this addition.

## Export

From the application repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT=web/.venv UV_CACHE_DIR=web/.cache/uv uv run python web/scripts/export_replay.py
```

The exporter reads Atlas through `flex.store.client("reader")` and atomically replaces `web/public/replay.json`. It includes version verdicts, run totals, jobs, diagnosis, frozen final scores, and the two focused hourly streams. Verdict reasons remain verbatim. Accepted versions are marked `repair` when `verdict.fixed` is nonempty, otherwise `cost`.

Hourly evidence and misses must match the attempt in the stored run summary. Incomplete hours, inconsistent identity, invalid jobs, or missing diagnosis fail before replacement. Every serialized string is scanned for credential patterns before any file write. A credential failure reports only its field path and preserves the existing replay.

Add `--fixture` to generate simulator fixtures. These use hand-authored controls and remain labeled fixture. They do not claim frozen final scores or supervisor lineage. Do not deploy a fixture in place of the final recorded replay.

## Local checks

Use Node 22.12 or newer. From `web/`:

```sh
npm ci && npm run build
npm test
npm run preview -- --port 4173 --strictPort
```

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT=web/.venv UV_CACHE_DIR=web/.cache/uv uv run python -m unittest discover -s web/tests -p 'test_*.py'
```

The browser check expects the recorded artifact. Run from `web/` with installed Playwright and Chrome:

```sh
PLAYWRIGHT_PACKAGE=/opt/homebrew/lib/node_modules/@playwright/mcp/package.json node scripts/browser_check.mjs
```

Screenshots and check results go into ignored `web/evidence/`. For a fixture export, `web/scripts/check_fixture.py` checks the simulator evidence.

## Static deployment

The demo has no live mode or database API. All browser requests use the static `replay.json`; `?mode=live` does not enable a server connection. Database access exists only in the local Python exporter. No MongoDB client or credentials ship with the app.

`modelence.config.json` specifies `node-22-slim`, service root `web`, `npm ci` followed by `npm run build`, and static `/` from `dist`. Modelence expects this config at its deployment root. Package a clean directory with that config and a nested `web/` containing only the frontend source, package files, Vite config, HTML entry, and public replay. Keep caches, environment files, Python tools, tests, and evidence outside the upload.

Follow the [Modelence deployment skill](https://modelence.com/skill.md) and [static setup instructions](https://docs.modelence.com/deploy/setup.md). Ricardo completes account selection and confirmation in the browser.
