# Cerebral Valley submission

**Project name.** Flex

**Problem statement.** Recursive Harnessing

**Repository.** https://github.com/ricardodreyes/flex-harness

**Description.**

Flex adapts an AI data center's training-power scheduler when operating conditions change. The first change we test is a jump in the simulated restart cost, from 35 kWh to 1,050 kWh of warm-up per cold start. The scheduler tuned for cheap restarts starts missing deadlines.

A supervisor model (Claude Opus 5.5) reads development diagnostics only and proposes a new policy, which is at most 8 bounded JSON rules over named observation fields. No model output is executed as code. A fixed evaluator that the supervisor can't edit accepts a candidate only if it repairs a failing validation scenario without breaking a passing one, or keeps the same pass set and cuts training energy cost by more than 1%. Deadlines come before cost.

MongoDB Atlas holds the record. Each simulated hour goes into a time-series collection. A `$jsonSchema` validator guards harness versions, and a multi-document transaction promotes the champion. Separate database users per role keep the supervisor out of the final-results database and keep the web reader read-only.

Results, from one frozen run on Sep 29 to Oct 10, 2026 CAISO prices that nobody had inspected before they were reserved: incumbent [RESULT], supervisor champion [RESULT], hand-written control repair [RESULT].

The CAISO NP15 day-ahead prices are real. The jobs, inference load, grid events, and restart cost are simulated assumptions. Final prices are kept outside the repo, which is procedural plus file-location isolation, not a security boundary. Texas SB 6 is motivation only; the replay doesn't show Texas compliance.

Built at the hackathon on Oct 11, 2026.
