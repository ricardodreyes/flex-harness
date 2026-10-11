"""Grid searches on dev scenarios only. Paste the winners into policies/ as literals."""

import itertools

from flex.contract import Policy, Scenario
from flex.evaluate import passes, run
from flex.scenarios import dev

# Widened at 1:10 p.m.: the first grid (U up to 1.5, C up to 4) had no point passing every dev-*-low.
U = (1.0, 1.2, 1.5, 2.0, 2.5, 3.0)
C = (0, 2, 4, 6)
Q = (0.1, 0.2, 0.3, 0.4, 0.5)
H = (0.5, 0.6, 0.7, 0.8, 0.9)


def incumbent(u: float, c: float, q: float) -> Policy:
    return {
        "context_fields": ["event_now", "slack_h", "need_h", "price_pct"],
        "rules": [
            {"when": [{"field": "event_now", "op": "==", "value": True}], "power": 0.0},
            {"when": [{"field": "slack_h", "op": "<=", "value": {"field": "need_h", "times": u, "plus": c}}],
             "power": 1.0},
            {"when": [{"field": "price_pct", "op": "<=", "value": q}], "power": 1.0},
        ],
        "default_power": 0.0,
    }


def restart_aware(u: float, c: float, q: float, h: float) -> Policy:
    base = incumbent(u, c, q)
    return {
        "context_fields": base["context_fields"] + ["running", "restart_kwh"],
        "rules": base["rules"][:2] + [
            {"when": [{"field": "running", "op": "==", "value": True}, {"field": "price_pct", "op": "<=", "value": h}],
             "power": 1.0},
            base["rules"][2],
        ],
        "default_power": 0.0,
    }


def search(name: str, grid: list[tuple], make, scenarios: list[Scenario]):
    scored = []
    for params in grid:
        results = run(make(*params), scenarios, "tune")
        late = sum(r["totals"]["late_job_hours"] for r in results.values())
        unfinished = sum(r["totals"]["unfinished_kwh"] for r in results.values())
        cost = sum(r["totals"]["training_energy_cost"] for r in results.values())
        scored.append((not all(passes(r["totals"]) for r in results.values()), late, unfinished, cost, params))
    failing, late, unfinished, cost, params = min(scored)
    ids = [s["id"] for s in scenarios]
    if failing:
        print(f"{name}: no params pass all of {ids}; least-late {params} has {late} late job-hours, "
              f"{unfinished:,.0f} kWh unfinished, ${cost:,.2f} training energy")
    else:
        print(f"{name}: params {params} pass {ids} at ${cost:,.2f} training energy")


if __name__ == "__main__":
    low = [s for s in dev() if s["id"].endswith("-low")]
    high = [s for s in dev() if s["id"].endswith("-high")]
    search("incumbent (u, c, q)", list(itertools.product(U, C, Q)), incumbent, low)
    search("restart_aware (u, c, q, h)", list(itertools.product(U, C, Q, H)), restart_aware, high)
