"""The one frozen comparison on the final split. Run once after the freeze; the output never feeds another repair.

It pins every version that ever held the champion pointer (status champion or retired in Atlas), so the comparison
can't be chosen after seeing final results, plus the restart_aware and control policies as labeled references.
--exploratory reruns the pinned policies, recomputes their identity from the current code and scenarios, and writes
a separate file."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from flex import evaluate
from flex.contract import HarnessVersion, Scenario
from flex.scenarios import EVALUATOR_VERSION, final
from policies.control_repair import CONTROL_REPAIR
from policies.restart_aware import RESTART_AWARE

RESULTS = Path("results")
COLS = ("scenario", "version", "pass", "feasible", "late h", "unfinished kWh", "cap int", "train $")
REFERENCES = (("restart_aware", "baseline", RESTART_AWARE), ("control", "control", CONTROL_REPAIR))


def pin(versions: list[HarnessVersion], scenarios: list[Scenario]) -> list[dict]:
    lineage = sorted((v for v in versions if v["status"] in ("champion", "retired")), key=lambda v: v["created_at"])
    entries = [{"version": v["_id"], "author": v["author"], "acceptance": v.get("acceptance"), "role": "champion",
                "policy": v["policy"]} for v in lineage]
    entries += [{"version": vid, "author": author, "acceptance": None, "role": "reference", "policy": policy}
                for vid, author, policy in REFERENCES]
    return [{**e, "identity": evaluate.identity(e["policy"], scenarios)} for e in entries]


def _run(pinned: list[dict], scenarios: list[Scenario], save_run=None) -> tuple[dict, list]:
    out, rows = {}, []
    for p in pinned:
        vid = p["version"]
        results = evaluate.run(p["policy"], scenarios, vid)
        out[vid] = {**{k: p[k] for k in ("author", "acceptance", "role", "identity")}, "scenarios": {},
                    "training_cost": 0.0}
        for sc in scenarios:
            r, t = results[sc["id"]], results[sc["id"]]["totals"]
            ok, feas = evaluate.passes(t), evaluate.feasible(r)
            out[vid]["scenarios"][sc["id"]] = {"totals": t, "passes": ok, "feasible": feas}
            out[vid]["training_cost"] += t["training_energy_cost"]
            rows.append((sc["id"], vid, ok, feas, t["late_job_hours"], f"{t['unfinished_kwh']:,.0f}",
                         t["cap_interventions"], f"{t['training_energy_cost']:,.2f}"))
            if save_run:
                save_run({"_id": f"{vid}:{sc['id']}", "version": vid, "scenario": sc["id"], "split": "final",
                          "totals": t, "identity": p["identity"], "created_at": datetime.now(timezone.utc)}, r)
    return out, rows


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--exploratory", action="store_true")
    args = ap.parse_args(argv)
    manifest = RESULTS / "final_manifest.json"
    if manifest.exists() and not args.exploratory:
        print(f"refusing to run: {manifest} exists, so the final comparison already ran. "
              "Use --exploratory to rerun the pinned policies; that output must not feed another repair.")
        raise SystemExit(1)
    scenarios, now = final(), datetime.now(timezone.utc)
    if args.exploratory:
        if not manifest.exists():
            raise SystemExit(f"--exploratory needs {manifest}")
        pinned = [{**p, "identity": evaluate.identity(p["policy"], scenarios)}
                  for p in json.loads(manifest.read_text())["pinned"]]
        target, save_run = RESULTS / f"exploratory-{now.strftime('%Y%m%dT%H%M%SZ')}.json", None
        print("exploratory run: pinned policies from the manifest, nothing stored; it must not feed another repair")
    else:
        from flex import store
        pinned = pin(store.versions(), scenarios)
        assert any(p["role"] == "champion" for p in pinned), "no champion lineage in Atlas"
        RESULTS.mkdir(exist_ok=True)
        with open(manifest, "x") as f:
            json.dump({"evaluator_version": EVALUATOR_VERSION, "created_at": now.isoformat(), "pinned": pinned},
                      f, indent=1, default=str)
        target, save_run = RESULTS / "final.json", store.save_run
    print("pinned:", ", ".join(f"{p['version']} ({p['role']})" for p in pinned))
    out, rows = _run(pinned, scenarios, save_run)
    target.write_text(json.dumps(out, indent=1, default=str))
    widths = [max(len(str(x)) for x in col) for col in zip(COLS, *rows)]
    for row in (COLS, *rows):
        print("  ".join(str(x).ljust(w) if i < 2 else str(x).rjust(w) for i, (x, w) in enumerate(zip(row, widths))))
    for vid, o in out.items():
        print(f"{vid}: summed training cost ${o['training_cost']:,.2f}")


if __name__ == "__main__":
    main()
