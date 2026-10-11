"""Proves the store against the real Atlas sandbox. Leaves no check-* documents and restores the champion."""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo.errors import OperationFailure

from flex import evaluate, store
from flex.contract import DB, FINAL_DB, HarnessVersion, Run, Verdict
from flex.scenarios import by_id
from policies.incumbent import INCUMBENT

PREFIX = {"$regex": "^check-"}
VERDICT: Verdict = {"accepted": True, "reasons": ["check"], "fixed": [], "regressed": [], "cost_delta_pct": 0.0}
failed = []


def check(ok: bool, what: str):
    print(f"{'PASS' if ok else 'FAIL'}  {what}")
    if not ok:
        failed.append(what)


def denied(op) -> str | None:
    try:
        op()
    except OperationFailure as e:
        return f"code {e.code} {e.details.get('codeName')}"
    return None


def version(vid: str) -> HarnessVersion:
    return {"_id": vid, "parent": None, "policy": INCUMBENT, "rationale": "check", "predicted": "check",
            "author": "baseline", "status": "candidate", "created_at": datetime.now(timezone.utc)}


def cleanup(admin):
    for db in (admin[DB], admin[FINAL_DB]):
        db.runs.delete_many({"_id": PREFIX})
        db.hours.delete_many({"meta.run": PREFIX})
        db.misses.delete_many({"run": PREFIX})
    admin[DB].harness_versions.delete_many({"_id": PREFIX})


def main():
    admin = store.client("admin")
    flex = admin[DB]
    pointer = flex.champion.find_one({"_id": "champion"})
    prior = pointer and flex.harness_versions.find_one({"_id": pointer["version"]}, {"status": 1})
    cleanup(admin)
    try:
        sc = by_id("dev-12-high")
        result = evaluate.run(INCUMBENT, [sc], "check-a")[sc["id"]]
        store.save_version(version("check-a"))
        got = next((v for v in store.versions() if v["_id"] == "check-a"), None)
        check(got is not None and got["policy"] == INCUMBENT and got["author"] == "baseline",
              "version round-trips through save_version and versions()")

        run: Run = {"_id": "check-a:dev-12-high", "version": "check-a", "scenario": sc["id"], "split": "dev",
                    "totals": result["totals"], "identity": evaluate.identity(INCUMBENT, [sc]),
                    "created_at": datetime.now(timezone.utc)}
        store.save_run(run, result)
        store.save_run(run, result)
        reader = store.client("reader")[DB]
        doc = reader.runs.find_one({"_id": run["_id"]})
        hours = reader.hours.count_documents({"meta.run": run["_id"]})
        misses = reader.misses.count_documents({"run": run["_id"]})
        check(doc is not None and doc["totals"] == result["totals"] and doc["identity"] == run["identity"],
              f"run round-trips: totals and identity equal, training cost ${doc and doc['totals']['training_energy_cost']:.2f}")
        check(hours == len(result["hours"]) and misses == len(result["misses"]),
              f"saving the run twice leaves {hours} hours and {misses} misses, sim produced "
              f"{len(result['hours'])} and {len(result['misses'])}")

        store.save_run({**run, "_id": "check-a:final", "split": "final"}, result)
        check(admin[FINAL_DB].runs.count_documents({"_id": "check-a:final"}) == 1
              and flex.runs.count_documents({"_id": "check-a:final"}) == 0,
              "a final-split run lands in flex_final through grader, not in flex")

        store.save_version(version("check-b"))
        store.promote("check-a", VERDICT)
        check(store.champion()["_id"] == "check-a", "promote check-a makes it champion")

        try:
            store.promote("check-missing", VERDICT)
            check(False, "promote of a missing version raises inside the transaction")
        except KeyError as e:
            print(f"      injected failure after demote and pointer writes: {e}")
        check(flex.champion.find_one({"_id": "champion"})["version"] == "check-a",
              "after the injected failure the champion pointer is still check-a")
        check(flex.harness_versions.find_one({"_id": "check-a"})["status"] == "champion",
              "after the injected failure check-a is still status champion, the demote rolled back")

        store.promote("check-b", VERDICT)
        statuses = {v["_id"]: v["status"] for v in flex.harness_versions.find({"_id": PREFIX})}
        check(store.champion()["_id"] == "check-b" and statuses == {"check-a": "candidate", "check-b": "champion"},
              f"promote check-b flips both statuses and the pointer: {statuses}")

        err = denied(lambda: store.client("reader")[DB].runs.insert_one({"_id": "check-reader"}))
        check(err is not None, f"reader can't write flex.runs: {err}")
        err = denied(lambda: store.client("supervisor")[FINAL_DB].runs.find_one())
        check(err is not None, f"supervisor can't read flex_final.runs: {err}")
        err = denied(lambda: store.client("grader")[DB].runs.insert_one({"_id": "check-grader"}))
        check(err is not None, f"grader can't write flex.runs: {err}")
    finally:
        cleanup(admin)
        if pointer:
            flex.champion.replace_one({"_id": "champion"}, pointer)
        if prior:
            flex.harness_versions.update_one({"_id": prior["_id"]}, {"$set": {"status": prior["status"]}})
        if not pointer:
            flex.champion.delete_one({"_id": "champion"})
    print(f"\n{'ALL PASS' if not failed else f'{len(failed)} FAILED'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
