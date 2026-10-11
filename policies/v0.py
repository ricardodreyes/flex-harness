from datetime import datetime, timezone

from flex.contract import HarnessVersion

V0: HarnessVersion = {
    "_id": "v0",
    "parent": None,
    "code": 'def decide(obs):\n    return 0.0 if obs["event_now"] or obs["price"] > 60 else 1.0',
    "context_fields": ["price", "event_now"],
    "guardrails": {"max_train_frac": 1.0, "zero_during_event": False},
    "tools": [],
    "rationale": "fixed price threshold, what ops teams run today",
    "predicted": "",
    "scores": {},
    "status": "champion",
    "created_at": datetime(2026, 10, 11, tzinfo=timezone.utc),
}
