# Cerebral Valley submission

**Project name.** Flex

**Problem statement.** Recursive Harnessing

**Repository.** https://github.com/ricardodreyes/flex-harness

**Description.**

Flex adapts an AI data center's training-power scheduler when operating conditions change. The first change we test is a jump in the simulated restart cost, from 35 kWh to 1,050 kWh of warm-up per cold start. The scheduler tuned for cheap restarts starts missing deadlines.

A supervisor model (Claude Opus 5.5) reads development diagnostics only and proposes a new policy, which is at most 8 bounded JSON rules over named observation fields. No model output is executed as code. A fixed evaluator that the supervisor can't edit scores each candidate on 12 validation scenarios. It rejects any candidate that makes a scenario worse on late job-hours, unfinished work, cap interventions, or completed jobs. It accepts a candidate that repairs a failing scenario. When no scenario got worse and none was repaired, it accepts only a cut in training energy cost of more than 1%. Deadlines come before cost.

MongoDB Atlas holds the record. Each simulated hour goes into a time-series collection. A `$jsonSchema` validator checks every harness version's envelope while the policy validator checks the rules, and a multi-document transaction promotes the champion. Separate database users per role keep the supervisor out of the final-results database and keep the web reader read-only.

The final comparison ran once, on 3 scenarios priced with Sep 29 to Oct 10, 2026 CAISO prices that nobody had inspected before they were reserved. Every pinned version met every deadline there, including the frozen incumbent, so the final set doesn't test the repair. The repair evidence is validation, where version g1-289b1a was accepted with "repairs val-25-high, val-26-high; training energy -1.93%". Summed final training energy was $17,924.46 for the incumbent and $15,741.65 for the champion g5-e942f4, which is -12.18%. The champion beat both hand-tuned references, at $16,695.84 and $16,781.72. Two evolve runs left 12 versions in Atlas, and 7 were rejected with reasons. Raindrop recorded 17 proposal events: 6 from a dry run that wrote nothing to Atlas, and 11 from the two Atlas runs, matching the 11 supervisor versions (counted from the dashboard timestamps at 2:40 p.m.).

The CAISO NP15 day-ahead prices are real. The jobs, inference load, grid events, and restart cost are simulated assumptions. Final prices are kept outside the repo. They're public CAISO data and an older copy is in the public git history, so they're held out by procedure and file location, not secrecy. Texas SB 6 is motivation only; the replay doesn't show Texas compliance.

Built at the hackathon on Oct 11, 2026.
