"""Creates Flex's collections, validators, and indexes on Atlas. Safe to run any number of times."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import CollectionInvalid

from flex.contract import DB, FINAL_DB
from flex.store import client

STRINGS = {"bsonType": "array", "items": {"bsonType": "string"}}


def obj(required: list[str], **props) -> dict:
    return {"bsonType": "object", "required": required, "properties": props}


VERDICT = obj(["accepted", "reasons", "fixed", "regressed", "cost_delta_pct"], accepted={"bsonType": "bool"},
              reasons=STRINGS, fixed=STRINGS, regressed=STRINGS, cost_delta_pct={"bsonType": ["number", "null"]})
IDENTITY = obj(["evaluator_version", "manifest_sha256", "policy_sha256", "scenario_ids"],
               evaluator_version={"bsonType": "string"}, manifest_sha256={"bsonType": "string"},
               policy_sha256={"bsonType": "string"}, scenario_ids=STRINGS)
HARNESS_VERSION = obj(["_id", "parent", "policy", "rationale", "predicted", "author", "status", "created_at"],
                      _id={"bsonType": "string"}, parent={"bsonType": ["string", "null"]},
                      # flex.policy.validate owns the policy contract; a rejected malformed proposal must still store
                      policy={"bsonType": "object"},
                      rationale={"bsonType": "string"}, predicted={"bsonType": "string"},
                      author={"enum": ["baseline", "control", "supervisor"]},
                      status={"enum": ["candidate", "champion", "rejected", "retired"]},
                      verdict=VERDICT, identity=IDENTITY, created_at={"bsonType": "date"})


def ensure(db, name: str, **opts):
    try:
        db.create_collection(name, **opts)
        print(f"{db.name}.{name}: created")
    except CollectionInvalid:
        if "validator" in opts:
            db.command("collMod", name, validator=opts["validator"])
        print(f"{db.name}.{name}: exists")


def run_collections(db):
    ensure(db, "hours", timeseries={"timeField": "ts", "metaField": "meta", "granularity": "hours"})
    ensure(db, "runs")
    ensure(db, "misses")
    db.hours.create_index([("meta.run", ASCENDING), ("meta.attempt", ASCENDING), ("ts", ASCENDING)])
    db.runs.create_index([("version", ASCENDING), ("scenario", ASCENDING)])
    db.runs.create_index([("created_at", DESCENDING)])
    db.misses.create_index([("run", ASCENDING), ("attempt", ASCENDING), ("h", ASCENDING)])
    db.misses.create_index([("kind", ASCENDING), ("scenario", ASCENDING)])


def main():
    mc = client("admin")
    flex = mc[DB]
    run_collections(flex)
    run_collections(mc[FINAL_DB])
    ensure(flex, "harness_versions", validator={"$jsonSchema": HARNESS_VERSION})
    ensure(flex, "champion")
    flex.harness_versions.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
    flex.harness_versions.create_index([("parent", ASCENDING)])


if __name__ == "__main__":
    main()
