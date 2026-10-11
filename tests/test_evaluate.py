import pytest

from flex.evaluate import accept
from policies.incumbent import INCUMBENT


def res(cost: float, late: int = 0, unfinished: float = 0.0, infeasible: int = 0, diagnosis=()):
    return {"totals": {"late_job_hours": late, "unfinished_kwh": unfinished, "cap_interventions": 0,
                       "infeasible_hours": infeasible, "training_energy_cost": cost},
            "diagnosis": list(diagnosis)}


def test_repair_accepted_with_positive_cost_delta():
    champ = {"a": res(100.0), "b": res(100.0, late=5)}
    cand = {"a": res(110.0), "b": res(110.0)}
    v = accept(INCUMBENT, champ, cand)
    assert v["accepted"] and v["fixed"] == ["b"] and v["regressed"] == []
    assert v["cost_delta_pct"] == pytest.approx(10.0)  # 220 vs 200
    assert any("costs +10.00%" in r for r in v["reasons"])


def test_regression_rejected():
    champ = {"a": res(100.0), "b": res(100.0, late=5)}
    cand = {"a": res(50.0, late=1), "b": res(50.0)}
    v = accept(INCUMBENT, champ, cand)
    assert not v["accepted"] and v["regressed"] == ["a"]
    assert "regression on a" in v["reasons"]


def test_partial_rejected():
    champ = {"a": res(100.0), "b": res(100.0, late=5)}
    cand = {"a": res(100.0), "b": res(100.0, late=2)}
    v = accept(INCUMBENT, champ, cand)
    assert not v["accepted"] and v["fixed"] == []
    assert any("partial progress on b" in r for r in v["reasons"])


def test_within_tolerance_rejected():
    v = accept(INCUMBENT, {"a": res(100.0)}, {"a": res(99.5)})  # -0.5%, tolerance is 1%
    assert not v["accepted"]
    assert any("within tolerance" in r for r in v["reasons"])


def test_cheaper_accepted():
    v = accept(INCUMBENT, {"a": res(100.0)}, {"a": res(95.0)})
    assert v["accepted"] and v["cost_delta_pct"] == pytest.approx(-5.0)


def test_invalid_rejected():
    v = accept({"context_fields": [], "rules": [], "default_power": 2.0}, {"a": res(100.0)}, {"a": res(1.0)})
    assert not v["accepted"] and v["reasons"][0] == "invalid policy"


def test_infeasible_scenario_excluded():
    champ = {"a": res(100.0), "imp": res(100.0, late=50, diagnosis=["job x ...: impossible for any policy"])}
    cand = {"a": res(95.0), "imp": res(100.0, late=10, diagnosis=["job x ...: impossible for any policy"])}
    v = accept(INCUMBENT, champ, cand)
    assert v["accepted"] and v["cost_delta_pct"] == pytest.approx(-5.0)
    assert "infeasible scenario imp, excluded" in v["reasons"]
