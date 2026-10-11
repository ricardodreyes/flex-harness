"""Stream harness changes from Atlas as they happen: uv run python -m flex.watch

Opens a change stream as the read-only reader user and prints one line per new or updated harness version and
per champion move, so a live evolve run is visible while it works.
"""

import argparse

from flex import store


def line(event: dict) -> str | None:
    doc = event.get("fullDocument") or {}
    coll = event["ns"]["coll"]
    if coll == "champion":
        return f"champion -> {doc.get('version')}"
    if not doc:
        return None
    if coll != "harness_versions":
        return f"{coll}: {doc.get('_id')}"
    verdict = doc.get("verdict") or {}
    label = doc.get("acceptance") or doc["status"]
    reasons = "; ".join(verdict.get("reasons", [])) or doc.get("rationale", "")[:100]
    return f"{doc['_id']:12s} {doc.get('author', ''):10s} {label:8s} {reasons}"


def watch(collections: tuple[str, ...], limit: int | None = None) -> None:
    db = store.client("reader")["flex"]
    pipeline = [{"$match": {"ns.coll": {"$in": list(collections)}, "operationType": {"$in": ["insert", "update", "replace"]}}}]
    seen = 0
    with db.watch(pipeline, full_document="updateLookup") as stream:
        print(f"watching flex.{', flex.'.join(collections)} (Ctrl+C to stop)", flush=True)
        for event in stream:
            text = line(event)
            if text:
                print(text, flush=True)
                seen += 1
                if limit and seen >= limit:
                    return


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--collections", nargs="+", default=["harness_versions", "champion"])
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    try:
        watch(tuple(args.collections), args.limit)
    except KeyboardInterrupt:
        pass
