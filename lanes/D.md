# Lane D: demonstration page (Codex)

Paste this into Codex opened in `app-web`. Run `git merge main` first, then read `lanes/README.md` and `flex/contract.py`. You own `web/` only.

The page tells one story in order. It's not a dashboard product.

1. The observed problem: training restarts became expensive, so the frozen tuned scheduler now misses deadlines. Show the late jobs, the restart count, and the warm-up energy, using the sim's own `diagnosis` lines.
2. The proposed change: the supervisor's rule and context-field diff against its parent, with its rationale and prediction. Rejected proposals stay visible with their verdict reasons.
3. The evaluation: the verdict, with fixed and regressed scenarios and the cost change. Show a cost increase plainly when the repair costs more.
4. The changed behavior: for one validation scenario, before and after over the same hours.
   - requested vs executed kW, overhead kW, price, and the event safety limit
   - each job's arrival, deadline, and completion

Always show the tuned baseline next to it: completed work, deadline results, and electricity cost. Show it winning where it wins.

Label every panel's source as one of "fixture", "recorded evaluation replay", or "live". Data comes from `flex.harness_versions`, `flex.runs`, `flex.hours`, and `flex.misses`, read only through the `reader` user on the server side. Database credentials never reach the browser.

Stack:
- A Vite + React page in `web/`. It runs locally in two modes:
  - Live: a small Node server in `web/server.js` reads Atlas through `MONGODB_READER_URI` from `.env` on the server side only.
  - Static: built from `web/public/replay.json`.
- `web/scripts/export_replay.py`, run with `uv run python web/scripts/export_replay.py`, writes `replay.json` from Atlas through `flex.store`. The coordinator runs it at the freeze. Every panel built from it is labeled "recorded evaluation replay".
- Fixtures for development come from calling `flex.sim` in the same script with `--fixture`.

Deploy target: Modelence Cloud as a static site. Ricardo approved deploying through https://modelence.com/skill.md when needed. Modelence runs Node only, and it can't reach the sandbox cluster without its IPs on our Atlas access list, which its docs don't publish. So the deployed page ships `replay.json` and holds no database credentials.
- Write `web/modelence.config.json` with `{"resources": {"web": {"type": "service", "root": "web", "image": "node-22-slim", "build": {"commands": ["npm ci", "npm run build"]}, "static": [{"path": "/", "dir": "dist"}]}}}`. Follow https://docs.modelence.com/deploy/setup.md for the `$schema` and for verifying the setup locally.
- The deploy itself (`npx modelence@latest deploy`) needs Ricardo's account. Stop and ask at that step.

Design for a projector: plain, one accent color, big numbers.

Check: the page renders from fixtures with every source label visible. Then it renders recorded evaluation replays from Atlas after Lanes B and C land.
