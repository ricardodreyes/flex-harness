import pytest

from flex.contract import World
from flex.sandbox import PolicyError, compile_policy
from flex.sim import simulate
from policies.v0 import V0

# 48h world: price $30 except hours 10-11 at $80, inference 100 kW flat, event in hours 20-21.
# One job arrives h0, deadline h40, 2800 kWh (4 h at 700 kW).
# v0 ignores the queue and trains at 700 kW in every hour with price <= 60 and no event: 48 - 2 - 2 = 44 h.
# Training energy: 44 h x 700 kW x $0.03 = $924.
# Inference energy: 46 h x 100 kW x $0.03 = $138, plus 2 h x 100 kW x $0.08 = $16.
# Energy = 924 + 138 + 16 = $1078. v0 idles in the event (100 kW < 280 cap), so the $3000 payment lands.
# The job finishes in hour 3, long before h40. Net = 1078 - 3000 = -1922, no late hours, no misses.
HOURS = 48
WORLD: World = {
    "split": "test", "start": "2026-09-01",
    "price": [80.0 if h in (10, 11) else 30.0 for h in range(HOURS)],
    "inference_kw": [100.0] * HOURS,
    "event": [h in (20, 21) for h in range(HOURS)],
    "event_cap_kw": 280.0,
    "jobs": [{"id": "j0", "arrive_h": 0, "deadline_h": 40, "work_kwh": 2800.0}],
}


def test_v0_hand_worked_totals():
    t = simulate(WORLD, V0, "t")["totals"]
    assert t["energy_cost"] == pytest.approx(1078.0)
    assert t["net"] == pytest.approx(-1922.0)
    assert (t["late_h"], t["missed_events"], t["over_cap_kwh"]) == (0, 0, 0.0)


def test_import_is_rejected():
    decide = compile_policy("def decide(obs):\n    return __import__('os') and 1.0", [])
    with pytest.raises(PolicyError):
        decide({})
