# Cerebral Valley submission

**Project name.** Flex

**Problem statement.** Recursive Harnessing

**Repository.** https://github.com/ricardodreyes/flex-harness

**Description.**

Restart costs rose 30x (35 to 1,050 kWh per cold start). The frozen scheduler passed 10 of 12 validation scenarios. Claude's first accepted repair passed 12 of 12, and every later champion kept 12 of 12. On 12 unseen days the champion at the freeze (g5-e942f4) cut training electricity cost 12.18% with zero missed deadlines. An ablation after the freeze shows most of that comes from one rule that holds paused jobs at 1% power to stay warm, which our simulator allows and real GPUs likely don't. Without that rule the saving is 4.28%, behind both hand-tuned references.

Flex adapts an AI data center's training-power scheduler when operating conditions change. A supervisor model (Claude Opus 5.5) reads development diagnostics only and proposes a new policy, which is at most 8 bounded JSON rules over named observation fields. No model output is executed as code. A fixed evaluator scores each candidate on 12 validation scenarios. It rejects any candidate that makes a scenario worse on late job-hours, unfinished work, cap interventions, or completed jobs. It accepts a candidate that repairs a failing scenario. When no scenario got worse and none was repaired, it accepts only a cut in training electricity cost of more than 1%. Deadlines come before cost.

Deadlines, physical limits, protected settings, and the evaluator are deliberately outside what the agent can edit. The simulator's safety controller, the policy validator, the Atlas schema, and the database roles enforce that. MongoDB's Atlas Agent Engine launch describes agents "governed by policy that can't be quietly switched off". Flex doesn't use Agent Engine. It builds the same idea from those four pieces.

MongoDB Atlas holds the record. Each simulated hour goes into a time-series collection. A `$jsonSchema` validator checks every harness version's envelope while the policy validator checks the rules, and a multi-document transaction promotes the champion. A change stream shows new versions and champion moves live while the harness runs. Separate database users per role keep the supervisor out of the final-results database and keep the web reader read-only.

The final comparison ran once, on 3 scenarios priced with Sep 29 to Oct 10, 2026 CAISO prices that nobody had inspected before they were reserved. Every pinned version met every deadline there, including the frozen incumbent, so the final set doesn't test the repair. The repair evidence is validation, where version g1-289b1a was accepted with "repairs val-25-high, val-26-high; training energy -1.93%". Verdict reasons say "training energy"; the number is training electricity cost in dollars. Summed final training electricity cost was $17,924.46 for the incumbent and $15,741.65 for the champion at the freeze (g5-e942f4), which is -12.18%. The hand-tuned references cost $16,695.84 and $16,781.72. An ablation after the freeze removed the champion's rule that holds jobs at 1% power to stay warm. Without it the champion costs $17,157.39, -4.28%, behind both references, with 36 restarts instead of 6. Our simulator treats any power as keeping a job warm. The fix is a protected minimum warm power, which needs a new evolve run and a new final set. Two evolve runs left 12 versions in Atlas, and 7 were rejected with reasons. Raindrop recorded 17 proposal events: 6 from a dry run that wrote nothing to Atlas, and 11 from the two Atlas runs, matching the 11 supervisor versions (counted from the dashboard timestamps at 2:40 p.m.).

The CAISO NP15 day-ahead prices are real. The jobs, inference load, grid events, and restart cost are simulated assumptions. Final prices are kept outside the repo. They're public CAISO data and an older copy is in the public git history, so they're held out by procedure and file location, not secrecy. Texas SB 6 is motivation only; the replay doesn't show Texas compliance.

Built at the hackathon on Oct 11, 2026.
