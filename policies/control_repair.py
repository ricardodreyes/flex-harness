"""Control, not agent-generated, never shown to the supervisor. Exists only to prove a behavioral repair is
feasible: the incumbent's frozen rules with `running` added to context, a hysteresis rule after the event rule,
and the slack constant c raised by 2. Hand-authored, not tuned."""

from flex.contract import Policy

CONTROL_REPAIR: Policy = {
    "context_fields": ["event_now", "slack_h", "need_h", "price_pct", "running"],
    "rules": [
        {"when": [{"field": "event_now", "op": "==", "value": True}], "power": 0.0},
        {"when": [{"field": "running", "op": "==", "value": True}, {"field": "price_pct", "op": "<=", "value": 0.7}],
         "power": 1.0},
        {"when": [{"field": "slack_h", "op": "<=", "value": {"field": "need_h", "times": 2.0, "plus": 2}}],
         "power": 1.0},
        {"when": [{"field": "price_pct", "op": "<=", "value": 0.5}], "power": 1.0},
    ],
    "default_power": 0.0,
}
