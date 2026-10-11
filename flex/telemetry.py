"""Optional Raindrop instrumentation. A no-op without RAINDROP_WRITE_KEY; a failure here never stops evolve."""

import os
from pathlib import Path

from dotenv import load_dotenv

from flex.contract import Verdict

load_dotenv(Path(__file__).parent.parent / ".env")

_ready = False


def _client():
    global _ready
    import raindrop.analytics as raindrop
    if not _ready:
        raindrop.init(api_key=os.environ["RAINDROP_WRITE_KEY"], tracing_enabled=False)
        _ready = True
    return raindrop


def record(proposal: dict, verdict: Verdict, version_id: str):
    if not os.environ.get("RAINDROP_WRITE_KEY"):
        return
    props = {"version": version_id, "accepted": verdict["accepted"], "reasons": "; ".join(verdict["reasons"])}
    if verdict["cost_delta_pct"] is not None:
        props["cost_delta_pct"] = verdict["cost_delta_pct"]
    try:
        _client().track_ai(user_id="flex-supervisor", event="proposal", model=proposal.get("model"),
                           input=proposal["predicted"], output=proposal["rationale"], properties=props)
    except Exception as e:
        print(f"telemetry: {type(e).__name__}: {e}")


def flush():
    if not _ready:
        return
    try:
        _client().flush()
    except Exception as e:
        print(f"telemetry: {type(e).__name__}: {e}")
