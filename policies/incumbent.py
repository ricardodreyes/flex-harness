"""The frozen incumbent: a slack-or-cheap scheduler tuned on dev-*-low only (flex.tune), then frozen.

Tuned at 1:10 p.m. on the widened grid in flex.tune: the cheapest point that passes all three dev-*-low
scenarios, $10,771.53 summed training energy. The first grid (u up to 1.5, c up to 4) had no passing point,
so the grid was widened after the first preflight had already shown the dev-*-high results."""

from flex.contract import Policy

INCUMBENT: Policy = {
    "context_fields": ["event_now", "slack_h", "need_h", "price_pct"],
    "rules": [
        {"when": [{"field": "event_now", "op": "==", "value": True}], "power": 0.0},
        {"when": [{"field": "slack_h", "op": "<=", "value": {"field": "need_h", "times": 2.0, "plus": 0}}],
         "power": 1.0},
        {"when": [{"field": "price_pct", "op": "<=", "value": 0.5}], "power": 1.0},
    ],
    "default_power": 0.0,
}
