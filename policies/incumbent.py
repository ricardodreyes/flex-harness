"""The frozen incumbent: a slack-or-cheap scheduler tuned on dev-*-low only (flex.tune), then frozen.

No point on the spec grid (u in {1.0, 1.2, 1.5}, c in {0, 2, 4}, q in {0.1..0.5}) passes all three dev-*-low
scenarios; the literals below are the grid's least-late point (1 late job-hour on dev-13-low, $10,604.84 summed
training energy). Frozen as-is so the before/after story runs against one fixed baseline."""

from flex.contract import Policy

INCUMBENT: Policy = {
    "context_fields": ["event_now", "slack_h", "need_h", "price_pct"],
    "rules": [
        {"when": [{"field": "event_now", "op": "==", "value": True}], "power": 0.0},
        {"when": [{"field": "slack_h", "op": "<=", "value": {"field": "need_h", "times": 1.0, "plus": 0}}],
         "power": 1.0},
        {"when": [{"field": "price_pct", "op": "<=", "value": 0.5}], "power": 1.0},
    ],
    "default_power": 0.0,
}
