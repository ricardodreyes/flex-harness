# Demo scripts

Both scripts show only work built on Oct 11, 2026. Every number comes from `results/final.json` or from the runs and versions in Atlas, the same numbers as the README. The spoken lines round dollar amounts; put the exact figures on screen.

## One-minute video

About 150 spoken words in five beats, timed at 150 words a minute.

**0:00 to 0:08. The problem.**
Show: the incumbent's validation runs, with the restart cost raised from 35 kWh to 1,050 kWh.
Say: "Restarts got expensive in our simulated AI data center. The frozen scheduler starts missing deadlines on two validation scenarios."

**0:08 to 0:20. The repair.**
Show: version `g1-289b1a` and its verdict, "repairs val-25-high, val-26-high; training energy -1.93%".
Say: "Claude reads the misses and rewrites the scheduler's rules. A fixed evaluator it can't edit checks the change. This one repairs both scenarios, with almost two percent less training energy."

**0:20 to 0:30. A refusal.**
Show: version `g4-4a14cc` and its verdict, "regression on val-26-high: late_job_hours 0 -> 1".
Say: "Not every edit gets in. This one looked reasonable. But it made one job an hour late. The evaluator called it a regression and refused it."

**0:30 to 0:50. The held-out result.**
Show: the final table. Champion `g5-e942f4` at $15,741.65, incumbent `v0` at $17,924.46, -12.18%.
Say: "Then twelve days of prices nobody had seen. The champion met every deadline. So did the old scheduler, so this tests cost. The champion cost about fifteen thousand seven hundred dollars. The old one cost seventeen thousand nine hundred. That's twelve percent less. It beat both hand-tuned references too."

**0:50 to 1:00. MongoDB.**
Show: Atlas Data Explorer on `harness_versions`.
Say: "Every version, verdict and run lives in MongoDB Atlas. Each part signs in as its own user. The supervisor can't read the final runs. Flex. Built today."

## Three-minute live demo

Have these open before you start: the web page, Atlas Data Explorer on `flex.harness_versions`, and a terminal in the repo.

**0:00 to 0:25. The problem.**
Show: the page header.
Say: "AI data centers schedule training power against electricity prices and grid events. When conditions change, a scheduler tuned for the old conditions starts missing deadlines. Flex lets a model repair the scheduler's policy, and a fixed evaluator decides whether the repair is kept. Only the CAISO prices are real. The jobs, the load, the events, and the restart cost are simulated."

**0:25 to 0:55. The incumbent breaks.**
Show: the incumbent's dev and validation runs, low against high restart cost.
Say: "This scheduler was tuned when a restart cost 35 kWh of warm-up. We raise it to 1,050 kWh. The same policy now has 2 late job-hours on dev-12-high and 5 on dev-13-high. On validation it has 1 on val-25-high and 4 on val-26-high. The diagnosis lines say why."

**0:55 to 1:35. The supervisor proposes, the evaluator decides.**
Show: the version lineage. Open `g4-4a14cc`, then `g1-289b1a`.
Say: "The supervisor gets dev evidence only: totals, diagnosis lines, recent misses, and the reasons earlier proposals failed. It returns a bounded JSON policy with a rationale and a prediction. This one, g4-4a14cc, was rejected with 'regression on val-26-high: late_job_hours 0 -> 1'. This one, g1-289b1a, was accepted with 'repairs val-25-high, val-26-high; training energy -1.93%'. Two evolve runs left 12 versions, and 7 were rejected with reasons. The supervisor can't edit the evaluator, the scenarios, or the restart cost."

**1:35 to 2:10. Atlas holds the record.**
Show: Data Explorer on `harness_versions`, then `champion`, then `hours` for one run.
Say: "Every version, verdict, run, hour, and miss lives in Atlas. A JSON schema validator checks every version's envelope, and the policy validator checks the rules, so even a malformed rejected proposal stays on record. Promotion is one transaction that moves the champion pointer and retires the old champion. Our check injects a failure inside that transaction and the old champion stays. Each role connects as its own database user. The supervisor can't read the final database, and the page's reader can't write."

**2:10 to 2:45. The frozen final comparison.**
Show: the final table.
Say: "The final prices are Sep 29 to Oct 10, and nobody looked at them before we reserved them. They live outside the repo. They're public CAISO data and an older copy is in our git history, so that's procedure and file location, not secrecy. One run, never fed back. Every pinned version met every deadline here, including the incumbent, so this set doesn't test the repair. It tests cost. Incumbent: $17,924.46. Champion g5-e942f4: $15,741.65, which is 12.18% less. Restart-aware reference: $16,695.84. Hand-written control repair: $16,781.72."

**2:45 to 3:00. Close.**
Say: "The harness adapted its own policy to a changed condition, and a judge it can't touch kept the change. Built today, on Atlas."

## Likely questions

- Is any of this real? The CAISO NP15 day-ahead prices are real. Everything else is a simulated assumption.
- Did the model ever see the final data? No. Final prices live outside the repo, the interpreter can't read files, and no prompt includes final data. They're public CAISO data and an older copy is in the public git history, so this is procedure and file location, not secrecy.
- Did the final set test the repair? No. The incumbent met every deadline there too. The repair evidence is validation, where g1-289b1a repaired val-25-high and val-26-high.
- Is the champion better everywhere? No. The gate scores only the 12 validation scenarios. The champion g5-e942f4 is 2 job-hours late on dev-13-high, where its parent g4-eac5bd was on time. The evaluator didn't change after anyone saw that.
- Does this help with Texas SB 6? SB 6 is motivation only. Its §39.170(b) reliability service excludes loads that curtail on wholesale prices, which this scheduler does, and the replay uses California prices.
- Does the champion beat the incumbent on cost? It doesn't have to. Deadlines come before cost. On the final set it cost $15,741.65 against $17,924.46, which is 12.18% less.
