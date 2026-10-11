import hashlib
import json

from flex.contract import COST_TOLERANCE, EvalIdentity, Policy, Scenario, SimResult, Totals, Verdict
from flex.policy import validate
from flex.scenarios import EVALUATOR_VERSION, manifest_sha256
from flex.sim import simulate
from flex.world import build_world, final_prices, prices


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


def accept(candidate_policy: Policy, champion_results: dict[str, SimResult],
           candidate_results: dict[str, SimResult]) -> Verdict:
    """The deterministic acceptance rule, applied in this order over the scenarios both were run on:

    1. An invalid candidate is rejected with its validation reasons.
    2. Any scenario the champion passes and the candidate fails is a regression: reject.
    3. Any scenario the champion fails that the candidate passes is a repair: accept, and report the training
       cost delta over every feasible scenario even when it is positive.
    4. Late job-hours improving on a failing scenario without passing it is partial progress: reject, say so.
    5. With an identical pass set, accept only when summed training cost is below champion x (1 - COST_TOLERANCE);
       otherwise reject as within tolerance.
    Infeasible scenarios (an infeasible hour, or a capacity-impossible job) are excluded and listed.
    """
    reasons = validate(candidate_policy)
    if reasons:
        return {"accepted": False, "reasons": ["invalid policy"] + reasons, "fixed": [], "regressed": [],
                "cost_delta_pct": None}
    ids = [s for s in champion_results if s in candidate_results]
    excluded = [s for s in ids if not feasible(champion_results[s]) or not feasible(candidate_results[s])]
    ids = [s for s in ids if s not in excluded]
    notes = [f"infeasible scenario {s}, excluded" for s in excluded]
    champ = {s: champion_results[s]["totals"] for s in ids}
    cand = {s: candidate_results[s]["totals"] for s in ids}
    regressed = [s for s in ids if passes(champ[s]) and not passes(cand[s])]
    fixed = [s for s in ids if not passes(champ[s]) and passes(cand[s])]
    champ_cost = sum(t["training_energy_cost"] for t in champ.values())
    cand_cost = sum(t["training_energy_cost"] for t in cand.values())
    delta = (cand_cost - champ_cost) / champ_cost * 100 if champ_cost else None
    delta_s = f"{delta:+.2f}%" if delta is not None else "n/a"

    def verdict(accepted: bool, *why: str) -> Verdict:
        return {"accepted": accepted, "reasons": [*why, *notes], "fixed": fixed, "regressed": regressed,
                "cost_delta_pct": delta}

    if regressed:
        return verdict(False, *[f"regression on {s}" for s in regressed])
    if fixed:
        return verdict(True, *[f"repaired {s}" for s in fixed],
                       f"costs {delta_s} training energy to restore deadlines" if delta is not None and delta > 0
                       else f"training energy {delta_s}")
    partial = [s for s in ids if not passes(cand[s]) and cand[s]["late_job_hours"] < champ[s]["late_job_hours"]]
    if partial:
        return verdict(False, *[f"partial progress on {s}: late job-hours {champ[s]['late_job_hours']} -> "
                                f"{cand[s]['late_job_hours']}, still failing" for s in partial])
    if cand_cost < champ_cost * (1 - COST_TOLERANCE):
        return verdict(True, f"same pass set, training energy {delta_s}")
    return verdict(False, f"within tolerance: training energy {delta_s}, needs below -{COST_TOLERANCE:.0%}")


def policy_sha256(policy: Policy) -> str:
    return hashlib.sha256(json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def identity(policy: Policy, scenarios: list[Scenario]) -> EvalIdentity:
    return {"evaluator_version": EVALUATOR_VERSION, "manifest_sha256": manifest_sha256(),
            "policy_sha256": policy_sha256(policy), "scenario_ids": [s["id"] for s in scenarios]}
