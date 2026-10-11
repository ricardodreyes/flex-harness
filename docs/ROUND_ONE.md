# Three-minute judging demo

Show the failure, the repair, the rejected cheaper proposal, and the measured result. Most of the time goes to working behavior and implementation, which together account for 65% of the supplied judging rubric.

The website is a recorded evaluation replay. A fresh model generation is a separate live operation after the benchmark freeze. Keep both labels visible.

## Prepare the screens

Open the [demo](https://flex-app-mv4dhmmqouu-prod.cloud.modelence.app) in separate tabs and position each before starting. Selections are not saved in the URL. Reloading resets them.

1. **Validation behavior.** Find “Same hours. Same jobs. Different decisions.” Confirm `val-26-high`, `v0`, and `g1-289b1a`. The before/after table has four late job-hours versus zero. The opening “Observed problem” section is a different development case.
2. **Accepted repair.** In “Inspect a proposal,” select `g1-289b1a`. Show the policy and observation fields.
3. **Rejected proposal.** In a separate tab, select `g4-4a14cc`. Position the evaluator reason in view.
4. **Architecture.** Open the diagram in [DESIGN.md](../DESIGN.md).
5. **Results.** Open the final scoreboard, then the [cost chart](images/cost-comparison.png). The chart includes the exploratory ablation absent from the current website.

Set browser zoom and terminal font size for the projector. Close notifications. Keep account pages, environment files, and command history out of the presentation.

For a fresh generation, start the watcher before the timer:

```sh
uv run python -m flex.watch
```

Wait for `watching ...`. In a second terminal, stage this command without executing it:

```sh
uv run python -m flex.evolve --gens 1
```

That command calls the model, records evidence, and may replace the current Atlas champion. It does not change the frozen benchmark or the exported website replay. Run it once per deliberate rehearsal or presentation. Do not retry to obtain a better verdict.

## Narration and actions

The time slots include clicks and pauses. Use the matching live-outcome sentence at 1:40. Rehearse aloud to establish your actual pace.

| Time | What to show and do | What to say |
| --- | --- | --- |
| 0:00 to 0:20 | Validation before/after. At the end of this beat, press Enter on the staged generation command. | “I built Flex to repair an AI training scheduler when operating conditions change. Simulated restart energy rose thirtyfold. The original scheduler passed ten of twelve validation cases. Claude's repair passed all twelve. I'm starting one new proposal now.” |
| 0:20 to 0:45 | Return to `val-26-high`. Point to four late job-hours versus zero. Move the shared 96-hour slider once. | “This is a completed run. The original schedule finished a job four hours late. The repair completed the same work on time. Restarting consumes electricity before training resumes, so chasing cheaper power can backfire. The prices are real California electricity prices. The jobs and restarts are simulated.” |
| 0:45 to 1:15 | Accepted `g1-289b1a` policy. Point to the added fields and deadline margin. | “Here's what Claude changed. It added a four-hour deadline margin and kept jobs running when restarting would be expensive. It also added restart energy, running state, and time until a grid event to the scheduler's observations. The proposal is bounded JSON. Claude can change these rules and fields. The simulator and evaluator stay fixed.” |
| 1:15 to 1:40 | Rejected `g4-4a14cc`, with exact reason visible. | “This later proposal was about two and a half percent cheaper on validation. It still failed. It changed one case from zero late hours to one, so the evaluator rejected it. A cost reduction can't override a deadline regression on the validation suite.” |
| 1:40 to 2:05 | Return to the watcher for the outcome sentence below, then the architecture diagram. | **Use one outcome sentence below.** Then: “Atlas stores the versions, verdicts, and hourly evidence. Promotion is one transaction that changes the champion pointer and retires the old version together. The change stream lets us observe the committed result.” |
| 2:05 to 2:40 | Frozen scoreboard, then cost chart. Keep the exploratory label visible. | “On three separate test workloads, all seven policies completed thirty-eight jobs on time. The frozen champion cut training electricity cost twelve percent. But most of that saving depends on a rule that keeps jobs warm at one percent power. Removing it reduced the saving to four percent, behind both hand-tuned references. That ablation happened after the benchmark freeze.” |
| 2:40 to 3:00 | Hold chart, then return to repair if time permits. | “The result is a repair we can inspect, a cheaper change the system refused, and a clear limit on the savings claim. Next I'd test the warm-up behavior against hardware and expand the regression suite.” |

Choose exactly one live-outcome sentence:

- **Accepted and pointer event observed:** “The new proposal passed, and this champion-pointer event confirms that promotion committed.”
- **Rejected:** “The new proposal was rejected. The evaluator kept the current champion and recorded this reason.”
- **Accepted without pointer event yet:** “The candidate passed evaluation. Promotion hasn't been confirmed by the watcher yet.”
- **Still running:** “This generation is still running. The completed records show the full evaluation path.”
- **Failed or disconnected:** “The live result isn't confirmed. I'll continue with the recorded evaluation and its saved evidence.”

If you omit the fresh generation, replace “I'm starting one new proposal now” with “I'll walk through the saved evaluation.” At 1:40, say “Each saved proposal includes its verdict and reason,” then continue with the Atlas explanation. Do not describe a replay as a live database feed.

## Answers for the next two minutes

| Likely question | Answer |
| --- | --- |
| What is improving? | Claude changes the scheduling rules and the fields the scheduler observes. The model weights and evaluator stay fixed. |
| Why MongoDB? | Atlas stores the policy lineage and hourly evidence. Transactions make champion replacement atomic. A read-only change stream reports changes. |
| What's harder than a few prompts? | The policy interpreter, reliability gate, matched evidence, crash recovery, database permissions, and atomic promotion. Hourly time-series writes use attempt IDs and a summary pointer so interrupted saves don't replace a complete result with partial evidence. |
| Did it really save 12%? | In this simulator, yes, against the frozen incumbent's training electricity cost. The keep-warm ablation reduced the saving to 4.28%. We have not measured savings on real hardware. |
| Did the final test prove the repair? | No. All policies met final deadlines. Validation established the 10/12 to 12/12 repair; the frozen final comparison measured cost. |
| Can it game its evaluator? | It cannot edit the evaluator or run arbitrary generated code. It can still exploit an inaccurate simulator assumption, as the keep-warm result shows. |
| Does every accepted change avoid regressions? | The gate checks twelve validation scenarios. The frozen champion has a disclosed two-hour regression on a development case. Expanding that coverage is a next step. |
| Is the result repeatable? | The frozen outputs and identity hashes are committed. The model's next proposal is not guaranteed to repeat. The final price file was kept separately and is not bundled with the repository. |

## Offline evidence

Keep these files open locally before entering the room:

- [Validation before/after](images/validation-repair.png).
- [Accepted policy](images/policy-repair.png).
- [Rejected proposal](images/rejected-proposal.png).
- [Cost and ablation chart](images/cost-comparison.png).
- [Design explanation](../DESIGN.md).

The replay can also run from an existing frontend build through a localhost static server. See [web setup](../web/README.md). A working offline replay is the first fallback; static captures are the second.

Do not run `db/check.py`, database setup, `flex.final`, or the replay exporter during the demo. `evolve --dry-run` still calls the model and may emit telemetry, so it is not an offline rehearsal mode.
