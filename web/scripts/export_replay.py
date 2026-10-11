"""Export the read-only demonstration data, or generate it with the real simulator."""

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from flex.contract import HarnessVersion, HourRecord, JobOutcome, Miss, Run, Totals
from flex.evaluate import accept, identity, run
from flex.scenarios import dev, validation
from policies.control_repair import CONTROL_REPAIR
from policies.incumbent import INCUMBENT

OUTPUT = ROOT / "web/public/replay.json"
SCENARIO = "val-26-high"
FOCUS = {"baseline": "v0", "version": "g1-289b1a", "scenario": SCENARIO}
EVOLVE_RUNS = [
    {"run": 1, "versions": ["g1-289b1a", "g2-4c62c7", "g3-efd420", "g4-4a14cc", "g5-683c0e"]},
    {"run": 2, "versions": ["g1-635b00", "g2-9db57e", "g3-c4b5fd", "g4-eac5bd", "g5-e942f4", "g6-e4085d"]},
]
FEATURED_REJECTION = "g4-4a14cc"
FINAL_RESULTS = ROOT / "results/final.json"
FINAL_MANIFEST = ROOT / "results/final_manifest.json"
CREDENTIAL = re.compile(r"sk-ant-|mongodb(?:\+srv)?://[^\s/@:]+:[^\s/@]+@|BEGIN(?: [A-Z0-9]+)* PRIVATE KEY|rdk_", re.IGNORECASE)


class CredentialPatternError(ValueError):
    pass


def check_credentials(value, path="$"):
    if isinstance(value, str):
        if CREDENTIAL.search(value):
            raise CredentialPatternError(f"Credential pattern at {path}")
    elif isinstance(value, dict):
        for index, (key, child) in enumerate(value.items()):
            check_credentials(key, f"{path}[key #{index}]")
            check_credentials(child, f"{path}[{json.dumps(key)}]")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            check_credentials(child, f"{path}[{index}]")


def final_results(path=FINAL_RESULTS, manifest_path=FINAL_MANIFEST):
    from flex.contract import EvalIdentity

    results = json.loads(path.read_text())
    manifest = json.loads(manifest_path.read_text())
    pinned = manifest["pinned"]
    if len(pinned) != 7 or list(results) != [row["version"] for row in pinned]:
        raise ValueError("Final results do not match all seven pinned versions")
    common = pinned[0]["identity"]
    rows = []
    for pin in pinned:
        version = pin["version"]
        record = results[version]
        identity_record = record["identity"]
        if (identity_record != pin["identity"]
                or any(not isinstance(identity_record.get(key), str) or not identity_record[key]
                       for key in ("evaluator_version", "manifest_sha256", "policy_sha256"))
                or identity_record["evaluator_version"] != manifest["evaluator_version"]
                or identity_record["manifest_sha256"] != common["manifest_sha256"]
                or identity_record["scenario_ids"] != common["scenario_ids"]
                or len(identity_record["scenario_ids"]) != 3
                or len(set(identity_record["scenario_ids"])) != 3
                or any(not isinstance(name, str) or not name.startswith("final-")
                       for name in identity_record["scenario_ids"])):
            raise ValueError("Invalid final result identity")
        if (any(record[key] != pin[key] for key in ("author", "acceptance", "role"))
                or record["author"] not in ("baseline", "control", "supervisor")
                or record["acceptance"] not in (None, "repair", "cost")
                or record["role"] not in ("champion", "reference")):
            raise ValueError("Invalid final result labels")
        if set(record["scenarios"]) != set(identity_record["scenario_ids"]):
            raise ValueError("Incomplete final scenario coverage")
        scenarios = {}
        for name in identity_record["scenario_ids"]:
            result = record["scenarios"][name]
            totals = result["totals"]
            if (any(not finite(totals.get(key)) for key in Totals.__annotations__)
                    or any(not isinstance(result.get(key), bool) for key in ("passes", "feasible"))):
                raise ValueError("Incomplete or invalid final totals")
            scenarios[name] = {"totals": {key: totals[key] for key in Totals.__annotations__},
                               "passes": result["passes"], "feasible": result["feasible"]}
        cost = record["training_cost"]
        if not finite(cost) or not math.isclose(cost, sum(row["totals"]["training_energy_cost"]
                                                        for row in scenarios.values()), rel_tol=1e-10, abs_tol=1e-6):
            raise ValueError("Final training cost does not match scenario totals")
        rows.append({"version": version, **{key: record[key] for key in ("author", "acceptance", "role")},
                     "identity": {key: identity_record[key] for key in EvalIdentity.__annotations__},
                     "training_cost": cost, "scenarios": scenarios})
    return rows


def recorded_metadata():
    return {"focus": dict(FOCUS), "evolve_runs": EVOLVE_RUNS,
            "featured_rejection": FEATURED_REJECTION, "final_results": final_results()}


