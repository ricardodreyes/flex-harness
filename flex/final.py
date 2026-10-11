"""The one frozen comparison on the final split. Run after the freeze; the output never feeds another repair."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from flex import evaluate
from flex.scenarios import EVALUATOR_VERSION, final, manifest_sha256
from policies.control_repair import CONTROL_REPAIR
from policies.incumbent import INCUMBENT
from policies.restart_aware import RESTART_AWARE

RESULTS = Path("results")
COLS = ("scenario", "policy", "pass", "feasible", "late h", "unfinished kWh", "cap int", "train $")


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if args.dry_run:
        from flex.evolve import JsonlStore
        store = JsonlStore()
    else:
        from flex import store
    champ = store.champion()
    assert champ, "no champion to compare"
    policies = {"incumbent": INCUMBENT, "champion": champ["policy"], "restart_aware": RESTART_AWARE,
                "control": CONTROL_REPAIR}
    scenarios = final()
    now = datetime.now(timezone.utc)
    suffix = ""
    if (RESULTS / "final.json").exists():
        suffix = "_exploratory_" + now.strftime("%Y%m%d%H%M%S")
        print("final.json already exists: this run is exploratory and must not feed another repair")
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"final_manifest{suffix}.json").write_text(json.dumps({
        "manifest_sha256": manifest_sha256(), "evaluator_version": EVALUATOR_VERSION, "champion": champ["_id"],
        "identities": {n: evaluate.identity(p, scenarios) for n, p in policies.items()},
        "created_at": now.isoformat()}, indent=1))
    out, rows = {}, []
    for name, policy in policies.items():
        results = evaluate.run(policy, scenarios, name)
        ident = evaluate.identity(policy, scenarios)
        out[name] = {"scenarios": {}, "training_cost": 0.0}
        for sc in scenarios:
            r, t = results[sc["id"]], results[sc["id"]]["totals"]
            ok, feas = evaluate.passes(t), evaluate.feasible(r)
            out[name]["scenarios"][sc["id"]] = {"totals": t, "passes": ok, "feasible": feas}
            out[name]["training_cost"] += t["training_energy_cost"]
            rows.append((sc["id"], name, ok, feas, t["late_job_hours"], f"{t['unfinished_kwh']:,.0f}",
                         t["cap_interventions"], f"{t['training_energy_cost']:,.2f}"))
            if not args.dry_run and not suffix:
                store.save_run({"_id": f"{name}:{sc['id']}", "version": name, "scenario": sc["id"], "split": "final",
                                "totals": t, "identity": ident, "created_at": now}, r)
    (RESULTS / f"final{suffix}.json").write_text(json.dumps(out, indent=1, default=str))
    widths = [max(len(str(x)) for x in col) for col in zip(COLS, *rows)]
    for row in (COLS, *rows):
        print("  ".join(str(x).ljust(w) if i < 2 else str(x).rjust(w) for i, (x, w) in enumerate(zip(row, widths))))
    for name, o in out.items():
        print(f"{name}: summed training cost ${o['training_cost']:,.2f}")


if __name__ == "__main__":
    main()
