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
7. Promotes the candidate if the evaluator accepted it.

The tuned incumbent stays as the baseline. A repair doesn't need to beat it on cost.

## The acceptance rule

Priorities, in order, are physical limits, then deadlines and completed work, then electricity cost. A repair may cost more if it restores deadlines.

`flex.evaluate.accept` applies these steps in order:

1. An invalid candidate is rejected with the validator's reasons.
2. A candidate that fails any validation scenario the champion passes is rejected for regression.
3. A candidate that passes a scenario the champion failed is accepted as a repair. Its cost change is reported even when the cost goes up.
4. Fewer late hours without a pass is logged as partial progress and rejected.
5. Otherwise the pass set is identical, and the candidate is accepted only if training energy cost drops by more than 1%.

A scenario passes with zero late job-hours, zero unfinished work, and zero cap interventions. Scenarios that are capacity-impossible or that have infeasible hours are reported and left out of pass and fail.

## Data splits

| Split | Prices | Seeds | Used for |
| --- | --- | --- | --- |
| dev | Apr 1 to Jun 30, 2026 | 11, 12, 13 | Baseline tuning and the supervisor's evidence. Diagnosis lines and totals go into the prompt. |
| validation | Jul 1 to Sep 28, 2026, including the Aug 30 window that was inspected and published earlier | 21, 22, 23 | The promotion gate. Repeated scoring here is selection feedback. Only the verdict reasons go back to the supervisor. |
| final | Sep 29 to Oct 10, 2026. Nobody had inspected these prices before they were reserved at 12:55 p.m. on Oct 11. | 31, 32, 33 | One frozen comparison through `flex.final`. Never fed back into any repair. |

The final prices live outside the repo, in `~/.config/flex`. That isolation is procedural plus file location. It isn't a security boundary. The policy interpreter can't read files, and the supervisor's prompt never contains final data.

## What each MongoDB feature does

- A time-series collection, `flex.hours`, holds one document per simulated hour, with `{run, version, scenario}` as its meta field.
- A `$jsonSchema` validator on `flex.harness_versions` rejects any version whose policy, verdict, identity, author, or status doesn't match the contract.
- A multi-document transaction in `flex.store.promote` moves the `champion` pointer and flips the version statuses together. `db/check.py` injects a failure inside that transaction and shows the old champion stays in place.
- Separate database users with built-in roles scoped per database:
  - `supervisor` has `readWrite` on `flex` and writes versions, dev and validation runs, and promotions.
  - `reader` has `read` on `flex` and serves the web page's server side.
  - `grader` has `readWrite` on `flex_final` and `read` on `flex`. `flex.store.save_run` sends every final-split run there.
  - An X.509 admin user runs `db/setup.py` and the cleanup in `db/check.py`, and nothing else.
- A separate database, `flex_final`, holds the final runs. `supervisor` can't read it.

## Run it

Install [uv](https://docs.astral.sh/uv/), then put the Atlas connection strings, the X.509 certificate path, and the Anthropic key in `.env` at the repo root. `.env` is gitignored, and the pre-commit hook in `scripts/hooks` blocks env files, keys, certificates, and Mongo URIs with passwords.

```sh
uv run pytest -q                              # physics, policy validation, acceptance rule
uv run python -m flex.preflight               # checks the scenario has a real, repairable problem
uv run python db/setup.py                     # creates collections, validators, and indexes; safe to rerun
uv run python db/check.py                     # proves the store against Atlas
uv run python -m flex.evolve --gens 6         # 6 is a cap, not a target
uv run python -m flex.final                   # once, after the freeze
```

## Results

Results come only from `results/final.json`, written once by `flex.final`.

| Policy | Final scenarios passed | Late job-hours | Unfinished kWh | Training energy cost |
| --- | --- | --- | --- | --- |
| incumbent | [RESULT] | [RESULT] | [RESULT] | [RESULT] |
| supervisor champion | [RESULT] | [RESULT] | [RESULT] | [RESULT] |
| restart-aware reference | [RESULT] | [RESULT] | [RESULT] | [RESULT] |
| control repair | [RESULT] | [RESULT] | [RESULT] | [RESULT] |

The control repair is hand-written. It proves the scenario can be repaired. The supervisor never sees it, and it isn't agent-generated.

## Why large-load curtailment matters

Texas SB 6 is the motivation, nothing more. The bill text is at https://capitol.texas.gov/tlodocs/89R/billtext/html/SB00006F.htm. §39.170(a) covers a curtailment protocol during firm load shed. §39.170(b) is a separate reliability service for loads of 75 MW or more, and it excludes loads that curtail on wholesale prices. Flex is a price-responsive scheduler, so it is one of those loads. The replay uses California prices and doesn't show Texas compliance.

## Built at the hackathon on Oct 11, 2026

Everything in this repo was built on Oct 11, 2026, at Harness Engineering & Model Wrangling, the MongoDB hackathon at SF Tech Week.
