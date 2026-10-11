"""Separately retuned reference: the incumbent family plus a hysteresis rule that keeps a warm job running while
prices stay moderate. Tuned on dev-*-high only (flex.tune, widened grid): the cheapest point that passes all
three dev-*-high scenarios, $15,049.30 summed training energy.

Retuned at 1:55 p.m. after the lateness fix: the same grid returned the same point, (u, c, q, h) =
(2.0, 0, 0.5, 0.8), at the same $15,049.30."""

from flex.contract import Policy

RESTART_AWARE: Policy = {
    "context_fields": ["event_now", "slack_h", "need_h", "price_pct", "running", "restart_kwh"],
    "rules": [
        {"when": [{"field": "event_now", "op": "==", "value": True}], "power": 0.0},
        {"when": [{"field": "slack_h", "op": "<=", "value": {"field": "need_h", "times": 2.0, "plus": 0}}],
         "power": 1.0},
        {"when": [{"field": "running", "op": "==", "value": True}, {"field": "price_pct", "op": "<=", "value": 0.8}],
         "power": 1.0},
        {"when": [{"field": "price_pct", "op": "<=", "value": 0.5}], "power": 1.0},
    ],
    "default_power": 0.0,
}
