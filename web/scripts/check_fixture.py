import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from flex.evaluate import accept
from web.scripts.export_replay import sanitize

replay = json.loads((Path(__file__).resolve().parents[1] / "public/replay.json").read_text())
versions = {version["_id"]: version for version in replay["versions"]}
runs = {run["_id"]: run for run in replay["runs"]}
scenarios = {scenario["id"]: scenario for scenario in replay["scenarios"]}
assert replay["source"] == "fixture", "The simulator check needs a generated fixture."
assert all(run["split"] in ("dev", "validation") for run in runs.values()), "Final runs must stay outside this fixture."
for run in runs.values():
    totals = run["totals"]
    hours = [hour for hour in replay["hours"] if hour["meta"]["run"] == run["_id"]]
    scenario = scenarios[run["scenario"]]
    assert len(hours) == scenario["arrival_days"] * 24 + scenario["tail_h"], "Every scenario hour must survive the export."
    assert len(run["jobs"]) == totals["jobs_total"], "Every simulated job must survive the export."
    assert abs(sum(hour["productive_kw"] for hour in hours) - totals["productive_kwh"]) < 0.01
    assert abs(sum(hour["overhead_kw"] for hour in hours) - totals["overhead_kwh"]) < 0.01
    for hour in hours:
        assert hour["executed_kw"] <= min(hour["requested_kw"], hour["safety_limit_kw"]) + 1e-7
        assert abs(hour["executed_kw"] - hour["productive_kw"] - hour["overhead_kw"]) < 1e-7
for version in versions.values():
    if version["parent"] is None:
        continue
    def results(version_id):
        return {run["scenario"]: {"totals": run["totals"], "diagnosis": run["diagnosis"]}
                for run in runs.values() if run["version"] == version_id and run["split"] == "validation"}
    assert accept(version["policy"], results(version["parent"]), results(version["_id"])) == version["verdict"], "Fixture verdict must match validation-only evaluation."
invalid = sanitize("versions", {"policy": {"rules": [None, {"when": [None], "secret": "remove"}]},
                                "verdict": {"accepted": False, "reasons": ["invalid policy"]}})
assert invalid["policy"]["rules"][0] is None
assert "secret" not in invalid["policy"]["rules"][1]
print(f"Fixture physics and validation verdicts verified for {len(runs)} runs, {len(replay['hours'])} hours.")
