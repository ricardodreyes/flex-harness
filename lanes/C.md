# Lane C: Atlas data layer, README, demo script

Paste this whole file into Claude Code opened in the `app-c` worktree. First read `lanes/README.md` and `flex/contract.py`. The MongoDB MCP server is connected. Project `ATLAS_PROJECT_ID`, cluster `Cluster0`, MongoDB 8.0. Admin auth is X.509, cert at `~/.config/atlas/X509_CERT_FILE`. URI and path are in `.env`.

1. `db/setup.py` must be idempotent, and running it twice must be clean. It creates:
   - in DB `flex`: time-series collections `prices` and `hours`, plus `runs`, `harness_versions` (with a `$jsonSchema` matching `HarnessVersion`), `misses`, and `champion`
   - in DB `flex_holdout`: the test prices
   - indexes for the page's queries
   - a Vector Search index on `misses.post_mortem` using automated embedding (Voyage). If the sandbox refuses auto-embed, record the error in the README and skip it.

   It loads prices from `data/` into the right split.
2. Database users through the MCP (`atlas-create-db-user`) with database-scoped built-in roles:
   - `operator`: `read` on `flex`
   - `supervisor`: `readWrite` on `flex`
   - `grader`: `read` on `flex_holdout`
   - `web`: `read` on `flex`

   Passwords go only into `.env` as `MONGODB_<ROLE>_URI`. Never print them.
3. `flex/store.py`: the functions in `lanes/README.md`. `promote` uses a transaction. `similar_misses` uses `$vectorSearch`, falling back to recent misses of the same kind.
4. `README.md`:
   - what Flex is, who it's for (Texas SB 6, Duke 76 GW, LBNL 6.7-12% by 2028, cited)
   - how the harness evolves
   - which MongoDB feature does which job
   - how to run it
   - a "Built at the hackathon on Oct 11, 2026" section
   - results copied from `flex.final` output only, so leave a placeholder until then

   Also `DEMO.md` (the 3-minute live script and the 1-minute video script) and `SUBMISSION.md` (the Cerebral Valley description).

Check by 1:30: `uv run python db/setup.py` runs twice cleanly, a fake run written through `store` shows up in Compass, and `operator` gets "unauthorized" on `flex_holdout`.
