# Demo scripts

Restart costs rose 30x (35 to 1,050 kWh per cold start). The frozen scheduler passed 10 of 12 validation scenarios. Claude's first accepted repair passed 12 of 12, and every later champion kept 12 of 12. On 12 unseen days the champion at the freeze (`g5-e942f4`) cut training electricity cost 12.18% with zero missed deadlines. An ablation after the freeze shows most of that comes from one rule that holds paused jobs at 1% power to stay warm, which our simulator allows and real GPUs likely don't. Without that rule the saving is 4.28%, behind both hand-tuned references.

Both scripts show only work built on Oct 11, 2026. Every number comes from `results/final.json` or from the runs and versions in Atlas, the same numbers as the README. The spoken lines round dollar amounts; put the exact figures on screen. Verdict reasons say "training energy"; the number is training electricity cost in dollars.

## One-minute video

About 150 spoken words in five beats, timed at 150 words a minute.

**0:00 to 0:12. The problem.**
Show: the incumbent's validation runs, with the restart cost raised from 35 kWh to 1,050 kWh.
Say: "Restarts got expensive in our simulated AI data center. One cold start now burns a thousand and fifty kilowatt-hours of warm-up. The frozen scheduler starts missing deadlines on two validation scenarios."

**0:12 to 0:26. The repair.**
Show: version `g1-289b1a` and its verdict, "repairs val-25-high, val-26-high; training energy -1.93%".
Say: "Claude reads the misses and rewrites the scheduler's rules. A fixed evaluator it can't edit checks the change. Ten of twelve became twelve of twelve. And its training electricity cost fell almost two percent."

**0:26 to 0:36. A refusal.**
Show: version `g4-4a14cc` and its verdict, "regression on val-26-high: late_job_hours 0 -> 1".
Say: "Not every edit gets in. This one looked reasonable. But it made one job an hour late. The evaluator called it a regression and refused it."

**0:36 to 0:49. The held-out result.**
Show: the final table. Champion at the freeze `g5-e942f4` at $15,741.65 against `v0` at $17,924.46, -12.18% training electricity cost. Then the ablation: $17,157.39, -4.28%, without the 1% keep-warm rule.
Say: "On twelve unseen days it met every deadline and cut cost twelve percent. Most of that came from a keep-warm trick our simulator allows, so we checked. Without it, four percent."

**0:49 to 1:00. MongoDB.**
Show: Atlas Data Explorer on `harness_versions`.
Say: "Every version, verdict and run lives in MongoDB Atlas. Each part signs in as its own user. The supervisor can't read the final runs. Flex. Built today."

## Three-minute live demo

Set up before you start:

- Left terminal in the repo, ready to run `uv run python -m flex.watch`.
- Right terminal in the repo, ready to run `uv run python -m flex.evolve --gens 1`.
- The web page open in a browser tab, and Atlas Data Explorer on `flex.harness_versions`.
- A label over the terminals that says "live run, after the freeze". The frozen results stay in `results/`, and nothing in this run changes them.

**0:00 to 0:10. Start both terminals.**
Do: start `flex.watch` on the left, then `flex.evolve --gens 1` on the right.
Say: "On the right, the harness is rewriting its own scheduler right now. On the left, a MongoDB change stream prints everything it writes to Atlas. This run is after our freeze, so it can't change the frozen results."

**0:10 to 0:50. The story while it runs.**
Show: both terminals.
Say: "AI data centers schedule training power against electricity prices and grid events. In our simulation, restart costs rose 30x, from 35 to 1,050 kilowatt-hours per cold start. The frozen scheduler passed 10 of 12 validation scenarios. It ran late on val-25-high and val-26-high. Claude reads the diagnosis lines and proposes bounded rules. A fixed evaluator it can't edit decides. The first accepted repair passed 12 of 12, and every later champion kept 12 of 12. Only the CAISO prices are real. The jobs, the load, the events, and the restart cost are simulated."

