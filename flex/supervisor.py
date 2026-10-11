"""One Opus call per proposal. The prompt carries dev evidence only; validation contributes verdict reasons."""

import json
from pathlib import Path
from typing import Literal

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

from flex import evaluate
from flex.contract import OBS_FIELDS, HarnessVersion, Miss, Op, SimResult
from flex.scenarios import dev

load_dotenv(Path(__file__).parent.parent / ".env")

ObsField = Literal[OBS_FIELDS]


class FieldRef(BaseModel):
    field: ObsField
    times: float
    plus: float


class Condition(BaseModel):
    field: ObsField
    op: Op
    value: bool | float | FieldRef


class Rule(BaseModel):
    when: list[Condition]
    power: float


class PolicyModel(BaseModel):
    context_fields: list[ObsField]
    rules: list[Rule]
    default_power: float


class Proposal(BaseModel):
    policy: PolicyModel
    rationale: str
    predicted: str


FIELD_DOCS = {
    "hour_of_day": "Hour of the day, 0 to 23, Pacific time.",
    "price": "Day-ahead electricity price for this hour, $/MWh.",
    "price_pct": "Share of the already-published prices for the rest of today (plus tomorrow after 13:00) that are "
                 "below this hour's price. 0 is the cheapest hour known, near 1 the dearest.",
    "event_now": "True while a grid event is active and the safety cap applies (bool).",
    "event_in_h": "Hours until the next event within 24 h, else None. A condition on a None field is false.",
    "slack_h": "Hours until the earliest active deadline; 99 when no job is queued.",
    "need_h": "Hours at the 700 kW ceiling to finish all queued work, excluding warm-up.",
    "queued_jobs": "Number of jobs queued.",
    "running": "True when the earliest-deadline job got power last hour, so it is warm (bool).",
    "restart_kwh": "Operator observation of the warm-up energy each cold start owes.",
}
assert set(FIELD_DOCS) == set(OBS_FIELDS)
SCHEMA = anthropic.transform_schema(Proposal)

SYSTEM = f"""You supervise a training-power scheduler for an AI data center. Each hour the scheduler requests a \
training fraction of the 700 kW ceiling. Its policy is an ordered rule list: the first rule whose conditions all hold \
sets the power fraction, otherwise default_power applies. You propose a changed policy; a fixed evaluator you cannot \
edit decides whether it is accepted.

Physics, identical for every policy:
- One step is one hour, so kW drawn equals kWh. Work is measured in productive training kWh; a 4,200 kWh job takes 6 \
hours at the ceiling.
- During grid events a safety controller limits training to the site cap minus inference load, never below zero. \
Requesting more than that is a cap intervention and counts as a failure.
- Executed power is the smallest of the request, the safety limit, and what the queue can absorb.
- Power goes to active jobs earliest-deadline first. A job that receives no power in an hour goes cold. Every start \
of a cold job owes restart_kwh of warm-up first: drawn and billed, but no progress. Pausing is therefore not free \
when restart_kwh is large.
- Work unfinished at the end is backlog and counts as a failure.

Priorities, in order: physical limits, then deadlines and completed work, then electricity cost. A repair may cost \
more if it restores deadlines. A scenario passes with zero late job-hours, zero unfinished work and zero \
cap interventions.

Policy bounds, enforced by a validator. A proposal that breaks them is recorded as a rejected version:
- At most 8 rules, at most 4 conditions per rule, at most 4096 bytes as JSON.
- Conditions may only read fields listed in context_fields, and the policy only ever receives those fields.
- Power values are in [0, 1]. Operators are <, <=, >, >=, ==.
- Bool fields (event_now, running) take a bool value and only ==.
- A condition value is a number or a field reference {{field, times, plus}} meaning field * times + plus. times is in \
[0, 100]. A reference cannot point at a bool field.

Observation fields:
{chr(10).join(f"- {k}: {v}" for k, v in FIELD_DOCS.items())}

You receive the current champion policy, its results on the development scenarios (totals and diagnosis lines), recent \
misses, and recent rejected proposals with the evaluator's reasons. Return a changed policy, a short rationale, and a \
falsifiable prediction about development scenarios, for example "late job-hours on dev-12-high go from 5 to 0"."""


def _dump(x) -> str:
    return json.dumps(x, indent=1, default=str)


def evidence(champion: HarnessVersion, dev_results: dict[str, SimResult], misses: list[Miss],
             rejected: list[HarnessVersion]) -> str:
    """Infeasible scenarios and scenario notes stay out: no policy can act on them."""
    assert set(dev_results) <= {s["id"] for s in dev()}, "evidence takes dev results only"
    results = {sid: r for sid, r in dev_results.items() if evaluate.feasible(r)}
    parts = [f"Champion policy ({champion['_id']}):\n{_dump(champion['policy'])}"]
    for sid, r in results.items():
        parts.append(f"Scenario {sid}\nTotals: {_dump(r['totals'])}\nDiagnosis:\n"
                     + "\n".join(f"- {d}" for d in r["diagnosis"]))
    parts.append("Recent misses:\n" + _dump([{k: v for k, v in m.items() if k not in ("run", "version")}
                                              for m in misses if m["scenario"] in results]))
    parts.append("Recent rejected proposals:\n" + _dump([
        {"policy": v["policy"], "predicted": v["predicted"], "reasons": v.get("verdict", {}).get("reasons", [])}
        for v in rejected[-5:]]))
    return "\n\n".join(parts)


def _short(e: Exception) -> str:
    return f"{type(e).__name__}: {str(e)[:120]}"


def _raw(text: str, error: str) -> dict:
    return {"policy": {"raw": text[:2000]}, "rationale": "", "predicted": "", "error": error}


def read_proposal(text: str) -> dict:
    """The model's JSON as sent: the policy is never round-tripped, so the validator sees exactly what it wrote."""
    try:
        obj = json.loads(text)
    except ValueError as e:
        return _raw(text, _short(e))
    text_of = {k: obj[k] for k in ("rationale", "predicted") if isinstance(obj, dict) and isinstance(obj.get(k), str)}
    if isinstance(obj, dict) and "policy" in obj and len(text_of) == 2:
        return {"policy": obj["policy"], **text_of, "error": None}
    return {"policy": obj, "rationale": "", "predicted": "", **text_of,
            "error": "response is not an object with policy, rationale and predicted"}


def propose(champion: HarnessVersion, dev_results: dict[str, SimResult], misses: list[Miss],
            rejected: list[HarnessVersion]) -> dict:
    # 32000 non-streaming tokens trips the SDK's 10 minute guard, so stream
    with anthropic.Anthropic().beta.messages.stream(
            model="claude-opus-5-5", max_tokens=32000, thinking={"type": "adaptive"},
            output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", system=SYSTEM,
            messages=[{"role": "user", "content": evidence(champion, dev_results, misses, rejected)}]) as stream:
        response = stream.get_final_message()
    text = "".join(b.text for b in response.content if b.type == "text")
    if response.stop_reason == "refusal":
        env = _raw(text, f"model refused, category {response.stop_details and response.stop_details.category}")
    elif response.stop_reason == "max_tokens":
        env = _raw(text, "hit max_tokens")
    else:
        env = read_proposal(text)
    return {**env, "model": response.model,
            "usage": {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens}}
