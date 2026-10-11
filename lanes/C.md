# Lane C: Atlas integration, access, factual docs

Paste this into Claude Code opened in `app-c`. Run `git merge main` first, then read `lanes/README.md` and `flex/contract.py`. The MongoDB MCP server is connected. Use the only project it lists, cluster `Cluster0`, MongoDB 8.0. Admin auth is X.509, configured in `.env`. Never print secrets.

1. `db/setup.py`, idempotent, so running it twice is clean. It creates:
   - Database `flex`:
     - `hours`, time-series with meta `{run, version, scenario}`, holding every `HourRecord` field
     - `runs`
     - `harness_versions`, with a `$jsonSchema` that mirrors `HarnessVersion`, including `policy`, `verdict`, `identity`, and `author`
     - `misses`
     - `champion`
   - Database `flex_final`: the final runs only.
   - Indexes for the page's queries.
   - Embeddings are optional. Skip them unless everything else is verified.
2. Users, created through the MCP with built-in roles scoped per database. Each URI goes only into `.env` as `MONGODB_<ROLE>_URI`.
   - `supervisor`: readWrite on `flex`
   - `reader`: read on `flex`, used by the web page server side
   - `grader`: readWrite on `flex_final` and read on `flex`
   - The X.509 admin is for setup only.
3. `flex/store.py`, with the signatures in `lanes/README.md`. `promote` flips the version's status and the `champion` pointer in one transaction.
4. `db/check.py` proves these against the real sandbox:
   - a version and a run round-trip
   - `promote` is atomic, because an injected failure inside the transaction leaves the old champion in place
   - `reader` can't write
   - `supervisor` can't read `flex_final`

   Paste its output in your report. Don't claim any of this works without that output.
5. `README.md`, `DEMO.md`, and `SUBMISSION.md`. State only facts.
   - Recursive Harnessing.
   - Built Oct 11, 2026.
   - CAISO NP15 day-ahead prices are real, while jobs, inference load, events, and the restart cost are simulated assumptions.
   - The split table from `lanes/README.md`, including that final prices live outside the repo and are held out by procedure and file location, not secrecy. A dethroned champion's status is "retired".
   - Texas SB 6 is motivation only, citing https://capitol.texas.gov/tlodocs/89R/billtext/html/SB00006F.htm. §39.170(a) covers a curtailment protocol during firm load shed. §39.170(b) is a separate ≥75 MW reliability service that excludes loads curtailing on wholesale prices, which this price-responsive scheduler is. The replay is California prices and doesn't show Texas compliance.
   - Results come only from `results/final.json`. Leave placeholders until then.

Check: the `db/check.py` output, plus `uv run python db/setup.py` run twice.