**0:50 to 1:20. The verdict streams in.**
Show: the left terminal. The new version prints with its status and verdict reasons. An accepted version is followed by a `champion -> ...` line.
Say, if accepted: "Accepted. The evaluator says why in its own words, and the champion pointer moves in Atlas."
Say, if refused: "Refused, with the reason. That's the gate working. Seven of the first eleven proposals were refused too."
If the run is still going, move on to the page and come back to the terminal at the end.

**1:20 to 2:05. The recorded evidence.**
Show: the page. Open `g1-289b1a`, then `g4-4a14cc`, then the final table.
Say: "This is the record from before the freeze. g1-289b1a was accepted with 'repairs val-25-high, val-26-high; training energy -1.93%'. g4-4a14cc was refused with 'regression on val-26-high: late_job_hours 0 -> 1'. On 12 unseen days the champion at the freeze, g5-e942f4, cut training electricity cost 12.18%, $15,741.65 against $17,924.46, with zero missed deadlines. The old scheduler met every deadline there too, so that set tests cost. Most of the saving comes from one rule that holds jobs at 1% power to stay warm, which our simulator allows. Without it, the champion costs $17,157.39, 4.28% less than the old scheduler and behind both hand-tuned references."

**2:05 to 2:45. What the agent can't edit.**
Show: Data Explorer on `harness_versions`, then `champion`.
Say: "Deadlines, physical limits, protected settings and the evaluator are outside what the agent can edit. The simulator's safety controller, the policy validator, the Atlas schema and the database roles enforce that. Every version, verdict, run and hour lives in Atlas. Promotion is one transaction. The supervisor can't read the final runs, and the page's reader can't write."

**2:45 to 3:00. Close.**
Say: "The harness rewrote its own rules under a gate it can't touch. Built today, on Atlas."

## Likely questions

- Did the agent game the simulator? Partly. Claude found that 1% power keeps a job warm in our model. Our ablation caught it. The deadline repair doesn't use that rule.
- Isn't this a dashboard? No. The harness rewrites its own rules under a fixed gate, and the page only replays its records.
- Why is the repair small? Higher restart costs made the old deadline margins too thin, because warm-up takes about 1.5 hours the old margin didn't count. The supervisor found that from the diagnosis lines, and g1-289b1a's rationale says so. It added a 4-hour margin to the deadline rule, kept warm jobs running when restarts are expensive, and started work early before grid events. The 2 failing validation scenarios went to 0.
- The champion is late on dev-13-high. Yes. The champion at the freeze (g5-e942f4) is 2 job-hours late there, where its parent g4-eac5bd was on time. The gate checks validation only. The next step is adding dev to the no-regression check. The evaluator didn't change after anyone saw it.
- Why not let it edit guardrails? Governance. Deadlines, physical limits, protected settings and the evaluator are deliberately outside what the agent can edit. An agent that can loosen its own gate can pass anything.
- Is any of this real? The CAISO NP15 day-ahead prices are real. Everything else is a simulated assumption.
- Did the model ever see the final data? No. Final prices live outside the repo, the interpreter can't read files, and no prompt includes final data. They're public CAISO data and an older copy is in the public git history, so this is procedure and file location, not secrecy.
- Did the final set test the repair? No. The incumbent met every deadline there too. The repair evidence is validation, where g1-289b1a took 10 of 12 to 12 of 12.
- Does the champion beat the incumbent on cost? It doesn't have to. Deadlines come before cost. On the final set the champion at the freeze (g5-e942f4) had $15,741.65 of training electricity cost against $17,924.46, which is 12.18% less. Without its 1% keep-warm rule it's $17,157.39, 4.28% less, and behind both hand-tuned references.
- Does this help with Texas SB 6? SB 6 is motivation only. Its §39.170(b) reliability service excludes loads that curtail on wholesale prices, which this scheduler does, and the replay uses California prices.