def validate_lineage(replay):
    versions = {version["_id"]: version for version in replay["versions"]}
    grouped = [version for group in replay["evolve_runs"] for version in group["versions"]]
    supervisor = [version["_id"] for version in versions.values() if version["author"] == "supervisor"]
    if len(grouped) != len(set(grouped)) or set(grouped) != set(supervisor):
        raise ValueError("Evolution run mapping does not cover stored supervisor versions")
    for version in versions.values():
        if version["parent"] is not None and version["parent"] not in versions:
            raise ValueError("Lineage parent is unavailable")
    rejected = replay.get("featured_rejection")
    if rejected is not None and versions.get(rejected, {}).get("verdict", {}).get("accepted") is not False:
        raise ValueError("Featured rejection is unavailable")
FIELDS = {
    "versions": list(HarnessVersion.__annotations__),
    "runs": [*Run.__annotations__, "jobs", "diagnosis"],
    "hours": [*HourRecord.__annotations__, "meta"],
    "misses": list(Miss.__annotations__),
}


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
        replay["versions"].append(sanitize("versions", version))
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
    replay.update(final_results=[], evolve_runs=[], featured_rejection=None)
    selected = select_focus(replay)
    replay["hours"] = [hour for hour in replay["hours"] if hour["meta"]["run"] in selected]
    replay["misses"] = [miss for miss in replay["misses"] if miss["run"] in selected]
    validate_hours(replay, selected)
    return replay


def compatible(left, right):
    a, b = left["identity"], right["identity"]
    return (a["evaluator_version"] == b["evaluator_version"]
            and a["manifest_sha256"] == b["manifest_sha256"]
            and sorted(a["scenario_ids"]) == sorted(b["scenario_ids"]))


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def select_focus(replay):
    versions = {version["_id"]: version for version in replay["versions"]}
    if len(versions) != len(replay["versions"]):
        raise ValueError("Duplicate version")
    runs = {}
    ids = set()
    for record in replay["runs"]:
        if any(not finite(record["totals"].get(key)) for key in Totals.__annotations__):
            raise ValueError("Incomplete or invalid run totals")
        if not isinstance(record.get("diagnosis"), list) or any(not isinstance(line, str) for line in record["diagnosis"]):
            raise ValueError("Run diagnosis unavailable")
        jobs = record.get("jobs")
        if not isinstance(jobs, list) or len(jobs) != record["totals"]["jobs_total"]:
            raise ValueError("Incomplete run jobs")
        job_ids = set()
        for job in jobs:
            if (not isinstance(job.get("id"), str) or not job["id"] or job["id"] in job_ids
                    or any(not finite(job.get(key)) for key in JobOutcome.__annotations__ if key not in ("id", "done_h"))
                    or "done_h" not in job or job["done_h"] is not None and not finite(job["done_h"])):
                raise ValueError("Duplicate or invalid job outcome")
            job_ids.add(job["id"])
        key = (record["version"], record["scenario"])
        if key in runs or record["_id"] in ids or record["version"] not in versions:
            raise ValueError("Duplicate or unlinked run")
        version_identity = versions[record["version"]].get("identity")
        if (record["scenario"] not in record["identity"]["scenario_ids"]
                or version_identity and version_identity["policy_sha256"] != record["identity"]["policy_sha256"]):
            raise ValueError("Run identity mismatch")
        runs[key] = record
        ids.add(record["_id"])
    repairs = [version for version in versions.values()
               if version["acceptance"] == "repair" and (version["_id"], SCENARIO) in runs]
    if not repairs:
        raise ValueError("No accepted repair with the required validation run")
    focus = replay.get("focus")
    repair = versions.get(focus["version"]) if focus else max(repairs, key=lambda version: (str(version["created_at"]), version["_id"]))
    if repair not in repairs:
        raise ValueError("Pinned repair is unavailable")
    candidate = runs[repair["_id"], SCENARIO]
    parent = runs.get((repair["parent"], SCENARIO))
    if not parent or not compatible(parent, candidate):
        raise ValueError("Matching parent run unavailable")
    baselines = [record for (version_id, scenario), record in runs.items()
                 if scenario == SCENARIO and versions[version_id]["author"] == "baseline"
                 and compatible(record, candidate)]
    if len(baselines) != 1:
        raise ValueError("One matching frozen baseline is required")
    if any(record["split"] != "validation" for record in (candidate, parent, baselines[0])):
        raise ValueError("Focus requires validation runs")
    before_jobs = {job["id"]: job for job in baselines[0]["jobs"]}
    after_jobs = {job["id"]: job for job in candidate["jobs"]}
    if (before_jobs.keys() != after_jobs.keys()
            or any(before_jobs[job_id][key] != after_jobs[job_id][key] for job_id in before_jobs
                   for key in ("arrive_h", "deadline_h", "work_kwh"))):
        raise ValueError("Selected job workloads differ")
    if focus and (focus["baseline"] != baselines[0]["version"] or focus["scenario"] != SCENARIO):
        raise ValueError("Pinned baseline is unavailable")
    replay["focus"] = {"baseline": baselines[0]["version"], "version": repair["_id"], "scenario": SCENARIO}
    return [baselines[0]["_id"], candidate["_id"]]


