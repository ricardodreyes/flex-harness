"""The one frozen comparison on the final split. Run once after the freeze; the output never feeds another repair.
--exploratory reruns the policies pinned in the manifest and writes a separate file."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from flex import evaluate
from flex.scenarios import EVALUATOR_VERSION, final
from policies.control_repair import CONTROL_REPAIR
from policies.incumbent import INCUMBENT
from policies.restart_aware import RESTART_AWARE

RESULTS = Path("results")
COLS = ("scenario", "policy", "pass", "feasible", "late h", "unfinished kWh", "cap int", "train $")


def _run(pinned: dict, scenarios: list[dict], save_run=None) -> tuple[dict, list]:
    out, rows = {}, []
    for name, p in pinned.items():
        results = evaluate.run(p["policy"], scenarios, p["version"])
        out[name] = {"version": p["version"], "identity": p["identity"], "scenarios": {}, "training_cost": 0.0}
        for sc in scenarios:
            r, t = results[sc["id"]], results[sc["id"]]["totals"]
            ok, feas = evaluate.passes(t), evaluate.feasible(r)
            out[name]["scenarios"][sc["id"]] = {"totals": t, "passes": ok, "feasible": feas}
            out[name]["training_cost"] += t["training_energy_cost"]
            rows.append((sc["id"], name, ok, feas, t["late_job_hours"], f"{t['unfinished_kwh']:,.0f}",
                         t["cap_interventions"], f"{t['training_energy_cost']:,.2f}"))
            if save_run:
                save_run({"_id": f"{p['version']}:{sc['id']}", "version": p["version"], "scenario": sc["id"],
                          "split": "final", "totals": t, "identity": p["identity"],
                          "created_at": datetime.now(timezone.utc)}, r)
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
        pinned = json.loads(manifest.read_text())["policies"]
        target, save_run = RESULTS / f"exploratory-{now.strftime('%Y%m%dT%H%M%SZ')}.json", None
        print("exploratory run: pinned policies from the manifest, nothing stored; it must not feed another repair")
    else:
        from flex import store
        champ = store.champion()
        assert champ, "no champion to compare"
        named = (("incumbent", "incumbent", INCUMBENT), ("champion", champ["_id"], champ["policy"]),
                 ("restart_aware", "restart_aware", RESTART_AWARE), ("control", "control", CONTROL_REPAIR))
        pinned = {n: {"version": v, "policy": p, "identity": evaluate.identity(p, scenarios)} for n, v, p in named}
        RESULTS.mkdir(exist_ok=True)
        with open(manifest, "x") as f:
            json.dump({"evaluator_version": EVALUATOR_VERSION, "created_at": now.isoformat(), "policies": pinned},
                      f, indent=1)
        target, save_run = RESULTS / "final.json", store.save_run
    out, rows = _run(pinned, scenarios, save_run)
    target.write_text(json.dumps(out, indent=1, default=str))
    widths = [max(len(str(x)) for x in col) for col in zip(COLS, *rows)]
    for row in (COLS, *rows):
        print("  ".join(str(x).ljust(w) if i < 2 else str(x).rjust(w) for i, (x, w) in enumerate(zip(row, widths))))
    for name, o in out.items():
        print(f"{name}: summed training cost ${o['training_cost']:,.2f}")


if __name__ == "__main__":
    main()
