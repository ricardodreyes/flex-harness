# Flex

Flex adapts the training-power scheduler of an AI data center when operating conditions change. A supervisor model reads the scheduler's development diagnostics and proposes a changed policy. A fixed evaluator that the supervisor can't edit decides whether to accept the change. MongoDB Atlas stores every version, run, hour, miss, and verdict, and holds the pointer to the current champion.

Flex targets the Recursive Harnessing problem statement: a harness that changes its own rules and context to fit a task.

## What is real and what is simulated

The electricity prices are real. They're CAISO NP15 day-ahead prices for 2026.

Everything else is a simulated assumption:

- the training jobs, their arrival times, and their deadlines
- the inference load
- the grid events and the site power cap during them
- the restart cost, which is the warm-up energy a cold job draws before it makes progress

The results describe this simulation only. They aren't evidence of savings or reliability at a real site.

## How the policy adapts

A policy is an ordered list of at most 8 rules. Each rule has at most 4 conditions over named observation fields and a training power between 0 and 1. The first matching rule wins. If no rule matches, the policy uses `default_power`. The whole policy is JSON of at most 4,096 bytes. `flex/policy.py` validates and interprets it. No model output is ever executed as code.

The first scenario raises the simulated restart cost from 35 kWh to 1,050 kWh of warm-up per cold start. The incumbent scheduler was tuned at the low restart cost and then frozen.

Each generation of `flex.evolve` does the following:

1. Runs the champion on the dev scenarios.
2. Sends the supervisor (`claude-opus-5-5`) the champion's policy, its dev totals and diagnosis lines, recent dev misses, the field meanings, the policy bounds, and the reasons the last five proposals were rejected.
3. Validates the proposal. An invalid proposal is stored as a rejected version with the validator's reasons.
4. Runs the champion and the candidate on the validation scenarios.
5. Applies `flex.evaluate.accept`.
6. Saves the version, its runs, and its misses to Atlas.
7. Promotes the candidate if the evaluator accepted it. The old champion's status becomes `retired`.

The tuned incumbent stays as the baseline. A repair doesn't need to beat it on cost.

## The acceptance rule

Priorities, in order, are physical limits, then deadlines and completed work, then electricity cost. A repair may cost more if it restores deadlines.

`flex.evaluate.accept` applies these steps in order:

1. An invalid candidate is rejected with the validator's reasons.
2. A candidate that wasn't run on exactly the champion's scenarios is rejected as an incomplete evaluation.
3. A candidate that makes any feasible scenario worse is rejected for regression. Worse means more late job-hours, more unfinished work, more cap interventions, or fewer completed jobs. Abandoning work can't win.
4. A candidate that passes a scenario the champion failed is accepted as a repair. Its cost change is reported even when the cost goes up.
5. Fewer late hours without a pass is rejected as partial progress.
6. Otherwise no scenario got worse and none was repaired. The candidate is accepted only if training energy cost drops by more than 1% of the champion's cost.

A scenario passes with zero late job-hours, zero unfinished work, and zero cap interventions. Scenarios that are capacity-impossible or that have infeasible hours are reported and left out of pass and fail.

## Data splits

| Split | Prices | Seeds | Used for |
| --- | --- | --- | --- |
| dev | Apr 1 to Jun 30, 2026 | 11, 12, 13 | Baseline tuning and the supervisor's evidence. Diagnosis lines and totals go into the prompt. |
| validation | Jul 1 to Sep 28, 2026. Seeds 24, 25, and 26 overlap the Aug 30 window that was inspected and published earlier. | 21 to 26, each at low and high restart cost, so 12 scenarios declared before any run on them | The promotion gate. Repeated scoring here is selection feedback. Only the verdict reasons go back to the supervisor. |
| final | Sep 29 to Oct 10, 2026. Nobody had inspected these prices before they were reserved at 12:55 p.m. on Oct 11. | 31, 32, 33 | One frozen comparison through `flex.final`. Never fed back into any repair. |

The final prices live outside the repo, at `~/.config/flex/caiso_np15_dam_2026_final.json`. Set `FLEX_FINAL_PRICES` to read them from another path. Only `flex.evaluate` opens the file, in `run` to simulate and in `identity` to hash it, and only for final-split scenarios. `tests/test_evaluate.py` checks that dev and validation evaluation never opens it. They're public CAISO data, and an older copy is in the public git history. They're held out by procedure and file location, not secrecy, and that isn't a security boundary. The policy interpreter can't read files, and the supervisor's prompt never contains final data.

## What each MongoDB feature does

- A time-series collection, `flex.hours`, holds one document per simulated hour, with `{run, version, scenario}` as its meta field.
- A `$jsonSchema` validator on `flex.harness_versions` checks the envelope of every version: `_id`, `parent`, `rationale`, `predicted`, `created_at`, the `author` and `status` enums, and the shapes of `verdict` and `identity`. Status is `candidate`, `champion`, `rejected`, or `retired`. Atlas accepts any object as `policy`, so a rejected malformed proposal is still stored. `flex.policy.validate` enforces the policy contract.
- `flex.store.save_run` can't use a transaction, because time-series writes can't join one. It inserts the new hours and misses under a fresh attempt id, then points the `runs` summary at that attempt, then deletes older attempts. `flex.store.run_record` reads only the attempt the summary points at, so a crash at any step leaves a complete result readable. `db/check.py` injects a failure between each pair of steps to prove it.
- A multi-document transaction in `flex.store.promote` moves the `champion` pointer, retires the old champion, and marks the new one champion, all together. `db/check.py` injects a failure inside that transaction and shows the old champion stays in place.
- Separate database users with built-in roles scoped per database:
  - `supervisor` has `readWrite` on `flex` and writes versions, dev and validation runs, and promotions.
  - `reader` has `read` on `flex` and serves the web page's server side.
  - `grader` has `readWrite` on `flex_final` and `read` on `flex`. `flex.store.save_run` sends every final-split run there.
  - An X.509 admin user runs `db/setup.py` and the cleanup in `db/check.py`, and nothing else.