def validate_hours(replay, selected):
    scenario = next(record for record in replay["scenarios"] if record["id"] == SCENARIO)
    expected = scenario["arrival_days"] * 24 + scenario["tail_h"]
    runs = {record["_id"]: record for record in replay["runs"]}
    streams = {run_id: {} for run_id in selected}
    for hour in replay["hours"]:
        meta = hour["meta"]
        run_id = meta["run"]
        if (run_id not in streams or meta["scenario"] != SCENARIO
                or meta["version"] != runs[run_id]["version"]):
            raise ValueError("Hour metadata mismatch")
        if any(not finite(hour[key]) for key in HourRecord.__annotations__ if key not in ("ts", "event")):
            raise ValueError("Invalid numeric hour")
        if not isinstance(hour["ts"], (datetime, str)) or not isinstance(hour["event"], bool):
            raise ValueError("Invalid hourly input")
        if hour["h"] in streams[run_id]:
            raise ValueError("Duplicate hour")
        streams[run_id][hour["h"]] = hour
    if any(set(stream) != set(range(expected)) for stream in streams.values()):
        raise ValueError("Incomplete selected hours")
    before, after = (streams[run_id] for run_id in selected)
    for h in range(expected):
        if any(before[h][key] != after[h][key] for key in ("ts", "price", "inference_kw", "event", "safety_limit_kw")):
            raise ValueError("Operating inputs differ")
    replay["hours"].sort(key=lambda hour: (selected.index(hour["meta"]["run"]), hour["h"]))


def recorded():
    from flex.store import client

    replay = {"schema_version": 1, "source": "recorded evaluation replay",
              "generated_at": datetime.now(timezone.utc), "scenarios": dev() + validation()}
    replay.update(recorded_metadata())
    connection = client("reader")
    try:
        db = connection["flex"]
        def read(key, collection, query, attempts=None):
            projection = {field: 1 for field in FIELDS[key]}
            if "_id" not in FIELDS[key]:
                projection["_id"] = 0
            if attempts is not None:
                projection["attempt"] = 1
            records = list(db[collection].find(query, projection))
            if attempts is not None:
                attempts.update({record["_id"]: record["attempt"] for record in records})
            return [sanitize(key, record) for record in records]

        replay["versions"] = read("versions", "harness_versions", {})
        validate_lineage(replay)
        attempts = {}
        replay["runs"] = read("runs", "runs", {"split": {"$in": ["dev", "validation"]}}, attempts)
        selected = select_focus(replay)
        replay["hours"] = read("hours", "hours", {"meta.run": {"$in": selected}, "meta.scenario": SCENARIO,
                              "$or": [{"meta.run": run_id, "meta.attempt": attempts[run_id]} for run_id in selected]})
        replay["misses"] = read("misses", "misses", {"run": {"$in": selected}, "scenario": SCENARIO,
                               "$or": [{"run": run_id, "attempt": attempts[run_id]} for run_id in selected]})
        validate_hours(replay, selected)
    finally:
        connection.close()
    return replay


def sanitize(kind, record):
    from flex.contract import EvalIdentity, Policy, Totals, Verdict

    def pick(value, fields):
        return {key: value[key] for key in fields if key in value}

    record = pick(record, FIELDS[kind])
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
        verdict = record.get("verdict")
        record["acceptance"] = ("repair" if verdict["fixed"] else "cost") if verdict and verdict["accepted"] else None
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


def export(use_fixture=False, output=OUTPUT):
    replay = fixture() if use_fixture else recorded()
    payload = json.dumps(replay, default=serialize, separators=(",", ":"), allow_nan=False)
    check_credentials(json.loads(payload))
    output.parent.mkdir(parents=True, exist_ok=True)
    pending = output.parent.parent / ".replay.tmp"
    pending.write_text(payload + "\n")
    pending.replace(output)
    return replay


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args()
    try:
        replay = export(args.fixture)
        print(f"Exported {replay['source']}: {len(replay['versions'])} versions, "
              f"{len(replay['runs'])} runs, {len(replay['hours'])} hours to web/public/replay.json")
    except CredentialPatternError as error:
        print(f"Replay export failed: {error}", file=sys.stderr)
        sys.exit(1)
    except Exception as error:
        print(f"Replay export failed ({type(error).__name__}). Check the reader setup and source records.", file=sys.stderr)
        sys.exit(1)
