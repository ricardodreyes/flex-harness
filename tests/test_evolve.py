import pytest

from flex import evolve, supervisor, telemetry
from flex.evaluate import run
from flex.scenarios import dev
from policies.control_repair import CONTROL_REPAIR
from policies.incumbent import INCUMBENT
from policies.restart_aware import RESTART_AWARE


@pytest.fixture(autouse=True)
def quiet_telemetry(monkeypatch):
    monkeypatch.setattr(telemetry, "record", lambda *a: None)


def stub(monkeypatch, policy):
    monkeypatch.setattr(supervisor, "propose", lambda *a: {"policy": policy, "rationale": "stub", "predicted": "stub"})


@pytest.mark.parametrize("bad", [
    {**INCUMBENT, "rules": INCUMBENT["rules"] * 3},
    {**INCUMBENT, "context_fields": ["event_now"]},
])
def test_invalid_proposal_is_a_rejected_version(tmp_path, monkeypatch, bad):
    store = evolve.JsonlStore(tmp_path)
    stub(monkeypatch, bad)
    evolve.evolve(store, 1)
    rejected = [v for v in store.versions() if v["status"] == "rejected"]
    assert len(rejected) == 1
    assert rejected[0]["verdict"]["reasons"][0] == "invalid policy"
    assert rejected[0]["author"] == "supervisor"
    assert store.champion()["_id"] == "v0"


def test_restart_aware_is_accepted_on_cost(tmp_path, monkeypatch):
    store = evolve.JsonlStore(tmp_path)
    stub(monkeypatch, RESTART_AWARE)
    evolve.evolve(store, 1)
    champ = store.champion()
    assert champ["_id"] != "v0" and champ["parent"] == "v0" and champ["policy"] == RESTART_AWARE
    verdict = champ["verdict"]
    assert verdict["accepted"] and verdict["reasons"][0].startswith("same pass set, training energy -")
    old, new = [11049.05, 14993.50, 13716.86], [10749.27, 14349.10, 12783.02]
    assert round(verdict["cost_delta_pct"], 2) == round((sum(new) - sum(old)) / sum(old) * 100, 2)
    assert {v["_id"]: v["status"] for v in store.versions()}["v0"] == "candidate"


def test_rerun_replaces_runs(tmp_path):
    store = evolve.JsonlStore(tmp_path)
    evolve.evolve(store, 0)
    evolve.evolve(store, 0)
    evolve._score(store, "v0", INCUMBENT, dev())
    evolve._score(store, "v0", INCUMBENT, dev())
    assert len(store._read("runs.jsonl")) == len(dev())


def test_evidence_holds_dev_only():
    text = supervisor.evidence({"_id": "v0", "policy": INCUMBENT}, run(INCUMBENT, dev(), "v0"), [], [])
    assert "val-" not in text and "final-" not in text
    assert supervisor._dump(CONTROL_REPAIR["rules"]) not in text
