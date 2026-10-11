"""The frozen scenario manifest. Settings here are protected: a candidate cannot touch them."""

import hashlib
import json

from flex.contract import Scenario, ScenarioSettings, Split
from flex.world import FINAL_PRICES, PRICES

EVALUATOR_VERSION = "2026-10-11.2"

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
    _sc("val-21", "validation", "2026-07-01", 21, HIGH, "promotion validation"),
    _sc("val-22", "validation", "2026-08-01", 22, HIGH, "promotion validation"),
    _sc("val-23", "validation", "2026-08-30", 23, HIGH,
        "promotion validation; the Aug 30 to Sep 28 price window was inspected before the build, not held out"),
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


def manifest_sha256() -> str:
    h = hashlib.sha256(json.dumps(SCENARIOS, sort_keys=True, separators=(",", ":")).encode())
    for path in (PRICES, FINAL_PRICES):
        h.update(hashlib.sha256(path.read_bytes()).hexdigest().encode())
    h.update(EVALUATOR_VERSION.encode())
    return h.hexdigest()
