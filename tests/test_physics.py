import pytest

from flex.contract import Policy, Scenario, World
from flex.evaluate import passes, run
from flex.scenarios import by_id
from flex.sim import simulate
from flex.world import build_world, prices

FULL: Policy = {"context_fields": [], "rules": [], "default_power": 1.0}
# runs every hour except hour-of-day 1, so a job started at h0 is paused at h1 and resumes cold at h2
PAUSE_AT_1: Policy = {"context_fields": ["hour_of_day"],
                      "rules": [{"when": [{"field": "hour_of_day", "op": "==", "value": 1}], "power": 0.0}],
                      "default_power": 1.0}


def world(hours: int, jobs, restart_kwh=0.0, event_cap=280.0, inference=100.0, event=(), price=30.0,
          cutoff=None) -> World:
    sc: Scenario = {"id": "t", "split": "dev", "start": "2026-04-01", "arrival_days": 1, "tail_h": 72, "seed": 0,
                    "settings": {"restart_kwh": restart_kwh, "event_cap_kw": event_cap, "work_scale": 1.0},
                    "note": ""}
    return {"scenario": sc, "price": [price] * hours, "inference_kw": [inference] * hours,
            "event": [h in event for h in range(hours)],
            "jobs": [{"id": f"j{i}", "arrive_h": a, "deadline_h": d, "work_kwh": w} for i, (a, d, w) in enumerate(jobs)],
            "arrival_cutoff_h": cutoff if cutoff is not None else hours}


def test_empty_queue_draws_nothing():
    r = simulate(world(3, []), FULL, "t", "v")
    assert [h["requested_kw"] for h in r["hours"]] == [700.0] * 3
    assert [h["executed_kw"] for h in r["hours"]] == [0.0] * 3
    # 3 h x 100 kW x $0.03 = $9, nothing for training
    assert r["totals"]["total_energy_cost"] == pytest.approx(9.0)
    assert r["totals"]["training_energy_cost"] == 0.0


def test_partial_final_hour_bills_only_what_ran():
    r = simulate(world(3, [(0, 10, 1000.0)]), FULL, "t", "v")
    assert [h["executed_kw"] for h in r["hours"]] == [700.0, 300.0, 0.0]
    # hour 2: (300 + 100) x $0.03 = $12; hour 1: (700 + 100) x 0.03 = $24; hour 3: $3
    assert [h["energy_cost"] for h in r["hours"]] == pytest.approx([24.0, 12.0, 3.0])
    assert r["totals"]["training_energy_cost"] == pytest.approx(30.0)
    assert r["jobs"][0]["done_h"] == 1


def test_conservation_on_dev_scenario():
    from policies.incumbent import INCUMBENT
    r = run(INCUMBENT, [by_id("dev-12-high")], "v")["dev-12-high"]
    t = r["totals"]
    assert (t["jobs_total"], t["jobs_completed"], len(r["hours"])) == (41, 41, 696)
    assert t["work_kwh"] == pytest.approx(289807.07, abs=0.01)
    assert t["overhead_kwh"] == pytest.approx(68429.06, abs=0.01)
    executed = sum(h["executed_kw"] for h in r["hours"])
    assert executed == pytest.approx(sum(h["productive_kw"] + h["overhead_kw"] for h in r["hours"]))
    assert t["productive_kwh"] == pytest.approx(t["work_kwh"] - t["unfinished_kwh"])
    assert t["overhead_kwh"] == pytest.approx(sum(h["overhead_kw"] for h in r["hours"]))


def test_last_hour_arrival_completes_in_tail():
    r = simulate(world(6, [(1, 40, 1400.0)], cutoff=2), FULL, "t", "v")
    assert r["jobs"][0]["done_h"] == 2
    assert r["totals"]["unfinished_kwh"] == 0


def test_terminal_backlog():
    # 7000 kWh is 10 h at the ceiling; a 4 h window and a 6 h world leave 7000 - 6 x 700 = 2800 unfinished
    r = simulate(world(6, [(0, 4, 7000.0)]), FULL, "t", "v")
    t = r["totals"]
    assert t["unfinished_kwh"] == pytest.approx(2800.0)
    assert t["late_job_hours"] == 3  # hours 3, 4 and 5: due at the start of hour 4
    assert t["jobs_completed"] == 0
    assert any("impossible for any policy" in d for d in r["diagnosis"])
    assert any("unfinished" in d for d in r["diagnosis"])
    assert [m["kind"] for m in r["misses"]].count("unfinished") == 1


