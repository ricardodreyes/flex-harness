import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from flex.contract import SPLITS, TRAIN_CAP_KW, Job, Split, World

SEEDS: dict[Split, int] = {"train": 1, "gate": 3, "test": 7}
EVENT_CAP_KW = 280.0
PACIFIC = ZoneInfo("America/Los_Angeles")
DATA = Path(__file__).parent.parent / "data" / "caiso_np15_dam_2026.json"


def local_prices(split: Split) -> list[float]:
    by_hour = {datetime.fromisoformat(k): v for k, v in json.loads(DATA.read_text())}
    first, last = (datetime.fromisoformat(d).replace(tzinfo=PACIFIC) for d in SPLITS[split])
    t0 = first.astimezone(timezone.utc)
    hours = round((last + timedelta(days=1) - first).total_seconds() / 3600)
    return [by_hour[t0 + timedelta(hours=i)] for i in range(hours)]


def build_world(split: Split, prices: list[float], seed: int) -> World:
    days = len(prices) // 24
    hours = days * 24
    # draw order replays the original probe's make_world so seeded loads reproduce its numbers
    rng = np.random.default_rng(seed)
    h = np.arange(hours) % 24
    rng.normal(0, 5, hours)
    spike = (rng.random(hours) < 0.04) & (h >= 15) & (h <= 22)
    rng.uniform(200, 900, spike.sum())
    inference = 120 + 100 * np.sin((h - 9) / 24 * 2 * np.pi) ** 2 + rng.normal(0, 10, hours)
    rng.choice(days, size=max(1, days // 11), replace=False)
    jobs: list[Job] = []
    for d in range(days):
        for _ in range(rng.integers(1, 3)):
            arrive = d * 24 + int(rng.integers(0, 24))
            work_kwh = float(rng.uniform(6, 14)) * TRAIN_CAP_KW
            jobs.append({"id": f"j{len(jobs)}", "arrive_h": arrive,
                         "deadline_h": arrive + int(rng.integers(30, 72)), "work_kwh": work_kwh})
    price = np.array(prices[:hours])
    event = np.zeros(hours, dtype=bool)
    for d in np.argsort(price.reshape(days, 24).max(axis=1))[-max(1, days // 10):]:
        event[d * 24 + 16:d * 24 + 20] = True
    return {"split": split, "start": SPLITS[split][0], "price": price.tolist(),
            "inference_kw": inference.tolist(), "event": event.tolist(),
            "event_cap_kw": EVENT_CAP_KW, "jobs": jobs}
