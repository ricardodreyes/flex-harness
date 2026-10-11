# Lane D: replay page (Codex)

Paste this whole file into Codex opened in the `app-web` worktree. First read `lanes/README.md` and `flex/contract.py`. You own `web/` only.

Build one page for a 3-minute live demo. It's a replay of what the harness did, not a dashboard product.

1. The hero: two synced hourly timelines for one held-out stress day, v0 (the fixed rule ops teams run today) and the champion. Show price ($/MWh), training kW, inference kW, the curtailment window with its cap, and job deadlines. The champion ran training early at cheap hours and stayed under the cap. v0 didn't.
2. The lineage: every harness version in order, with its rationale, the code diff against its parent, train and gate net deltas, and accepted or rejected. Rejected ones stay visible, because the harness refusing a plausible edit is part of the story.
3. The scoreboard: v0 vs champion on the test month, with energy cost, late hours, missed curtailments, and net.

Data comes from MongoDB Atlas collections `flex.harness_versions`, `flex.runs`, and `flex.hours` (time-series, `{ts, run, version, price, train_kw, inference_kw, event, cost}`), read-only. Update live while evolution runs, through a change stream or Modelence live queries.

Stack: a Modelence app (`npx create-modelence-app@latest web`; docs at https://docs.modelence.com/hackathon/mongodb-2026), with `MONGODB_URI` set to the `web` read-only user from `.env` (Lane C creates it). Until 2:30 build against fixtures in `web/fixtures/*.json` that match the contract. If Modelence fights you for more than 20 minutes, use Next.js with `--webpack` (never Turbopack) instead. Design: plain and legible, built for a projector, with one accent color and big numbers.

Check: the page renders the fixture day and lineage by 2:30, and live Atlas data by 3:15.
