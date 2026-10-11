"""Atlas reads and writes for every lane. Each operation connects as the least-privileged user that can do it."""

import os
from functools import cache
from pathlib import Path
from typing import Literal
from uuid import uuid4

import certifi
from dotenv import load_dotenv
from pymongo import MongoClient

from flex.contract import DB, FINAL_DB, HarnessVersion, Miss, MissKind, Run, SimResult, Verdict
from flex.scenarios import dev

load_dotenv(Path(__file__).parent.parent / ".env")

Role = Literal["admin", "supervisor", "reader", "grader"]


@cache
def client(role: Role) -> MongoClient:
    if role == "admin":
        return MongoClient(os.environ["MONGODB_URI"], tlsCAFile=certifi.where(),
                           tlsCertificateKeyFile=os.path.expanduser(os.environ["MONGODB_CERT_PATH"]))
    return MongoClient(os.environ[f"MONGODB_{role.upper()}_URI"], tlsCAFile=certifi.where())


def save_version(v: HarnessVersion) -> None:
    client("supervisor")[DB].harness_versions.replace_one({"_id": v["_id"]}, v, upsert=True)


def save_run(run: Run, result: SimResult) -> str:
    """Writes the evidence under a fresh attempt id before the summary points at it, so a crash at any step
    leaves the previous complete result readable. Time-series writes can't join a transaction."""
    if any(m["run"] != run["_id"] for m in result["misses"]):
        raise ValueError(f"misses don't belong to run {run['_id']}")
    db = client("grader")[FINAL_DB] if run["split"] == "final" else client("supervisor")[DB]
    attempt = uuid4().hex
    meta = {"run": run["_id"], "version": run["version"], "scenario": run["scenario"], "attempt": attempt}
    if result["hours"]:
        db.hours.insert_many([{**h, "meta": meta} for h in result["hours"]])
    if result["misses"]:
        db.misses.insert_many([{**m, "attempt": attempt} for m in result["misses"]])
    db.runs.replace_one({"_id": run["_id"]},
                        {**run, "attempt": attempt, "diagnosis": result["diagnosis"], "jobs": result["jobs"]},
                        upsert=True)
    db.hours.delete_many({"meta.run": run["_id"], "meta.attempt": {"$ne": attempt}})
    db.misses.delete_many({"run": run["_id"], "attempt": {"$ne": attempt}})
    return attempt


def run_record(run_id: str, final: bool = False) -> dict | None:
    """The run summary with only the hours and misses of the attempt it points at."""
    db = client("grader")[FINAL_DB] if final else client("reader")[DB]
    run = db.runs.find_one({"_id": run_id})
    if not run:
        return None
    at = {"meta.run": run_id, "meta.attempt": run["attempt"]}
    return {"run": run, "hours": list(db.hours.find(at, {"_id": 0}).sort("ts", 1)),
            "misses": list(db.misses.find({"run": run_id, "attempt": run["attempt"]}, {"_id": 0}).sort("h", 1))}


def promote(version_id: str, verdict: Verdict) -> None:
    mc = client("supervisor")
    db = mc[DB]
    with mc.start_session() as s, s.start_transaction():
        old = db.champion.find_one({"_id": "champion"}, session=s)
        if old and old["version"] != version_id:
            db.harness_versions.update_one({"_id": old["version"]}, {"$set": {"status": "retired"}}, session=s)
        db.champion.replace_one({"_id": "champion"}, {"_id": "champion", "version": version_id}, upsert=True,
                                session=s)
        if not db.harness_versions.update_one({"_id": version_id}, {"$set": {"status": "champion", "verdict": verdict}},
                                              session=s).matched_count:
            raise KeyError(f"no harness version {version_id}")


def champion() -> HarnessVersion | None:
    db = client("reader")[DB]
    pointer = db.champion.find_one({"_id": "champion"})
    return pointer and db.harness_versions.find_one({"_id": pointer["version"]})


def versions() -> list[HarnessVersion]:
    return list(client("reader")[DB].harness_versions.find().sort("created_at", 1))


def recent_misses(kind: MissKind | None = None, k: int = 20) -> list[Miss]:
    query: dict = {"scenario": {"$in": [s["id"] for s in dev()]}}
    if kind:
        query["kind"] = kind
    return list(client("reader")[DB].misses.find(query, {"_id": 0}).sort("_id", -1).limit(k))