- A separate database, `flex_final`, holds the final runs. `supervisor` can't read it.

## Run it

Install [uv](https://docs.astral.sh/uv/). These steps need no credentials:

```sh
uv sync
uv run pytest -q                                                      # physics, policy validation, acceptance rule
uv run python -m flex.preflight                                       # checks the scenario has a real, repairable problem
uv run python -m flex.sim --policy incumbent --scenario dev-12-high   # one run; prints totals and diagnosis lines
```

`flex.sim` takes a module name from `policies/` and a scenario id from `flex/scenarios.py`. It refuses final scenarios.

The Atlas and supervisor steps need `.env` at the repo root with the Atlas connection strings, the X.509 certificate path, and the Anthropic key. `.env` is gitignored, and the pre-commit hook in `scripts/hooks` blocks env files, keys, certificates, and Mongo URIs with passwords.

```sh
uv run python db/setup.py                     # creates collections, validators, and indexes; safe to rerun
uv run python db/check.py                     # proves the store against Atlas
uv run python -m flex.evolve --gens 6         # 6 is a cap, not a target
```

`flex.final` also needs the final prices at `~/.config/flex/caiso_np15_dam_2026_final.json`, or at the path in `FLEX_FINAL_PRICES`. The repo doesn't include that file, and `data/fetch_caiso.py` doesn't write it.

```sh
uv run python -m flex.final                   # once, after the freeze
```

## Results

`flex.final` ran once, at 14:43 PDT on Oct 11, on final-31, final-32, and final-33 (Sep 29 to Oct 10, 2026 prices). Every number here comes from `results/final_manifest.json`, `results/final.json`, `results/final.log`, and the version records in Atlas.

On the 3 final scenarios, every pinned version met every deadline, including the frozen incumbent `v0`. So the final set doesn't test the repair. The repair evidence is validation, where the evaluator accepted `g1-289b1a` with "repairs val-25-high, val-26-high; training energy -1.93%".

| Version | What it is | Final scenarios passed | Late job-hours | Unfinished kWh | Summed training energy | vs v0 |
| --- | --- | --- | --- | --- | --- | --- |
| `v0` | frozen incumbent | 3 of 3 | 0 | 0 | $17,924.46 | |
| `g1-289b1a` | supervisor, the validation repair | 3 of 3 | 0 | 0 | $18,241.62 | +1.77% |
| `g5-683c0e` | supervisor | 3 of 3 | 0 | 0 | $16,135.24 | -9.98% |
| `g4-eac5bd` | supervisor | 3 of 3 | 0 | 0 | $16,061.45 | -10.39% |
| `g5-e942f4` | supervisor, current champion | 3 of 3 | 0 | 0 | $15,741.65 | -12.18% |
| `restart_aware` | hand-tuned reference | 3 of 3 | 0 | 0 | $16,695.84 | -6.85% |
| `control` | hand-written control repair | 3 of 3 | 0 | 0 | $16,781.72 | -6.38% |

The champion beat both hand-tuned references on training energy.

Two evolve runs wrote 12 versions to Atlas, the seed `v0` and 11 supervisor proposals. The evaluator rejected 7 of them with reasons. One is `g4-4a14cc`, rejected with "regression on val-26-high: late_job_hours 0 -> 1". Four accepted versions were later retired, and `g5-e942f4` is the champion. Raindrop recorded 17 proposal events, read from its dashboard at 2:40 p.m.

The control repair is hand-written. It proves the scenario can be repaired. The supervisor never sees it, and it isn't agent-generated.

## Known limitations

- The promotion gate scores only the 12 validation scenarios. The final champion, `g5-e942f4`, has 2 late job-hours on dev-13-high, where its parent `g4-eac5bd` had none. Rerunning both policies from Atlas on dev-13-high measures that. The evaluator didn't change after anyone saw it. Both versions carry evaluator version `2026-10-11.3`, which is still the current one.
- `flex.store.save_run` assumes one writer per run id. Two concurrent saves of the same run can delete each other's evidence and leave the summary pointing at an attempt that no longer exists.
- Final-price isolation is procedure plus file location, not a security boundary. See [Data splits](#data-splits).

## Why large-load curtailment matters

Texas SB 6 is the motivation, nothing more. The bill text is at https://capitol.texas.gov/tlodocs/89R/billtext/html/SB00006F.htm. §39.170(a) covers a curtailment protocol during firm load shed. §39.170(b) is a separate reliability service for loads of 75 MW or more, and it excludes loads that curtail on wholesale prices. Flex is a price-responsive scheduler, so it is one of those loads. The replay uses California prices and doesn't show Texas compliance.

## Built at the hackathon on Oct 11, 2026

Everything in this repo was built on Oct 11, 2026, at Harness Engineering & Model Wrangling, the MongoDB hackathon at SF Tech Week.
