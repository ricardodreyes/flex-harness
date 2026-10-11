"""Propose, validate, score on validation, accept or reject, promote. Never loads final scenarios."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from flex import evaluate, supervisor, telemetry
from flex.contract import HarnessVersion, Run, SimResult, Verdict
from flex.policy import validate
from flex.scenarios import dev, validation
from policies.incumbent import INCUMBENT


class JsonlStore:
    """flex.store's interface over local files, for --dry-run and tests."""

    def __init__(self, root: Path = Path("results/dev")):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def _read(self, name: str) -> list[dict]:
        p = self.root / name
        return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []

    def _write(self, name: str, rows: list[dict]):
        (self.root / name).write_text("".join(json.dumps(r, default=str) + "\n" for r in rows))

    def save_version(self, v: HarnessVersion):
        self._write("versions.jsonl", [r for r in self._read("versions.jsonl") if r["_id"] != v["_id"]] + [v])

    def save_run(self, run: Run, result: SimResult):
        if any(m["run"] != run["_id"] for m in result["misses"]):
            raise ValueError(f"misses don't belong to run {run['_id']}")
        self._write("runs.jsonl", [r for r in self._read("runs.jsonl") if r["_id"] != run["_id"]]
                    + [{**run, "diagnosis": result["diagnosis"], "jobs": result["jobs"]}])
        self._write("misses.jsonl", [r for r in self._read("misses.jsonl") if r["run"] != run["_id"]]
                    + [dict(m) for m in result["misses"]])

    def promote(self, version_id: str, verdict: Verdict):
        rows = self._read("versions.jsonl")
        assert any(r["_id"] == version_id for r in rows), f"no harness version {version_id}"
        for r in rows:
            if r["status"] == "champion":
                r["status"] = "retired"
            if r["_id"] == version_id:
                r["status"], r["verdict"] = "champion", verdict
        self._write("versions.jsonl", rows)
        (self.root / "champion.json").write_text(json.dumps({"version": version_id}))

    def champion(self) -> HarnessVersion | None:
        p = self.root / "champion.json"
        if not p.exists():
            return None
        vid = json.loads(p.read_text())["version"]
        return next(r for r in self._read("versions.jsonl") if r["_id"] == vid)

    def versions(self) -> list[HarnessVersion]:
        return sorted(self._read("versions.jsonl"), key=lambda r: r["created_at"])

    def recent_misses(self, kind: str | None = None, k: int = 20) -> list[dict]:
        ids = {s["id"] for s in dev()}
        rows = reversed(self._read("misses.jsonl"))
        return [m for m in rows if m["scenario"] in ids and kind in (None, m["kind"])][:k]


def _score(store, version_id: str, policy: dict, scenarios: list[dict]) -> dict[str, SimResult]:
    results = evaluate.run(policy, scenarios, version_id)
    ident = evaluate.identity(policy, scenarios)
    for sc in scenarios:
        run: Run = {"_id": f"{version_id}:{sc['id']}", "version": version_id, "scenario": sc["id"],
                    "split": sc["split"], "totals": results[sc["id"]]["totals"], "identity": ident,
                    "created_at": datetime.now(timezone.utc)}
        store.save_run(run, results[sc["id"]])
    return results


def _late_misses(results: dict[str, SimResult], k: int = 20) -> list:
    # store.recent_misses(kind="late") is all dev-imp-11, whose misses no policy can fix
    return [m for r in results.values() if evaluate.feasible(r) for m in r["misses"] if m["kind"] == "late"][:k]


def evolve(store, gens: int):
    if store.champion() is None:
        store.save_version({"_id": "v0", "parent": None, "policy": INCUMBENT,
                            "rationale": "frozen incumbent, tuned on dev-*-low", "predicted": "",
                            "author": "baseline", "status": "candidate", "created_at": datetime.now(timezone.utc)})
        store.promote("v0", {"accepted": True, "reasons": ["seed: frozen incumbent"], "fixed": [], "regressed": [],
                             "cost_delta_pct": None})
    scored, champ_dev, champ_val = None, {}, {}
    for gen in range(1, gens + 1):
        champ = store.champion()
        if scored != champ["_id"]:
            champ_dev = _score(store, champ["_id"], champ["policy"], dev())
            champ_val = _score(store, champ["_id"], champ["policy"], validation())
            scored = champ["_id"]
        rejected = [v for v in store.versions() if v["status"] == "rejected"][-5:]
        try:
            p = supervisor.propose(champ, champ_dev, _late_misses(champ_dev), rejected)
        except Exception as e:
            print(f"g{gen}: proposal failed, {type(e).__name__}")
            continue
        vid = f"g{gen}-{uuid4().hex[:6]}"
        if p["error"]:
            verdict = {"accepted": False, "reasons": [f"unparseable proposal: {p['error']}"], "fixed": [],
                       "regressed": [], "cost_delta_pct": None}
        elif validate(p["policy"]):
            verdict = evaluate.accept(p["policy"], champ_val, {})
        else:
            verdict = evaluate.accept(p["policy"], champ_val, _score(store, vid, p["policy"], validation()))
        acceptance = ("repair" if verdict["fixed"] else "cost") if verdict["accepted"] else None
        store.save_version({"_id": vid, "parent": champ["_id"], "policy": p["policy"], "rationale": p["rationale"],
                            "predicted": p["predicted"], "author": "supervisor", "verdict": verdict,
                            "identity": evaluate.identity(p["policy"], validation()),
                            "status": "candidate" if verdict["accepted"] else "rejected",
                            **({"acceptance": acceptance} if acceptance else {}),
                            "created_at": datetime.now(timezone.utc)})
        if verdict["accepted"]:
            store.promote(vid, verdict)
        telemetry.record(p, verdict, vid, acceptance)
        cost = verdict["cost_delta_pct"]
        print(f"{vid} {f'ACCEPT {acceptance}' if acceptance else 'REJECT'} {'; '.join(verdict['reasons'])} | cost "
              f"{f'{cost:+.2f}%' if cost is not None else 'n/a'} | predicted: {p['predicted']}\n    {p['rationale']}")


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--gens", type=int, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if args.dry_run:
        store = JsonlStore()
    else:
        from flex import store
    evolve(store, args.gens)
    telemetry.flush()


if __name__ == "__main__":
    main()
