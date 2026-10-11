"""The physics from the contract docstring. One step is one hour, so kW drawn equals kWh; work is productive kWh."""

import argparse
from datetime import datetime, timedelta, timezone

from flex.contract import (TRAIN_CAP_KW, HourRecord, JobOutcome, Miss, MissKind, Obs, Policy, SimResult, Totals,
                           World)
from flex.policy import compile_policy
from flex.world import PACIFIC, build_world, prices

EPS = 1e-9


def impossible_jobs(world: World) -> list[tuple[str, float, int]]:
    """(id, hours needed at the ceiling, hours in the window) for jobs no policy can finish: the work plus the
    one warm-up every start pays exceeds the ceiling over the window."""
    restart = world["scenario"]["settings"]["restart_kwh"]
    out = []
    for j in world["jobs"]:
        need = (j["work_kwh"] + restart) / TRAIN_CAP_KW
        window = j["deadline_h"] - j["arrive_h"]
        if need > window:
            out.append((j["id"], need, window))
    return out


def _warm_ups(kwh: float) -> str:
    return f"warm-ups used {kwh:,.0f} kWh ({kwh / TRAIN_CAP_KW:.1f} h at the ceiling)"


def diagnose(world: World, jobs: list[JobOutcome], remaining: list[float], totals: Totals) -> list[str]:
    lines = []
    for j, rem in zip(jobs, remaining):
        if j["done_h"] is None:
            lines.append(f"job {j['id']} unfinished with {rem:,.0f} kWh remaining, {j['late_h']} h past its deadline "
                         f"after {j['starts']} starts; {_warm_ups(j['overhead_kwh'])}")
        elif j["late_h"]:
            lines.append(f"job {j['id']} finished {j['late_h']} h late after {j['starts']} starts; "
                         f"{_warm_ups(j['overhead_kwh'])}")
    for jid, need, window in impossible_jobs(world):
        lines.append(f"job {jid} needs {need:.1f} h at the ceiling but had {window} h before its deadline: "
                     "impossible for any policy")
    cap = world["scenario"]["settings"]["event_cap_kw"]
    if totals["infeasible_hours"]:
        lines.append(f"inference exceeded the {cap:g} kW event cap in {totals['infeasible_hours']} hours: "
                     "infeasible for the training controller")
    if totals["cap_interventions"]:
        lines.append(f"{totals['cap_interventions']} cap interventions: the safety controller cut requested power")
    lines.append(f"{totals['starts']} starts, {totals['restarts']} restarts; {_warm_ups(totals['overhead_kwh'])}")
    return lines


