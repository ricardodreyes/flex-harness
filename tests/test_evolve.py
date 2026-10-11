import json

import bson
import pytest

from flex import evaluate, evolve, final, supervisor, telemetry
from flex.evaluate import accept, run
from flex.scenarios import by_id, dev, validation
from policies.control_repair import CONTROL_REPAIR
from policies.incumbent import INCUMBENT
from policies.restart_aware import RESTART_AWARE


@pytest.fixture(autouse=True)
def quiet_telemetry(monkeypatch):
    monkeypatch.setattr(telemetry, "record", lambda *a: None)


def stub(monkeypatch, policy):
    monkeypatch.setattr(supervisor, "propose", lambda *a: {"policy": policy, "rationale": "stub", "predicted": "stub",
                                                          "model": "stub", "usage": {}, "error": None})


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
        assert store.champion()["_id"] == cand["_id"] and status["v0"] == "retired"
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


def test_read_proposal_keeps_unknown_keys_and_evolve_stores_them_rejected(tmp_path, monkeypatch):
    policy = {**INCUMBENT, "surprise": 1}
    env = supervisor.read_proposal(json.dumps({"policy": policy, "rationale": "r", "predicted": "p"}))
    assert env["policy"] == policy and env["error"] is None
    store = evolve.JsonlStore(tmp_path)
    monkeypatch.setattr(supervisor, "propose", lambda *a: env)
    evolve.evolve(store, 1)
    cand = next(v for v in store.versions() if v["author"] == "supervisor")
    assert cand["policy"] == policy and cand["status"] == "rejected" and not cand["verdict"]["accepted"]
    assert "acceptance" not in cand


def test_unparseable_response_is_a_stored_rejection_without_validation(tmp_path, monkeypatch):
    env = {**supervisor.read_proposal("not json"), "model": "stub", "usage": {}}
    assert env["error"] and env["policy"] == {"raw": "not json"}
    store = evolve.JsonlStore(tmp_path)
    monkeypatch.setattr(supervisor, "propose", lambda *a: env)
    evolve.evolve(store, 1)
    cand = next(v for v in store.versions() if v["author"] == "supervisor")
    assert cand["status"] == "rejected" and cand["verdict"]["reasons"][0].startswith("unparseable proposal: ")
    assert not any(r["version"] == cand["_id"] for r in store._read("runs.jsonl"))
    assert store.champion()["_id"] == "v0"


@pytest.mark.parametrize("fixed, acceptance", [(["val-21-high"], "repair"), ([], "cost")])
def test_acceptance_is_marked_and_promotes(tmp_path, monkeypatch, fixed, acceptance):
    store = evolve.JsonlStore(tmp_path)
    stub(monkeypatch, {**INCUMBENT, "default_power": 0.0})
    monkeypatch.setattr(evaluate, "accept", lambda *a: {"accepted": True, "reasons": ["stub"], "fixed": fixed,
                                                        "regressed": [], "cost_delta_pct": -2.0})
    evolve.evolve(store, 1)
    cand = next(v for v in store.versions() if v["author"] == "supervisor")
    assert cand["acceptance"] == acceptance and store.champion()["_id"] == cand["_id"]
    assert {v["_id"]: v["status"] for v in store.versions()}["v0"] == "retired"


def test_evidence_leaves_out_notes_and_infeasible_scenarios():
    results = run(INCUMBENT, dev(), "v0")
    text = supervisor.evidence({"_id": "v0", "policy": INCUMBENT}, results, [], [])
    assert "dev-imp-11" not in text and "dev-cap-11" not in text
    assert "val-" not in text and "final-" not in text
    assert not any(by_id(s)["note"] in text for s in results)


def test_final_refuses_when_the_manifest_exists(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(final, "RESULTS", tmp_path)
    manifest = tmp_path / "final_manifest.json"
    manifest.write_bytes(b'{"frozen": true}')
    with pytest.raises(SystemExit) as e:
        final.main([])
    assert e.value.code and manifest.read_bytes() == b'{"frozen": true}'
    assert [p.name for p in tmp_path.iterdir()] == ["final_manifest.json"]
    assert "final_manifest.json" in capsys.readouterr().out


@pytest.mark.parametrize("policy, stored", [
    ([1, 2], {"raw": "[1, 2]"}),
    ({"context_fields": [], "rules": [], "default_power": 10**20},
     {"context_fields": [], "rules": [], "default_power": "100000000000000000000"}),
])
def test_malformed_policy_is_stored_as_a_rejection(tmp_path, monkeypatch, policy, stored):
    store = evolve.JsonlStore(tmp_path)
    stub(monkeypatch, policy)
    evolve.evolve(store, 1)
    cand = next(v for v in store.versions() if v["author"] == "supervisor")
    assert cand["policy"] == stored and cand["status"] == "rejected" and not cand["verdict"]["accepted"]
    bson.encode({"policy": cand["policy"]})


def test_pin_takes_every_champion_and_the_references():
    def v(id, status, acceptance=None):
        return {"_id": id, "status": status, "author": "supervisor", "policy": INCUMBENT, "created_at": id,
                **({"acceptance": acceptance} if acceptance else {})}
    versions = [v("b", "retired", "repair"), v("a", "retired"), v("c", "rejected"), v("d", "candidate"),
                v("e", "champion", "cost")]
    pinned = final.pin(versions, validation())
    assert [(p["version"], p["role"], p["acceptance"]) for p in pinned] == [
        ("a", "champion", None), ("b", "champion", "repair"), ("e", "champion", "cost"),
        ("restart_aware", "reference", None), ("control", "reference", None)]
    assert pinned[-1]["policy"] == CONTROL_REPAIR and pinned[-1]["author"] == "control"
    assert pinned[0]["identity"] == evaluate.identity(INCUMBENT, validation())