def test_deadline_is_start_of_hour():
    # 700 kWh due at the start of hour 1: idle in h0 then full in h1 finishes one hour late and fails
    idle_h0: Policy = {"context_fields": ["hour_of_day"],
                       "rules": [{"when": [{"field": "hour_of_day", "op": "==", "value": 0}], "power": 0.0}],
                       "default_power": 1.0}
    r = simulate(world(3, [(0, 1, 700.0)]), idle_h0, "t", "v")
    assert (r["jobs"][0]["done_h"], r["jobs"][0]["late_h"], r["totals"]["late_job_hours"]) == (1, 1, 1)
    assert not passes(r["totals"])
    r = simulate(world(3, [(0, 1, 700.0)]), FULL, "t", "v")
    assert (r["jobs"][0]["done_h"], r["jobs"][0]["late_h"], r["totals"]["late_job_hours"]) == (0, 0, 0)
    assert passes(r["totals"])


def test_dev_scenario_workload_literals():
    sc = by_id("dev-11-low")
    w = build_world(sc, prices(sc["start"], sc["arrival_days"] * 24 + sc["tail_h"]))
    assert len(w["jobs"]) == 40
    assert round(sum(j["work_kwh"] for j in w["jobs"])) == 258022
    assert w["arrival_cutoff_h"] == 624
    assert len(w["price"]) == len(w["inference_kw"]) == len(w["event"]) == 696


def test_fixed_limits():
    # event hour 1 with 200 kW inference: safety limit 80 kW, the full request is cut and counted
    r = simulate(world(3, [(0, 10, 5000.0)], inference=200.0, event=(1,)), FULL, "t", "v")
    assert [h["executed_kw"] for h in r["hours"]] == [700.0, 80.0, 700.0]
    assert r["totals"]["cap_interventions"] == 1
    assert r["totals"]["infeasible_hours"] == 0
    assert all(h["executed_kw"] <= min(700.0, h["safety_limit_kw"]) for h in r["hours"])
    # inference 300 kW above the 280 cap: infeasible hour, nothing for training
    r = simulate(world(2, [(0, 10, 5000.0)], inference=300.0, event=(1,)), FULL, "t", "v")
    assert r["hours"][1]["executed_kw"] == 0.0
    assert r["totals"]["infeasible_hours"] == 1
    assert any("infeasible for the training controller" in d for d in r["diagnosis"])


def test_warm_up_paid_on_every_cold_start():
    # 1400 kWh job, restart 100: h0 pays 100 warm-up + 600 work, h1 paused, h2 pays 100 again + 600, h3 does 200
    r = simulate(world(5, [(0, 10, 1400.0)], restart_kwh=100.0), PAUSE_AT_1, "t", "v")
    assert [h["executed_kw"] for h in r["hours"]] == [700.0, 0.0, 700.0, 200.0, 0.0]
    assert [h["overhead_kw"] for h in r["hours"]] == [100.0, 0.0, 100.0, 0.0, 0.0]
    assert r["jobs"][0]["overhead_kwh"] == 200.0
    assert (r["jobs"][0]["starts"], r["totals"]["restarts"]) == (2, 1)
    assert r["jobs"][0]["done_h"] == 3


def test_same_arrivals_and_inference_across_policies():
    from policies.control_repair import CONTROL_REPAIR
    from policies.incumbent import INCUMBENT
    sc = by_id("dev-11-low")
    a, b = (run(p, [sc], "v")[sc["id"]] for p in (INCUMBENT, CONTROL_REPAIR))
    assert [j["arrive_h"] for j in a["jobs"]] == [j["arrive_h"] for j in b["jobs"]]
    assert [j["work_kwh"] for j in a["jobs"]] == [j["work_kwh"] for j in b["jobs"]]
    assert [h["inference_kw"] for h in a["hours"]] == [h["inference_kw"] for h in b["hours"]]
    assert a["totals"]["work_kwh"] == b["totals"]["work_kwh"]
    assert (len(a["jobs"]), len(a["hours"]), round(a["totals"]["work_kwh"])) == (40, 696, 258022)
    assert round(sum(h["inference_kw"] for h in a["hours"])) == 118449
