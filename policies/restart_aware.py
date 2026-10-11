"""Separately retuned reference: the incumbent family plus a hysteresis rule that keeps a warm job running while
prices stay moderate. Tuned on dev-*-high only (flex.tune).

No point on the spec grid passes all three dev-*-high scenarios; the literals below are the least-late point
(6 late job-hours, $14,880.07 summed training energy)."""

from flex.contract import Policy

RESTART_AWARE: Policy = {
    "context_fields": ["event_now", "slack_h", "need_h", "price_pct", "running", "restart_kwh"],
    "rules": [
        {"when": [{"field": "event_now", "op": "==", "value": True}], "power": 0.0},
        {"when": [{"field": "slack_h", "op": "<=", "value": {"field": "need_h", "times": 1.0, "plus": 0}}],
         "power": 1.0},
        {"when": [{"field": "running", "op": "==", "value": True}, {"field": "price_pct", "op": "<=", "value": 0.8}],
         "power": 1.0},
        {"when": [{"field": "price_pct", "op": "<=", "value": 0.5}], "power": 1.0},
    ],
    "default_power": 0.0,
}
