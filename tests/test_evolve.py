import pytest

from flex import evolve, supervisor, telemetry
from flex.evaluate import accept, run
from flex.scenarios import dev, validation
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
    assert rejected[0]["author"] == "supervisor" and not rejected[0]["verdict"]["accepted"]
    assert rejected[0]["verdict"]["cost_delta_pct"] is None
    assert not any(r["version"] == rejected[0]["_id"] for r in store._read("runs.jsonl"))
    assert store.champion()["_id"] == "v0"


def test_stores_the_evaluator_verdict_and_promotes_only_on_accept(tmp_path, monkeypatch):
    store = evolve.JsonlStore(tmp_path)
    stub(monkeypatch, RESTART_AWARE)
    evolve.evolve(store, 1)
    expected = accept(RESTART_AWARE, run(INCUMBENT, validation(), "v0"), run(RESTART_AWARE, validation(), "c"))
    cand = next(v for v in store.versions() if v["author"] == "supervisor")
    assert cand["verdict"] == expected and cand["parent"] == "v0" and cand["policy"] == RESTART_AWARE
    status = {v["_id"]: v["status"] for v in store.versions()}
    if expected["accepted"]:
        assert store.champion()["_id"] == cand["_id"] and status["v0"] == "candidate"
    else:
        assert store.champion()["_id"] == "v0" and status[cand["_id"]] == "rejected"


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
