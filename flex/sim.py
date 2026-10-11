import argparse
import importlib
from datetime import datetime, timedelta, timezone

from flex.contract import (EVENT_PAYMENT, LATE_PENALTY, OVER_CAP_PENALTY_PER_KWH, TRAIN_CAP_KW, HarnessVersion,
                           HourRecord, Miss, MissKind, Obs, SimResult, Totals, World)
from flex.sandbox import compile_policy
from flex.world import PACIFIC, SEEDS, build_world, local_prices


def simulate(world: World, version: HarnessVersion, run_id: str) -> SimResult:
    decide = compile_policy(version["code"], version["tools"])
    fields = version["context_fields"]
    cap_frac = version["guardrails"]["max_train_frac"]
    zero_in_event = version["guardrails"]["zero_during_event"]
    price, inference, event, jobs = world["price"], world["inference_kw"], world["event"], world["jobs"]
    hours = len(price)
    t0 = datetime.fromisoformat(world["start"]).replace(tzinfo=PACIFIC).astimezone(timezone.utc)
    remaining = [j["work_kwh"] for j in jobs]
    arriving = sorted(range(len(jobs)), key=lambda i: jobs[i]["arrive_h"])
    next_arrival = 0
    active: list[int] = []
    records: list[HourRecord] = []
    misses: list[Miss] = []
    recent: list[str] = []
    energy = over_kwh = net = 0.0
    late_h = missed_events = 0
    event_ok = True

    def miss(kind: MissKind, t: int, ts: datetime, obs: Obs):
        misses.append({"run": run_id, "version": version["_id"], "split": world["split"], "h": t, "ts": ts,
                       "kind": kind, "context": obs})
        recent.append(f"{kind}@h{t}")

    for t in range(hours):
        while next_arrival < len(arriving) and jobs[arriving[next_arrival]]["arrive_h"] <= t:
            active.append(arriving[next_arrival])
            next_arrival += 1
        active.sort(key=lambda i: jobs[i]["deadline_h"])
        ts = t0 + timedelta(hours=t)
        slack = min((jobs[i]["deadline_h"] - t for i in active), default=99)
        need_h = sum(remaining[i] for i in active) / TRAIN_CAP_KW
        event_in = next((k for k in range(1, 13) if t + k < hours and event[t + k]), None)
        full: Obs = {
            "hour_of_day": t % 24, "price": price[t], "prices_ahead": price[t:(t // 24 + 2) * 24],
            "event_now": event[t], "event_in_h": event_in, "slack_h": slack, "need_h": need_h,
            "inference_kw": inference[t], "recent_misses": recent[-3:],
        }
        frac = min(max(decide({k: full[k] for k in fields}), 0.0), cap_frac)
        if zero_in_event and event[t]:
            frac = 0.0
        train_kw = frac * TRAIN_CAP_KW
        hour_energy = (train_kw + inference[t]) * price[t] / 1000
        cost = hour_energy
        if event[t]:
            over = max(0.0, train_kw + inference[t] - world["event_cap_kw"])
            if over > 0:
                cost += over * OVER_CAP_PENALTY_PER_KWH
                over_kwh += over
                event_ok = False
                miss("over_cap", t, ts, full)
            if t + 1 == hours or not event[t + 1]:
                if event_ok:
                    cost -= EVENT_PAYMENT
                else:
                    missed_events += 1
                    miss("missed_event", t, ts, full)
                event_ok = True
        work = train_kw
        for i in active:
            take = min(work, remaining[i])
            remaining[i] -= take
            work -= take
            if work <= 0:
                break
        for i in active:
            if remaining[i] > 0 and t >= jobs[i]["deadline_h"]:
                late_h += 1
                cost += LATE_PENALTY
                miss("late", t, ts, full)
        active = [i for i in active if remaining[i] > 0]
        energy += hour_energy
        net += cost
        records.append({"h": t, "ts": ts, "price": price[t], "train_kw": train_kw, "inference_kw": inference[t],
                        "event": event[t], "cost": cost})
    totals: Totals = {"energy_cost": energy, "late_h": late_h, "missed_events": missed_events,
                      "over_cap_kwh": over_kwh, "net": net}
    return {"totals": totals, "hours": records, "misses": misses}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v0")
    ap.add_argument("--split", default="test", choices=list(SEEDS))
    args = ap.parse_args()
    version = getattr(importlib.import_module(f"policies.{args.version}"), args.version.upper())
    world = build_world(args.split, local_prices(args.split), SEEDS[args.split])
    print(simulate(world, version, "cli")["totals"])
