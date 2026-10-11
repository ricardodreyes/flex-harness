import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from flex.contract import TRAIN_CAP_KW, Job, Scenario, World

PACIFIC = ZoneInfo("America/Los_Angeles")
DATA = Path(__file__).parent.parent / "data"
PRICES = DATA / "caiso_np15_dam_2026.json"
FINAL_PRICES = DATA / "final" / "caiso_np15_dam_2026_final.json"
MAX_DEADLINE_OFFSET_H = 72


def _slice(path: Path, start: str, hours: int) -> list[float]:
    by_hour = {datetime.fromisoformat(k): v for k, v in json.loads(path.read_text())}
    t0 = datetime.fromisoformat(start).replace(tzinfo=PACIFIC).astimezone(timezone.utc)
    return [by_hour[t0 + timedelta(hours=i)] for i in range(hours)]


def prices(start: str, hours: int) -> list[float]:
    """CAISO NP15 day-ahead prices from a Pacific calendar day, Apr 1 to Sep 28 2026."""
    return _slice(PRICES, start, hours)


def final_prices(start: str, hours: int) -> list[float]:
    """Sep 29 to Oct 10 2026, reserved for the final evaluator. Nothing else may call this."""
    return _slice(FINAL_PRICES, start, hours)


def build_world(scenario: Scenario, prices: list[float]) -> World:
    cutoff = scenario["arrival_days"] * 24
    assert scenario["tail_h"] >= MAX_DEADLINE_OFFSET_H, "tail must cover the last deadline"
    hours = cutoff + scenario["tail_h"]
    assert len(prices) >= hours, f"need {hours} prices, got {len(prices)}"
    rng = np.random.default_rng(scenario["seed"])
    h = np.arange(hours) % 24
    inference = 120 + 100 * np.sin((h - 9) / 24 * 2 * np.pi) ** 2 + rng.normal(0, 10, hours)
    jobs: list[Job] = []
    for d in range(scenario["arrival_days"]):
        for _ in range(rng.integers(1, 3)):
            arrive = d * 24 + int(rng.integers(0, 24))
            work_kwh = float(rng.uniform(6, 14)) * TRAIN_CAP_KW * scenario["settings"]["work_scale"]
            jobs.append({"id": f"{scenario['id']}-j{len(jobs)}", "arrive_h": arrive,
                         "deadline_h": arrive + int(rng.integers(30, MAX_DEADLINE_OFFSET_H + 1)),
                         "work_kwh": work_kwh})
    price = np.array(prices[:hours])
    event = np.zeros(hours, dtype=bool)
    days = scenario["arrival_days"]
    daily_max = price[:cutoff].reshape(days, 24).max(axis=1)
    for d in np.argsort(daily_max)[-max(1, days // 10):]:
        event[d * 24 + 16:d * 24 + 20] = True
    return {"scenario": scenario, "price": price.tolist(), "inference_kw": inference.tolist(),
            "event": event.tolist(), "jobs": jobs, "arrival_cutoff_h": cutoff}
