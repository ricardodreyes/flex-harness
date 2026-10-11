"""The frozen scenario manifest. Settings here are protected: a candidate cannot touch them."""

from flex.contract import Scenario, ScenarioSettings, Split

EVALUATOR_VERSION = "2026-10-11.3"

LOW: ScenarioSettings = {"restart_kwh": 35.0, "event_cap_kw": 280.0, "work_scale": 1.0}  # 3 min at the ceiling
HIGH: ScenarioSettings = {"restart_kwh": 1050.0, "event_cap_kw": 280.0, "work_scale": 1.0}  # 1.5 h at the ceiling


def _sc(id: str, split: Split, start: str, seed: int, settings: ScenarioSettings, note: str,
        arrival_days: int = 26, tail_h: int = 72) -> Scenario:
    return {"id": id, "split": split, "start": start, "arrival_days": arrival_days, "tail_h": tail_h, "seed": seed,
            "settings": settings, "note": note}


SCENARIOS: list[Scenario] = [
    *[sc for seed, start in ((11, "2026-04-01"), (12, "2026-05-01"), (13, "2026-06-01")) for sc in (
        _sc(f"dev-{seed}-low", "dev", start, seed, LOW, "cheap restarts, the world the incumbent was tuned in"),
        _sc(f"dev-{seed}-high", "dev", start, seed, HIGH, "expensive restarts, same workload and prices"),
    )],
    _sc("dev-imp-11", "dev", "2026-04-01", 11, {**HIGH, "work_scale": 2.5},
        "dev-11-high with 2.5x work; capacity-impossible: one job cannot fit its window at the ceiling and the aggregate "
        "work overloads the cluster, 199,495 kWh unfinished even at full power"),
    _sc("dev-cap-11", "dev", "2026-04-01", 11, {**LOW, "event_cap_kw": 100.0},
        "dev-11-low with a 100 kW event cap; inference alone exceeds it, infeasible for the training controller"),
    # Pre-declared at 1:45 p.m. before any run on them; seeds and starts were not chosen from results. The last
    # start is Aug 31, not Sep 1, so the 29-day window ends inside the Sep 28 price data.
    *[sc for seed, start, inspected in ((21, "2026-07-01", False), (22, "2026-07-16", False), (23, "2026-08-01", False),
                                        (24, "2026-08-16", True), (25, "2026-08-30", True), (26, "2026-08-31", True))
      for sc in (
        _sc(f"val-{seed}-low", "validation", start, seed, LOW, "promotion validation, cheap restarts"
            + ("; overlaps the Aug 30 to Sep 28 price window inspected before the build" if inspected else "")),
        _sc(f"val-{seed}-high", "validation", start, seed, HIGH, "promotion validation, expensive restarts"
            + ("; overlaps the Aug 30 to Sep 28 price window inspected before the build" if inspected else "")),
    )],
    *[_sc(f"final-{seed}", "final", "2026-09-29", seed, HIGH, "held-out workload seed on reserved Sep 29 to Oct 10 prices",
          arrival_days=9) for seed in (31, 32, 33)],
]


def by_split(split: Split) -> list[Scenario]:
    return [s for s in SCENARIOS if s["split"] == split]


def dev() -> list[Scenario]:
    return by_split("dev")


def validation() -> list[Scenario]:
    return by_split("validation")


def final() -> list[Scenario]:
    return by_split("final")


def by_id(id: str) -> Scenario:
    return next(s for s in SCENARIOS if s["id"] == id)

