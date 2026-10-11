"""Stream harness changes from Atlas as they happen: uv run python -m flex.watch

Opens a change stream as the read-only reader user and prints one line per harness-version write and per champion
move. It shows database events (a stored proposal, its verdict, a committed promotion), not model reasoning. Start
it before a generation; it prints nothing for history and must be restarted if the connection drops.
"""

import argparse

from flex import store


def line(event: dict) -> str | None:
    doc = event.get("fullDocument")
    if not doc:
        return None
    coll = event["ns"]["coll"]
    if coll == "champion":
        return f"PROMOTED  champion pointer -> {doc.get('version')} (committed in Atlas)"
    if coll != "harness_versions":
        return f"{coll}: {doc.get('_id')}"
    reasons = "; ".join((doc.get("verdict") or {}).get("reasons", []))
    decision = f"accepted as {doc['acceptance']}" if doc.get("acceptance") else ("rejected" if doc.get("status") == "rejected" else "no verdict")
    return f"{doc['_id']:12s} status={doc.get('status', '?'):9s} {decision:20s} {reasons}"


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
