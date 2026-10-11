"""Validates and interprets the bounded rule policy from the contract. No exec, eval, imports or attribute lookup:
the interpreter only reads dict keys of the observation it is handed."""

import json
import math
import operator
from typing import Callable

from flex.contract import BOOL_FIELDS, OBS_FIELDS, Obs, Policy

MAX_RULES = 8
MAX_CONDITIONS = 4
MAX_BYTES = 4096
MAX_ABS = 1e6
MAX_TIMES = 100.0
KEYS = {"context_fields", "rules", "default_power"}
PROTECTED = {"restart_kwh", "event_cap_kw", "work_scale", "settings", "TRAIN_CAP_KW", "event_cap", "restart"}
OPS: dict[str, Callable[[float, float], bool]] = {
    "<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge, "==": operator.eq}


class PolicyError(Exception):
    def __init__(self, reasons: list[str]):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


def _number(v, bound: float = MAX_ABS) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and abs(v) <= bound


def _power(v, where: str, out: list[str]):
    if not _number(v) or not 0.0 <= v <= 1.0:
        out.append(f"{where}: power must be a finite number in [0, 1], got {v!r}")


def _condition(c, where: str, fields: list[str], out: list[str]):
    if not isinstance(c, dict):
        out.append(f"{where}: condition must be an object")
        return
    unknown = set(c) - {"field", "op", "value"}
    if unknown:
        out.append(f"{where}: unknown condition keys {sorted(unknown)}")
    field, op, value = c.get("field"), c.get("op"), c.get("value")
    if field not in OBS_FIELDS:
        out.append(f"{where}: unknown field {field!r}")
    elif field not in fields:
        out.append(f"{where}: field {field!r} is not in context_fields")
    if op not in OPS:
        out.append(f"{where}: op {op!r} not in {sorted(OPS)}")
    if field in BOOL_FIELDS:
        if not isinstance(value, bool):
            out.append(f"{where}: {field} takes a bool value, got {value!r}")
        if op != "==":
            out.append(f"{where}: {field} only supports ==")
    elif isinstance(value, dict):
        if set(value) != {"field", "times", "plus"}:
            out.append(f"{where}: field reference needs exactly field, times, plus")
        ref = value.get("field")
        if ref not in OBS_FIELDS:
            out.append(f"{where}: reference to unknown field {ref!r}")
        elif ref not in fields:
            out.append(f"{where}: referenced field {ref!r} is not in context_fields")
        elif ref in BOOL_FIELDS:
            out.append(f"{where}: cannot reference bool field {ref!r} arithmetically")
        if not _number(value.get("times"), MAX_TIMES) or value["times"] < 0:
            out.append(f"{where}: times must be a finite number in [0, {MAX_TIMES:g}]")
        if not _number(value.get("plus")):
            out.append(f"{where}: plus must be a finite number within ±{MAX_ABS:g}")
    elif not _number(value):
        out.append(f"{where}: value must be a finite number within ±{MAX_ABS:g} or a field reference, got {value!r}")


def validate(policy) -> list[str]:
    """Human-readable reasons the policy is invalid. Empty means valid. Never raises on bad input."""
    if not isinstance(policy, dict):
        return [f"policy must be an object, got {type(policy).__name__}"]
    out: list[str] = []
    for k in sorted(set(policy) - KEYS, key=str):
        out.append(f"{k}: protected setting" if k in PROTECTED else f"unknown key {k!r}")
    for k in sorted(KEYS - set(policy)):
        out.append(f"missing key {k!r}")
    try:
        size = len(json.dumps(policy, separators=(",", ":"), sort_keys=True).encode())
    except (TypeError, ValueError):
        out.append("policy is not plain JSON")
        size = 0
    if size > MAX_BYTES:
        out.append(f"policy is {size} bytes as JSON, limit {MAX_BYTES}")
    fields = policy.get("context_fields", [])
    if not isinstance(fields, list) or not all(isinstance(f, str) for f in fields):
        out.append("context_fields must be a list of field names")
        fields = []
    if len(set(fields)) != len(fields):
        out.append("context_fields must be unique")
    for f in fields:
        if f not in OBS_FIELDS:
            out.append(f"context_fields: unknown field {f!r}")
    rules = policy.get("rules", [])
    if not isinstance(rules, list):
        out.append("rules must be a list")
        rules = []
    if len(rules) > MAX_RULES:
        out.append(f"{len(rules)} rules, limit {MAX_RULES}")
    for i, r in enumerate(rules):
        where = f"rule {i}"
        if not isinstance(r, dict) or set(r) != {"when", "power"}:
            out.append(f"{where}: must have exactly when and power")
            continue
        _power(r["power"], where, out)
        when = r["when"]
        if not isinstance(when, list):
            out.append(f"{where}: when must be a list of conditions")
            continue
        if len(when) > MAX_CONDITIONS:
            out.append(f"{where}: {len(when)} conditions, limit {MAX_CONDITIONS}")
        for j, c in enumerate(when):
            _condition(c, f"{where} condition {j}", fields, out)
    if "default_power" in policy:
        _power(policy["default_power"], "default_power", out)
    return out


def _holds(obs: Obs, field: str, op: str, value) -> bool:
    actual = obs.get(field)
    if actual is None:
        return False
    if isinstance(value, dict):
        ref = obs.get(value["field"])
        if ref is None:
            return False
        value = ref * value["times"] + value["plus"]
    return OPS[op](actual, value)


def compile_policy(policy: Policy) -> Callable[[Obs], float]:
    """First matching rule wins, else default_power. A None observation makes any condition on it false."""
    reasons = validate(policy)
    if reasons:
        raise PolicyError(reasons)
    rules = [([(c["field"], c["op"], c["value"]) for c in r["when"]], float(r["power"])) for r in policy["rules"]]
    default = float(policy["default_power"])

    def decide(obs: Obs) -> float:
        for when, power in rules:
            if all(_holds(obs, f, op, v) for f, op, v in when):
                return power
        return default

    return decide