def simulate(world: World, policy: Policy, run_id: str, version_id: str) -> SimResult:
    decide = compile_policy(policy)
    fields = policy["context_fields"]
    sc = world["scenario"]
    restart_kwh, event_cap = sc["settings"]["restart_kwh"], sc["settings"]["event_cap_kw"]
    price, inference, event, jobs = world["price"], world["inference_kw"], world["event"], world["jobs"]
    hours, n = len(price), len(jobs)
    t0 = datetime.fromisoformat(sc["start"]).replace(tzinfo=PACIFIC).astimezone(timezone.utc)
    remaining = [j["work_kwh"] for j in jobs]
    debt = [0.0] * n  # outstanding warm-up kWh, meaningful only while warm
    warm = [False] * n  # received power last hour
    starts, late = [0] * n, [0] * n
    overhead = [0.0] * n
    done: list[int | None] = [None] * n
    by_arrival = sorted(range(n), key=lambda i: jobs[i]["arrive_h"])
    next_arrival = 0
    active: list[int] = []
    records: list[HourRecord] = []
    misses: list[Miss] = []
    interventions = infeasible = 0
    training_cost = total_cost = 0.0

    def miss(kind: MissKind, t: int, ts: datetime, obs: Obs, detail: str, job: str | None = None):
        m: Miss = {"run": run_id, "version": version_id, "scenario": sc["id"], "h": t, "ts": ts, "kind": kind,
                   "detail": detail, "context": obs}
        if job is not None:
            m["job"] = job
        misses.append(m)

    for t in range(hours):
        while next_arrival < n and jobs[by_arrival[next_arrival]]["arrive_h"] <= t:
            active.append(by_arrival[next_arrival])
            next_arrival += 1
        active.sort(key=lambda i: jobs[i]["deadline_h"])
        ts = t0 + timedelta(hours=t)
        hod = t % 24
        known = price[t:min(hours, (t // 24 + (2 if hod >= 13 else 1)) * 24)]
        full: Obs = {
            "hour_of_day": hod,
            "price": price[t],
            "price_pct": sum(p < price[t] for p in known) / len(known),
            "event_now": event[t],
            "event_in_h": next((k for k in range(1, 25) if t + k < hours and event[t + k]), None),
            "slack_h": min((jobs[i]["deadline_h"] - t for i in active), default=99),
            "need_h": sum(remaining[i] for i in active) / TRAIN_CAP_KW,
            "queued_jobs": len(active),
            "running": bool(active) and warm[active[0]],
            "restart_kwh": restart_kwh,
        }
        requested = min(max(decide({k: full[k] for k in fields}), 0.0), 1.0) * TRAIN_CAP_KW
        limit = max(0.0, event_cap - inference[t]) if event[t] else TRAIN_CAP_KW
        if event[t] and inference[t] > event_cap:
            infeasible += 1
            miss("infeasible_hour", t, ts, full, f"inference {inference[t]:.0f} kW exceeds the {event_cap:g} kW cap")
        if requested > limit + EPS:
            interventions += 1
            miss("cap_intervention", t, ts, full, f"requested {requested:.0f} kW, safety limit {limit:.0f} kW")
        absorbable = sum((debt[i] if warm[i] else restart_kwh) + remaining[i] for i in active)
        executed = min(requested, limit, absorbable)
        power = executed
        productive = overhead_now = 0.0
        powered: set[int] = set()
        for i in active:
            if power <= EPS:
                break
            if not warm[i]:
                warm[i] = True
                debt[i] = restart_kwh
                starts[i] += 1
            pay = min(power, debt[i])
            debt[i] -= pay
            overhead[i] += pay
            overhead_now += pay
            power -= pay
            prog = min(power, remaining[i])
            remaining[i] -= prog
            productive += prog
            power -= prog
            powered.add(i)
            if remaining[i] <= EPS:
                remaining[i] = 0.0
                done[i] = t
        for i in active:
            if i not in powered:
                warm[i] = False
            if remaining[i] > 0 and t >= jobs[i]["deadline_h"] - 1:
                late[i] += 1
                miss("late", t, ts, full, f"{remaining[i]:,.0f} kWh remaining past deadline h{jobs[i]['deadline_h']}",
                     jobs[i]["id"])
        active = [i for i in active if remaining[i] > 0]
        hour_cost = (executed + inference[t]) * price[t] / 1000
        training_cost += executed * price[t] / 1000
        total_cost += hour_cost
        records.append({"h": t, "ts": ts, "price": price[t], "requested_kw": requested, "executed_kw": executed,
                        "productive_kw": productive, "overhead_kw": overhead_now, "inference_kw": inference[t],
                        "event": event[t], "safety_limit_kw": limit, "energy_cost": hour_cost})

    end_ts = t0 + timedelta(hours=hours)
    for i in range(n):
        if remaining[i] > 0:
            miss("unfinished", hours, end_ts, {}, f"{remaining[i]:,.0f} kWh of {jobs[i]['work_kwh']:,.0f} unfinished",
                 jobs[i]["id"])
    outcomes: list[JobOutcome] = [
        {"id": j["id"], "arrive_h": j["arrive_h"], "deadline_h": j["deadline_h"], "work_kwh": j["work_kwh"],
         "done_h": done[i], "late_h": late[i], "starts": starts[i], "overhead_kwh": overhead[i]}
        for i, j in enumerate(jobs)]
    totals: Totals = {
        "jobs_total": n,
        "jobs_completed": sum(d is not None for d in done),
        "jobs_late": sum(l > 0 for l in late),
        "late_job_hours": sum(late),
        "work_kwh": sum(j["work_kwh"] for j in jobs),
        "productive_kwh": sum(r["productive_kw"] for r in records),
        "overhead_kwh": sum(overhead),
        "unfinished_kwh": sum(remaining),
        "starts": sum(starts),
        "restarts": sum(s - 1 for s in starts if s >= 1),
        "cap_interventions": interventions,
        "infeasible_hours": infeasible,
        "training_energy_cost": training_cost,
        "total_energy_cost": total_cost,
    }
    return {"totals": totals, "jobs": outcomes, "hours": records, "misses": misses,
            "diagnosis": diagnose(world, outcomes, remaining, totals)}


if __name__ == "__main__":
    import importlib

    from flex.scenarios import by_id

    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default="incumbent")
    ap.add_argument("--scenario", default="dev-11-low")
    args = ap.parse_args()
    sc = by_id(args.scenario)
    assert sc["split"] != "final", "the CLI never runs final scenarios"
    policy = getattr(importlib.import_module(f"policies.{args.policy}"), args.policy.upper())
    world = build_world(sc, prices(sc["start"], sc["arrival_days"] * 24 + sc["tail_h"]))
    result = simulate(world, policy, "cli", args.policy)
    print(result["totals"])
    print("\n".join(result["diagnosis"]))
