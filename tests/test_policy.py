import copy
import math

import pytest

import flex.sim
from flex.evaluate import run
from flex.policy import PolicyError, compile_policy, validate
from flex.scenarios import by_id
from policies.incumbent import INCUMBENT

VALID = {
    "context_fields": ["price_pct", "running", "need_h"],
    "rules": [{"when": [{"field": "price_pct", "op": "<=", "value": 0.3}], "power": 1.0}],
    "default_power": 0.0,
}


def variant(**changes):
    p = copy.deepcopy(VALID)
    p.update(changes)
    return p


def rule(field="price_pct", op="<=", value=0.3, power=1.0, n=1):
    return variant(rules=[{"when": [{"field": field, "op": op, "value": value}] * n, "power": power}])


INVALID = {
    "negative power": rule(power=-0.1),
    "power 1.5": rule(power=1.5),
    "nan power": rule(power=math.nan),
    "inf value": rule(value=math.inf),
    "string power": rule(power="1.0"),
    "bool power": rule(power=True),
    "unknown field": rule(field="weather"),
    "field not in context": rule(field="slack_h"),
    "op !=": rule(op="!="),
    "9 rules": variant(rules=[VALID["rules"][0]] * 9),
    "5 conditions": rule(n=5),
    "payload > 4096 bytes": variant(context_fields=["price_pct"] + ["a" * 5000]),
    "extra key restart_kwh": variant(restart_kwh=0.0),
    "bool value on numeric field": rule(value=True),
    "non-bool value on running": rule(field="running", op="==", value=1),
    "not a dict": "def decide(obs): return 1",
    "rules not a list": variant(rules="x"),
    "none": None,
    "list": [],
    "list field": rule(field=["price_pct"]),
    "dict op": rule(op={"<=": 1}),
    "list value": rule(value=[0.3]),
    "list ref field": rule(value={"field": ["need_h"], "times": 1, "plus": 0}),
    "dict field on bool": rule(field={"running": True}, op="==", value=True),
    "huge int power": rule(power=10**309),
    "huge int value": rule(value=10**309),
    "huge int times": rule(value={"field": "need_h", "times": 10**309, "plus": 0}),
    "nested junk": variant(rules=[{"when": [[[]]], "power": [[]]}, [], None, 1]),
    "none condition": variant(rules=[{"when": [None], "power": 1.0}]),
    "none power": rule(power=None),
}
REASON = {
    "none": "policy must be an object",
    "list": "policy must be an object",
    "list field": "field and op must be strings",
    "dict op": "field and op must be strings",
    "list value": "value must be a finite number",
    "list ref field": "reference to unknown field",
    "dict field on bool": "field and op must be strings",
    "huge int power": "power must be a finite number in [0, 1]",
    "huge int value": "value must be a finite number",
    "huge int times": "times must be a finite number",
    "nested junk": "must have exactly when and power",
    "none condition": "condition must be an object",
    "none power": "power must be a finite number",
}


@pytest.mark.parametrize("name", list(INVALID))
def test_invalid_policy_gets_a_reason(name):
    reasons = validate(INVALID[name])
    assert reasons, name
    if name in REASON:
        assert any(REASON[name] in r for r in reasons), reasons
    with pytest.raises(PolicyError):
        compile_policy(INVALID[name])


def test_protected_setting_named():
    assert "restart_kwh: protected setting" in validate(variant(restart_kwh=0.0))


def test_valid_policy_has_no_reasons():
    assert validate(VALID) == []
    assert validate(INCUMBENT) == []


def test_first_match_wins_and_none_is_false():
    decide = compile_policy(variant(rules=[
        {"when": [{"field": "need_h", "op": ">", "value": 1}], "power": 0.5},
        {"when": [{"field": "price_pct", "op": "<=", "value": 0.3}], "power": 1.0}]))
    assert decide({"need_h": 2, "price_pct": 0.1}) == 0.5
    assert decide({"need_h": None, "price_pct": 0.1}) == 1.0
    assert decide({"need_h": 0, "price_pct": 0.9}) == 0.0


def test_rule_change_changes_executed_kw():
    sc = by_id("dev-11-low")
    changed = copy.deepcopy(INCUMBENT)
    changed["rules"][2]["when"][0]["value"] = 0.2
    a, b = (run(p, [sc], "v")[sc["id"]] for p in (INCUMBENT, changed))
    assert [h["executed_kw"] for h in a["hours"]] != [h["executed_kw"] for h in b["hours"]]


def test_policy_sees_only_context_fields(monkeypatch):
    seen = []
    real = compile_policy

    def wrap(policy):
        decide = real(policy)

        def spy(obs):
            seen.append(set(obs))
            return decide(obs)
        return spy

    monkeypatch.setattr(flex.sim, "compile_policy", wrap)
    sc = by_id("dev-11-low")
    run(VALID, [sc], "v")
    assert seen and all(s == set(VALID["context_fields"]) for s in seen)
