"""Proves the store against the real Atlas sandbox. Leaves no check-* documents and restores the champion."""

import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo.collection import Collection
from pymongo.errors import OperationFailure

from flex import evaluate, store
from flex.contract import DB, FINAL_DB, HarnessVersion, Run, SimResult, Verdict
from flex.scenarios import by_id
from policies.control_repair import CONTROL_REPAIR
from policies.incumbent import INCUMBENT

PREFIX = {"$regex": "^check-"}
VERDICT: Verdict = {"accepted": True, "reasons": ["check"], "fixed": [], "regressed": [], "cost_delta_pct": 0.0}
failed = []


class Injected(Exception):
    pass


def check(ok: bool, what: str):
    print(f"{'PASS' if ok else 'FAIL'}  {what}")
    if not ok:
        failed.append(what)


def error_code(op) -> int | None:
    try:
        op()
    except OperationFailure as e:
        return e.code
    return None


@contextmanager
def fail_on(method: str):
    orig = getattr(Collection, method)

    def boom(self, *a, **k):
        raise Injected(f"{method} on {self.name}")

    setattr(Collection, method, boom)
    try:
        yield
    finally:
        setattr(Collection, method, orig)


def version(vid: str, **over) -> HarnessVersion:
    return {"_id": vid, "parent": None, "policy": INCUMBENT, "rationale": "check", "predicted": "check",
            "author": "baseline", "status": "candidate", "created_at": datetime.now(timezone.utc), **over}


def run_for(rid: str, split: str, result: SimResult) -> Run:
    sc = by_id("dev-12-high")
    return {"_id": rid, "version": "check-a", "scenario": sc["id"], "split": split, "totals": result["totals"],
            "identity": evaluate.identity(INCUMBENT, [sc]), "created_at": datetime.now(timezone.utc)}


def matches(rec: dict | None, result: SimResult) -> bool:
    return (rec is not None and rec["run"]["totals"] == result["totals"]
            and len(rec["hours"]) == len(result["hours"]) and len(rec["misses"]) == len(result["misses"]))


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
        store.save_version(version("check-a"))
        got = next((v for v in store.versions() if v["_id"] == "check-a"), None)
        check(got is not None and got["policy"] == INCUMBENT and got["author"] == "baseline",
              "version round-trips through save_version and versions()")
        bad_policy = {"rules": "not a list", "default_power": "max", "extra": 1}
        store.save_version(version("check-bad", policy=bad_policy, author="supervisor", status="rejected",
                                   verdict={**VERDICT, "accepted": False, "reasons": ["invalid policy"]}))
        check(flex.harness_versions.find_one({"_id": "check-bad"})["policy"] == bad_policy,
              "a rejected proposal with a malformed policy is stored as-is")
        code = error_code(lambda: store.save_version(version("check-bogus", status="bogus")))
        check(code == 121, f"the envelope stays strict: status 'bogus' fails validation with code {code}")

        sc = by_id("dev-12-high")
        rid = "check-a:dev-12-high"
        first = evaluate.run(INCUMBENT, [sc], "check-a")[sc["id"]]
        second = evaluate.run(CONTROL_REPAIR, [sc], "check-a")[sc["id"]]
        check(first["totals"] != second["totals"] and len(first["misses"]) != len(second["misses"]),
              f"two distinct results for {rid}: {len(first['misses'])} vs {len(second['misses'])} misses")

        store.save_run(run_for(rid, "dev", first), first)
        check(matches(store.run_record(rid), first),
              f"run round-trips: totals, {len(first['hours'])} hours, {len(first['misses'])} misses")

        try:
            with fail_on("replace_one"):
                store.save_run(run_for(rid, "dev", second), second)
            check(False, "injected failure before the summary write raises")
        except Injected as e:
            print(f"      injected failure after the evidence inserts: {e}")
        check(matches(store.run_record(rid), first),
              "after a failure before the summary write, the previous complete result is still what reads back")

        try:
            with fail_on("delete_many"):
                store.save_run(run_for(rid, "dev", second), second)
            check(False, "injected failure before the cleanup raises")
        except Injected as e:
            print(f"      injected failure after the summary write: {e}")
        stale = flex.hours.count_documents({"meta.run": rid})
        check(matches(store.run_record(rid), second) and stale > len(second["hours"]),
              f"after a failure before cleanup, the new complete result reads back despite {stale} stored hours")

        store.save_run(run_for(rid, "dev", second), second)
        check(flex.hours.count_documents({"meta.run": rid}) == len(second["hours"])
              and flex.misses.count_documents({"run": rid}) == len(second["misses"]),
              "the next clean save deletes every older attempt")

        try:
            store.save_run(run_for("check-mismatch", "dev", first), first)
            check(False, "save_run rejects misses that belong to another run")
        except ValueError as e:
            check(flex.runs.count_documents({"_id": "check-mismatch"}) == 0,
                  f"save_run rejects misses for another run and writes nothing: {e}")

        fid = "check-a:final"
        final = {**first, "misses": [{**m, "run": fid} for m in first["misses"]]}
        store.save_run(run_for(fid, "final", final), final)
        check(matches(store.run_record(fid, final=True), final) and len(final["misses"]) > 0
              and flex.runs.count_documents({"_id": fid}) == 0,
              f"a final-split run and its {len(final['misses'])} misses land in flex_final through grader, not flex")

        store.save_version(version("check-b"))
        store.promote("check-a", VERDICT)
        check(store.champion()["_id"] == "check-a", "promote check-a makes it champion")
        try:
            store.promote("check-missing", VERDICT)
            check(False, "promote of a missing version raises inside the transaction")
        except KeyError as e:
            print(f"      injected failure after the retire and pointer writes: {e}")
        check(flex.champion.find_one({"_id": "champion"})["version"] == "check-a",
              "after the injected failure the champion pointer is still check-a")
        check(flex.harness_versions.find_one({"_id": "check-a"})["status"] == "champion",
              "after the injected failure check-a is still status champion, the retire rolled back")
        store.promote("check-b", VERDICT)
        statuses = {v["_id"]: v["status"] for v in flex.harness_versions.find({"_id": {"$in": ["check-a", "check-b"]}})}
        check(store.champion()["_id"] == "check-b" and statuses == {"check-a": "retired", "check-b": "champion"},
              f"promote check-b retires check-a and moves the pointer: {statuses}")

        code = error_code(lambda: store.client("reader")[DB].runs.insert_one({"_id": "check-reader"}))
        check(code == 13, f"reader can't write flex.runs: code {code}")
        code = error_code(lambda: store.client("supervisor")[FINAL_DB].runs.find_one())
        check(code == 13, f"supervisor can't read flex_final.runs: code {code}")
        code = error_code(lambda: store.client("grader")[DB].runs.insert_one({"_id": "check-grader"}))
        check(code == 13, f"grader can't write flex.runs: code {code}")
    finally:
        cleanup(admin)
        if pointer:
            flex.champion.replace_one({"_id": "champion"}, pointer)
        else:
            flex.champion.delete_one({"_id": "champion"})
        if prior:
            flex.harness_versions.update_one({"_id": prior["_id"]}, {"$set": {"status": prior["status"]}})
    print(f"\n{'ALL PASS' if not failed else f'{len(failed)} FAILED'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
