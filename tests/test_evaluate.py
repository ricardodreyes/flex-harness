from pathlib import Path

import pytest

from flex.evaluate import accept, identity, run
from flex.scenarios import by_id, dev, validation
from flex.world import FINAL_PRICES, PRICES
from policies.incumbent import INCUMBENT


def res(cost: float, late: int = 0, unfinished: float = 0.0, infeasible: int = 0, diagnosis=(), cap: int = 0,
        completed: int = 40):
    return {"totals": {"jobs_completed": completed, "late_job_hours": late, "unfinished_kwh": unfinished,
                       "cap_interventions": cap, "infeasible_hours": infeasible, "training_energy_cost": cost},
            "diagnosis": list(diagnosis)}


def test_repair_accepted_with_positive_cost_delta():
    champ = {"a": res(100.0), "b": res(100.0, late=5)}
    cand = {"a": res(110.0), "b": res(110.0)}
    v = accept(INCUMBENT, champ, cand)
    assert v["accepted"] and v["fixed"] == ["b"] and v["regressed"] == []
    assert v["cost_delta_pct"] == pytest.approx(10.0)  # 220 vs 200
    assert "repairs b; training energy +10.00% to restore deadlines" in v["reasons"]


def test_regression_rejected():
    champ = {"a": res(100.0), "b": res(100.0, late=5)}
    cand = {"a": res(50.0, late=1), "b": res(50.0)}
    v = accept(INCUMBENT, champ, cand)
    assert not v["accepted"] and v["regressed"] == ["a"]
    assert "regression on a: late_job_hours 0 -> 1" in v["reasons"]


def test_partial_rejected():
    champ = {"a": res(100.0), "b": res(100.0, late=5)}
    cand = {"a": res(100.0), "b": res(100.0, late=2)}
    v = accept(INCUMBENT, champ, cand)
    assert not v["accepted"] and v["fixed"] == []
    assert "partial: b late job-hours 5 -> 2, still failing" in v["reasons"]


def test_within_tolerance_rejected():
    v = accept(INCUMBENT, {"a": res(100.0)}, {"a": res(99.5)})  # -0.5%, tolerance is 1%
    assert not v["accepted"]
    assert "within tolerance: -0.50%, needs below -1%" in v["reasons"]


def test_cheaper_accepted():
    v = accept(INCUMBENT, {"a": res(100.0)}, {"a": res(95.0)})
    assert v["accepted"] and v["cost_delta_pct"] == pytest.approx(-5.0)
    assert "cheaper: training energy -5.00%" in v["reasons"]


def test_cost_increase_worded_not_cheaper():
    v = accept(INCUMBENT, {"a": res(100.0)}, {"a": res(110.1)})
    assert not v["accepted"]
    assert "not cheaper: training energy +10.10%" in v["reasons"]


def test_negative_costs_rising_rejected():
    v = accept(INCUMBENT, {"a": res(-100.0)}, {"a": res(-99.5)})
    assert not v["accepted"] and v["cost_delta_pct"] == pytest.approx(0.5)
    assert "not cheaper: training energy +0.50%" in v["reasons"]
    v = accept(INCUMBENT, {"a": res(-100.0)}, {"a": res(-100.0)})
    assert not v["accepted"] and v["cost_delta_pct"] == 0.0
    v = accept(INCUMBENT, {"a": res(-100.0)}, {"a": res(-105.0)})
    assert v["accepted"] and v["cost_delta_pct"] == pytest.approx(-5.0)


def test_zero_champion_cost():
    assert not accept(INCUMBENT, {"a": res(0.0)}, {"a": res(0.0)})["accepted"]
    v = accept(INCUMBENT, {"a": res(0.0)}, {"a": res(-1.0)})
    assert v["accepted"] and v["cost_delta_pct"] is None


def test_abandoning_work_rejected():
    # dev-11-low as measured: constant-full completes all 40 jobs but trips the cap; constant-zero does nothing
    champ = {"dev-11-low": res(3995.68, cap=8, completed=40)}
    cand = {"dev-11-low": res(0.0, unfinished=258022.0, late=13361, completed=0)}
    v = accept(INCUMBENT, champ, cand)
    assert not v["accepted"] and v["regressed"] == ["dev-11-low"]
    assert "regression on dev-11-low: late_job_hours 0 -> 13361, unfinished_kwh 0 -> 258022, " \
           "jobs_completed 40 -> 0" in v["reasons"]


def test_missing_scenario_rejected():
    champ = {"a": res(100.0), "b": res(100.0)}
    v = accept(INCUMBENT, champ, {"a": res(50.0)})
    assert not v["accepted"] and v["reasons"] == ["incomplete evaluation: missing b"]
    v = accept(INCUMBENT, champ, {"a": res(50.0), "b": res(50.0), "c": res(1.0)})
    assert not v["accepted"] and v["reasons"] == ["incomplete evaluation: missing c"]


def test_dev_and_validation_never_open_final_prices(monkeypatch):
    opened = []
    real_text, real_bytes = Path.read_text, Path.read_bytes

    def spy_text(self, *a, **k):
        opened.append(self)
        return real_text(self, *a, **k)

    def spy_bytes(self, *a, **k):
        opened.append(self)
        return real_bytes(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", spy_text)
    monkeypatch.setattr(Path, "read_bytes", spy_bytes)
    identity(INCUMBENT, dev())
    identity(INCUMBENT, validation())
    run(INCUMBENT, [by_id("dev-11-low"), by_id("val-21-high")], "v")
    assert PRICES in opened
    assert FINAL_PRICES not in opened
    assert all("final" not in str(p) for p in opened)


def test_invalid_rejected():
    v = accept({"context_fields": [], "rules": [], "default_power": 2.0}, {"a": res(100.0)}, {"a": res(1.0)})
    assert not v["accepted"] and v["reasons"][0] == "invalid policy"


def test_infeasible_scenario_excluded():
    champ = {"a": res(100.0), "imp": res(100.0, late=50, diagnosis=["job x ...: impossible for any policy"])}
    cand = {"a": res(95.0), "imp": res(100.0, late=10, diagnosis=["job x ...: impossible for any policy"])}
    v = accept(INCUMBENT, champ, cand)
    assert v["accepted"] and v["cost_delta_pct"] == pytest.approx(-5.0)
    assert "infeasible scenario imp, excluded" in v["reasons"]
