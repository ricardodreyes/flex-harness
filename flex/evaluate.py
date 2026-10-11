import hashlib
import json

from flex.contract import COST_TOLERANCE, EvalIdentity, Policy, Scenario, SimResult, Totals, Verdict
from flex.policy import validate
from flex.scenarios import EVALUATOR_VERSION
from flex.sim import simulate
from flex.world import FINAL_PRICES, PRICES, build_world, final_prices, prices


def run(policy: Policy, scenarios: list[Scenario], version_id: str) -> dict[str, SimResult]:
    out = {}
    for sc in scenarios:
        hours = sc["arrival_days"] * 24 + sc["tail_h"]
        load = final_prices if sc["split"] == "final" else prices
        out[sc["id"]] = simulate(build_world(sc, load(sc["start"], hours)), policy, f"{version_id}:{sc['id']}",
                                 version_id)
    return out


def passes(totals: Totals) -> bool:
    return totals["late_job_hours"] == 0 and totals["unfinished_kwh"] == 0 and totals["cap_interventions"] == 0


def feasible(result: SimResult) -> bool:
    """A scenario with an infeasible hour or a capacity-impossible job is outside pass/fail for every policy."""
    return result["totals"]["infeasible_hours"] == 0 and not any("impossible for any policy" in d
                                                                 for d in result["diagnosis"])


RELIABILITY = (("late_job_hours", 1), ("unfinished_kwh", 1), ("cap_interventions", 1), ("jobs_completed", -1))


def _delta_pct(champ_cost: float, cand_cost: float) -> float | None:
    return (cand_cost - champ_cost) / abs(champ_cost) * 100 if champ_cost else None


def accept(candidate_policy: Policy, champion_results: dict[str, SimResult],
           candidate_results: dict[str, SimResult]) -> Verdict:
    """The deterministic acceptance rule, applied in this order:

    1. An invalid candidate is rejected with its validation reasons.
    2. The candidate must have been run on exactly the champion's scenarios; otherwise reject as incomplete.
    3. On every feasible scenario the candidate may not have more late job-hours, more unfinished work, more cap
       interventions, or fewer completed jobs than the champion: reject as a regression. This covers losing a
       pass and abandoning work.
    4. Any scenario the champion fails that the candidate passes is a repair: accept, and report the training
       cost delta over every feasible scenario even when it is positive.
    5. Late job-hours improving on a failing scenario without passing it is partial progress: reject, say so.
    6. Otherwise no scenario got worse and none was repaired. Accept only when summed training cost is below
       champion - COST_TOLERANCE x |champion|; a zero champion cost accepts only a negative candidate cost.
    Infeasible scenarios (an infeasible hour, or a capacity-impossible job) are excluded and listed.
    """
    reasons = validate(candidate_policy)
    if reasons:
        return {"accepted": False, "reasons": ["invalid policy"] + reasons, "fixed": [], "regressed": [],
                "cost_delta_pct": None}
    missing = sorted(set(champion_results) ^ set(candidate_results))
    if missing:
        return {"accepted": False, "reasons": [f"incomplete evaluation: missing {', '.join(missing)}"], "fixed": [],
                "regressed": [], "cost_delta_pct": None}
    ids = list(champion_results)
    excluded = [s for s in ids if not feasible(champion_results[s]) or not feasible(candidate_results[s])]
    ids = [s for s in ids if s not in excluded]
    notes = [f"infeasible scenario {s}, excluded" for s in excluded]
    champ = {s: champion_results[s]["totals"] for s in ids}
    cand = {s: candidate_results[s]["totals"] for s in ids}
    worse = {s: [f"{k} {champ[s][k]:g} -> {cand[s][k]:g}" for k, sign in RELIABILITY
                 if sign * cand[s][k] > sign * champ[s][k]] for s in ids}
    regressed = [s for s in ids if worse[s]]
    fixed = [s for s in ids if not passes(champ[s]) and passes(cand[s])]
    champ_cost = sum(t["training_energy_cost"] for t in champ.values())
    cand_cost = sum(t["training_energy_cost"] for t in cand.values())
    delta = _delta_pct(champ_cost, cand_cost)
    delta_s = f"{delta:+.2f}%" if delta is not None else "n/a"

    def verdict(accepted: bool, *why: str) -> Verdict:
        return {"accepted": accepted, "reasons": [*why, *notes], "fixed": fixed, "regressed": regressed,
                "cost_delta_pct": delta}

    if regressed:
        return verdict(False, *[f"regression on {s}: {', '.join(worse[s])}" for s in regressed])
    if fixed:
        return verdict(True, f"repairs {', '.join(fixed)}; training energy {delta_s}"
                       + (" to restore deadlines" if delta is not None and delta > 0 else ""))
    partial = [s for s in ids if not passes(cand[s]) and cand[s]["late_job_hours"] < champ[s]["late_job_hours"]]
    if partial:
        return verdict(False, *[f"partial: {s} late job-hours {champ[s]['late_job_hours']} -> "
                                f"{cand[s]['late_job_hours']}, still failing" for s in partial])
    if cand_cost < champ_cost - COST_TOLERANCE * abs(champ_cost):
        return verdict(True, f"cheaper: training energy {delta_s}")
    if delta is None or delta >= 0:
        return verdict(False, f"not cheaper: training energy {delta_s}")
    return verdict(False, f"within tolerance: {delta_s}, needs below -{COST_TOLERANCE:.0%}")


def policy_sha256(policy: Policy) -> str:
    return hashlib.sha256(json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def identity(policy: Policy, scenarios: list[Scenario]) -> EvalIdentity:
    """Hashes the supplied scenario definitions, the evaluator version, and only the price files their splits
    read, so dev and validation identities never touch the final prices."""
    h = hashlib.sha256(json.dumps(scenarios, sort_keys=True, separators=(",", ":")).encode())
    for path in sorted({FINAL_PRICES if s["split"] == "final" else PRICES for s in scenarios}):
        h.update(hashlib.sha256(path.read_bytes()).hexdigest().encode())
    h.update(EVALUATOR_VERSION.encode())
    return {"evaluator_version": EVALUATOR_VERSION, "manifest_sha256": h.hexdigest(),
            "policy_sha256": policy_sha256(policy), "scenario_ids": [s["id"] for s in scenarios]}
