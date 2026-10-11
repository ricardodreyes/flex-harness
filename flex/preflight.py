"""The feasibility prerequisite for the restart scenario, on dev scenarios only. Never touches final."""

import sys

from flex.evaluate import feasible, passes, run
from flex.scenarios import dev
from policies.control_repair import CONTROL_REPAIR
from policies.incumbent import INCUMBENT
from policies.restart_aware import RESTART_AWARE

POLICIES = {"incumbent": INCUMBENT, "control_repair": CONTROL_REPAIR, "restart_aware": RESTART_AWARE}
COLS = ("scenario", "policy", "jobs", "late h", "unfinished kWh", "restarts", "overhead kWh", "cap int", "train $")


def main():
    scenarios = dev()
    results = {name: run(policy, scenarios, name) for name, policy in POLICIES.items()}
    rows = []
    for sc in scenarios:
        for name in POLICIES:
            t = results[name][sc["id"]]["totals"]
            rows.append((sc["id"], name, f"{t['jobs_completed']}/{t['jobs_total']}", t["late_job_hours"],
                         f"{t['unfinished_kwh']:,.0f}", t["restarts"], f"{t['overhead_kwh']:,.0f}",
                         t["cap_interventions"], f"{t['training_energy_cost']:,.2f}"))
    widths = [max(len(str(x)) for x in col) for col in zip(COLS, *rows)]
    for row in (COLS, *rows):
        print("  ".join(str(x).ljust(w) if i < 2 else str(x).rjust(w) for i, (x, w) in enumerate(zip(row, widths))))
    print()
    for sc in scenarios:
        for name in POLICIES:
            r = results[name][sc["id"]]
            if not passes(r["totals"]) or not feasible(r):
                print(f"{sc['id']} / {name}: {r['diagnosis'][0]}")
    print()
    low = [s["id"] for s in scenarios if s["id"].endswith("-low")]
    high = [s["id"] for s in scenarios if s["id"].endswith("-high")]
    inc, rep, aware = results["incumbent"], results["control_repair"], results["restart_aware"]
    a = all(passes(inc[s]["totals"]) for s in low)
    high_fail = [s for s in high if not passes(inc[s]["totals"])]
    b = len(high_fail) >= 2 and all(any("starts" in d and "late" in d for d in inc[s]["diagnosis"]) for s in high_fail)
    c = bool(high_fail) and all(passes(rep[s]["totals"]) for s in high_fail)
    d = all(not feasible(results[p][s]) for p in POLICIES for s in ("dev-imp-11", "dev-cap-11"))
    for letter, ok, text in (("a", a, f"incumbent passes every dev-*-low"),
                             ("b", b, f"incumbent fails >= 2 of 3 dev-*-high with restart/warm-up diagnosis "
                                      f"(fails {high_fail})"),
                             ("c", c, f"control_repair passes the failing dev-*-high {high_fail}"),
                             ("d", d, "dev-imp-11 and dev-cap-11 reported infeasible for every policy")):
        print(f"({letter}) {'ok  ' if ok else 'FAIL'} {text}")
    ok = a and b and c and d
    print("PREREQUISITE", "PASS" if ok else "FAIL")
    print()

    def cost(res, ids):
        return sum(res[s]["totals"]["training_energy_cost"] for s in ids)

    for ids, label in ((low, "dev-*-low"), (high, "dev-*-high")):
        base = cost(inc, ids)
        print(f"{label}: incumbent ${base:,.2f}, control_repair ${cost(rep, ids):,.2f} "
              f"({(cost(rep, ids) - base) / base * 100:+.1f}%), restart_aware ${cost(aware, ids):,.2f} "
              f"({(cost(aware, ids) - base) / base * 100:+.1f}%)")
    for s in low + high:
        r, w = rep[s]["totals"]["training_energy_cost"], aware[s]["totals"]["training_energy_cost"]
        print(f"{s}: {'restart_aware' if w < r else 'control_repair'} cheaper by ${abs(w - r):,.2f}")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
