# Demo scripts

Both scripts show only work built on Oct 11, 2026. Every number in brackets comes from a recorded run. Fill dev and validation numbers from Atlas after `flex.evolve`, and final numbers from `results/final.json` after `flex.final`. Don't say a number that isn't filled in. If no supervisor proposal was accepted, say so plainly and cut the accepted beats.

## Three-minute live demo

Have these open before you start: the web page, Atlas Data Explorer on `flex.harness_versions`, and a terminal in the repo.

**0:00 to 0:25. The problem.**
Show: the page header.
Say: "AI data centers schedule training power against electricity prices and grid events. When conditions change, a scheduler tuned for the old conditions starts missing deadlines. Flex lets a model repair the scheduler's policy, and a fixed evaluator decides whether the repair is kept. Only the CAISO prices are real. The jobs, the load, the events, and the restart cost are simulated."

**0:25 to 0:55. The incumbent breaks.**
Show: the incumbent's dev runs, low against high restart cost.
Say: "This scheduler was tuned when a restart cost 35 kWh of warm-up. We raise it to 1,050 kWh. The same policy now has [RESULT] late job-hours on dev-12-high and [RESULT] on dev-13-high. The diagnosis lines say why."

**0:55 to 1:35. The supervisor proposes, the evaluator decides.**
Show: the version lineage. Open one rejected and one accepted supervisor version.
Say: "The supervisor gets dev evidence only: totals, diagnosis lines, recent misses, and the reasons earlier proposals failed. It returns a bounded JSON policy with a rationale and a prediction. This one was rejected: [REASON]. This one was accepted as a repair: [REASON], at [RESULT] training energy. The supervisor can't edit the evaluator, the scenarios, or the restart cost."

**1:35 to 2:10. Atlas holds the record.**
Show: Data Explorer on `harness_versions`, then `champion`, then `hours` for one run.
Say: "Every version, verdict, run, hour, and miss lives in Atlas. A JSON schema validator checks every version's envelope, and the policy validator checks the rules, so even a malformed rejected proposal stays on record. Promotion is one transaction that moves the champion pointer and retires the old champion. Our check injects a failure inside that transaction and the old champion stays. Each role connects as its own database user. The supervisor can't read the final database, and the page's reader can't write."

**2:10 to 2:45. The frozen final comparison.**
Show: the final table.
Say: "The final prices are Sep 29 to Oct 10, and nobody looked at them before we reserved them. They live outside the repo. They're public CAISO data and an older copy is in our git history, so that's procedure and file location, not secrecy. One run, never fed back. Incumbent: [RESULT]. Supervisor champion: [RESULT]. Hand-written control repair: [RESULT]."

**2:45 to 3:00. Close.**
Say: "The harness adapted its own policy to a changed condition, and a judge it can't touch kept the change. Built today, on Atlas."

## Likely questions

- Is any of this real? The CAISO NP15 day-ahead prices are real. Everything else is a simulated assumption.
- Did the model ever see the final data? No. Final prices live outside the repo, the interpreter can't read files, and no prompt includes final data. They're public CAISO data and an older copy is in the public git history, so this is procedure and file location, not secrecy.
- Does this help with Texas SB 6? SB 6 is motivation only. Its §39.170(b) reliability service excludes loads that curtail on wholesale prices, which this scheduler does, and the replay uses California prices.
- Does the champion beat the incumbent on cost? It doesn't have to. Deadlines come before cost. Cost change: [RESULT].

## One-minute video

**0:00 to 0:10.** Page header. "Flex lets a model repair an AI data center's training scheduler when conditions change, and a fixed evaluator decides what's kept."

**0:10 to 0:22.** Incumbent dev runs. "Restart cost goes from 35 to 1,050 kWh. The tuned scheduler now misses [RESULT] job-hours of deadlines."

**0:22 to 0:38.** Lineage with one rejected and one accepted version. "The supervisor proposes bounded rule changes from dev evidence. Rejected: [REASON]. Accepted: [REASON]."

**0:38 to 0:50.** Atlas Data Explorer. "Atlas holds every version and run, validates the schema, and promotes in one transaction, with a separate user per role."

**0:50 to 1:00.** Final table. "On reserved prices nobody had seen: [RESULT]. Real CAISO prices, simulated site. Built Oct 11, 2026."
