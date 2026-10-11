"""Export the read-only demonstration data, or generate it with the real simulator."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from flex.contract import HarnessVersion, HourRecord, JobOutcome, Miss, Run
from flex.evaluate import accept, identity, run
from flex.scenarios import dev, validation
from policies.control_repair import CONTROL_REPAIR
from policies.incumbent import INCUMBENT

OUTPUT = ROOT / "web/public/replay.json"


def fixture():
    scenarios = [s for s in dev() if s["id"] in ("dev-12-low", "dev-12-high")] + validation()
    now = datetime.now(timezone.utc)
    rejected = {
        "context_fields": ["event_now", "price_pct"],
        "rules": [
            {"when": [{"field": "event_now", "op": "==", "value": True}], "power": 0.0},
            {"when": [{"field": "price_pct", "op": "<=", "value": 0.3}], "power": 1.0},
        ],
        "default_power": 0.0,
    }
    specifications = [
        ("fixture-incumbent", INCUMBENT, "baseline", "champion",
         "Frozen scheduler tuned on low restart-cost development scenarios.",
         "Preserve the original schedule when restart warm-up is inexpensive."),
        ("fixture-control-repair", CONTROL_REPAIR, "control", "candidate",
         "Hand-authored feasibility control. Keep warm jobs running through moderately expensive hours and begin urgent work earlier.",
         "Fewer cold starts should restore deadlines. Training electricity may cost more."),
        ("fixture-control-cheap", rejected, "control", "candidate",
         "Hand-authored rejected control. Request training only in the cheapest 30% of hours.",
         "Lower prices may reduce electricity cost, but omitting urgency risks deadlines."),
    ]
    replay = {"schema_version": 1, "source": "fixture", "generated_at": now,
              "versions": [], "runs": [], "hours": [], "misses": [], "scenarios": scenarios}
    baseline = None
    for version_id, policy, author, status, rationale, predicted in specifications:
        results = run(policy, scenarios, version_id)
        evaluation = identity(policy, validation())
        version = {"_id": version_id, "parent": None if author == "baseline" else "fixture-incumbent",
                   "policy": policy, "rationale": rationale, "predicted": predicted, "author": author,
                   "status": status, "identity": evaluation, "created_at": now}
        if baseline is None:
            baseline = results
        else:
            validation_ids = {s["id"] for s in validation()}
            version["verdict"] = accept(policy, {key: value for key, value in baseline.items() if key in validation_ids},
                                         {key: value for key, value in results.items() if key in validation_ids})
            version["status"] = "champion" if version["verdict"]["accepted"] else "rejected"
        replay["versions"].append(version)
        for scenario in scenarios:
            result = results[scenario["id"]]
            run_id = f"{version_id}:{scenario['id']}"
            replay["runs"].append({"_id": run_id, "version": version_id, "scenario": scenario["id"],
                                   "split": scenario["split"], "totals": result["totals"],
                                   "identity": identity(policy, [s for s in scenarios if s["split"] == scenario["split"]]),
                                   "created_at": now,
                                   "jobs": result["jobs"], "diagnosis": result["diagnosis"]})
            meta = {"run": run_id, "version": version_id, "scenario": scenario["id"]}
            replay["hours"].extend({**hour, "meta": meta} for hour in result["hours"])
            replay["misses"].extend(result["misses"])
    return replay


def recorded():
    from flex.store import client

    fields = {
        "versions": ("harness_versions", list(HarnessVersion.__annotations__)),
        "runs": ("runs", [*Run.__annotations__, "jobs", "diagnosis"]),
        "hours": ("hours", [*HourRecord.__annotations__, "meta"]),
        "misses": ("misses", list(Miss.__annotations__)),
    }
    replay = {"schema_version": 1, "source": "recorded evaluation replay",
              "generated_at": datetime.now(timezone.utc), "scenarios": dev() + validation()}
    connection = client("reader")
    try:
        db = connection["flex"]
        for key, (collection, allowed) in fields.items():
            projection = {field: 1 for field in allowed}
            if "_id" not in allowed:
                projection["_id"] = 0
            replay[key] = [sanitize(key, record) for record in db[collection].find({}, projection)]
    finally:
        connection.close()
    return replay


def sanitize(kind, record):
    from flex.contract import EvalIdentity, Policy, Totals, Verdict

    def pick(value, fields):
        return {key: value[key] for key in fields if key in value}

    if kind == "versions":
        raw_policy = record.get("policy")
        record["policy"] = pick(raw_policy, Policy.__annotations__) if isinstance(raw_policy, dict) else None
        if record["policy"] and isinstance(record["policy"].get("rules"), list):
            rules = []
            for raw_rule in record["policy"]["rules"]:
                rule = pick(raw_rule, ("power", "when")) if isinstance(raw_rule, dict) else None
                if rule and isinstance(rule.get("when"), list):
                    conditions = []
                    for raw_condition in rule["when"]:
                        condition = pick(raw_condition, ("field", "op", "value")) if isinstance(raw_condition, dict) else None
                        if condition and isinstance(condition.get("value"), dict):
                            condition["value"] = pick(condition["value"], ("field", "times", "plus"))
                        conditions.append(condition)
                    rule["when"] = conditions
                rules.append(rule)
            record["policy"]["rules"] = rules
        if "verdict" in record:
            record["verdict"] = pick(record["verdict"], Verdict.__annotations__)
    if "identity" in record:
        record["identity"] = pick(record["identity"], EvalIdentity.__annotations__)
    if kind == "runs":
        record["totals"] = pick(record["totals"], Totals.__annotations__)
        if "jobs" in record:
            record["jobs"] = [pick(job, JobOutcome.__annotations__) for job in record["jobs"]]
    if kind == "hours":
        record["meta"] = pick(record["meta"], ("run", "version", "scenario"))
    if kind == "misses":
        from flex.contract import Obs
        record["context"] = pick(record["context"], Obs.__annotations__)
    return record


def serialize(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Unsupported replay value {type(value).__name__}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args()
    try:
        replay = fixture() if args.fixture else recorded()
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(replay, default=serialize, separators=(",", ":"), allow_nan=False)
        pending = OUTPUT.parent.parent / ".replay.tmp"
        pending.write_text(payload + "\n")
        pending.replace(OUTPUT)
        print(f"Exported {replay['source']}: {len(replay['versions'])} versions, "
              f"{len(replay['runs'])} runs, {len(replay['hours'])} hours to web/public/replay.json")
    except Exception as error:
        print(f"Replay export failed ({type(error).__name__}). Check the reader setup and source records.", file=sys.stderr)
        sys.exit(1)
