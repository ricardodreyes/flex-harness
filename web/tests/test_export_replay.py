from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from web.scripts.export_replay import export, fixture, recorded, SCENARIO


def matches(record, query):
    for key, expected in query.items():
        if key == "$or":
            if not any(matches(record, option) for option in expected):
                return False
            continue
        value = record
        for part in key.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if isinstance(expected, dict) and "$in" in expected:
            if value not in expected["$in"]:
                return False
        elif value != expected:
            return False
    return True


class Reader:
    def __init__(self, replay):
        self.records = {"harness_versions": deepcopy(replay["versions"]), "runs": deepcopy(replay["runs"]),
                        "hours": deepcopy(replay["hours"]), "misses": deepcopy(replay["misses"])}
        self.calls = []
        self.closed = False
        for run in self.records["runs"]:
            run["attempt"] = f"attempt-{run['_id']}"
        for hour in self.records["hours"]:
            hour["meta"]["attempt"] = f"attempt-{hour['meta']['run']}"
        for miss in self.records["misses"]:
            miss["attempt"] = f"attempt-{miss['run']}"

    def __getitem__(self, name):
        if name == "flex":
            return self
        reader = self

        class Collection:
            def find(self, query, projection):
                reader.calls.append((name, query, projection))
                return [{key: deepcopy(value) for key, value in record.items() if projection.get(key)}
                        for record in reader.records[name] if matches(record, query)]

        return Collection()

    def close(self):
        self.closed = True


class ExportReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = fixture()

    def setUp(self):
        self.reader = Reader(self.fixture)
        self.client = patch("flex.store.client", return_value=self.reader).start()
        self.addCleanup(patch.stopall)
        self.repair = next(version for version in self.reader.records["harness_versions"]
                           if version["acceptance"] == "repair")
        self.baseline = next(version for version in self.reader.records["harness_versions"]
                             if version["author"] == "baseline")

    def test_reader_export_keeps_verbatim_reasons_and_structured_markers(self):
        self.repair["verdict"]["reasons"] = ["repairs val-26-high; training energy +2.1% to restore deadlines"]
        self.repair["private"] = "not public"
        final = deepcopy(self.reader.records["runs"][0])
        final.update(_id="final-run", scenario="final-31", split="final")
        self.reader.records["runs"].append(final)
        replay = recorded()
        self.client.assert_called_once_with("reader")
        self.assertTrue(self.reader.closed)
        self.assertEqual(replay["source"], "recorded evaluation replay")
        self.assertEqual(replay["focus"], {"version": self.repair["_id"], "scenario": SCENARIO})
        versions = {version["_id"]: version for version in replay["versions"]}
        self.assertEqual(versions[self.repair["_id"]]["verdict"]["reasons"], self.repair["verdict"]["reasons"])
        self.assertEqual(versions[self.repair["_id"]]["acceptance"], "repair")
        self.assertIsNone(versions[self.baseline["_id"]]["acceptance"])
        self.assertIsNone(versions["fixture-control-cheap"]["acceptance"])
        self.assertNotIn("private", versions[self.repair["_id"]])
        self.assertTrue(all("jobs" in run and "diagnosis" in run and "totals" in run for run in replay["runs"]))
        self.assertTrue(all(run["split"] in ("dev", "validation") and "attempt" not in run for run in replay["runs"]))
        selected = [f"{self.baseline['_id']}:{SCENARIO}", f"{self.repair['_id']}:{SCENARIO}"]
        self.assertEqual(self.reader.calls[1][1], {"split": {"$in": ["dev", "validation"]}})
        self.assertEqual(self.reader.calls[2][1], {"meta.run": {"$in": selected}, "meta.scenario": SCENARIO,
                         "$or": [{"meta.run": run_id, "meta.attempt": f"attempt-{run_id}"} for run_id in selected]})
        self.assertTrue(all("attempt" not in hour["meta"] for hour in replay["hours"]))

    def test_retired_repair_wins_focus_over_a_newer_cost_acceptance(self):
        self.repair["status"] = "retired"
        cost = deepcopy(self.repair)
        cost.update(_id="newest-cost", parent=self.repair["_id"], created_at="2099-01-01T00:00:00Z", status="champion")
        cost["verdict"].update(fixed=[], reasons=["cheaper: training energy -3.00%"])
        self.reader.records["harness_versions"].append(cost)
        replay = recorded()
        self.assertEqual(replay["focus"]["version"], self.repair["_id"])
        self.assertEqual(next(version for version in replay["versions"] if version["_id"] == cost["_id"])["acceptance"], "cost")

    def test_shuffled_records_keep_the_same_focus_and_sorted_hours(self):
        for records in self.reader.records.values():
            records.reverse()
        replay = recorded()
        self.assertEqual(replay["focus"]["version"], self.repair["_id"])
        scenario = next(scenario for scenario in replay["scenarios"] if scenario["id"] == SCENARIO)
        expected = scenario["arrival_days"] * 24 + scenario["tail_h"]
        for run_id in {hour["meta"]["run"] for hour in replay["hours"]}:
            self.assertEqual([hour["h"] for hour in replay["hours"] if hour["meta"]["run"] == run_id], list(range(expected)))

    def test_equal_timestamps_choose_the_last_id_deterministically(self):
        newer = deepcopy(self.repair)
        newer["_id"] = "z-repair"
        self.reader.records["harness_versions"].insert(0, newer)
        candidate = deepcopy(next(run for run in self.reader.records["runs"]
                                  if run["version"] == self.repair["_id"] and run["scenario"] == SCENARIO))
        original_id = candidate["_id"]
        candidate.update(_id=f"z-repair:{SCENARIO}", version="z-repair", attempt="new-attempt")
        self.reader.records["runs"].append(candidate)
        for original in self.reader.records["hours"][:]:
            if original["meta"]["run"] == original_id:
                hour = deepcopy(original)
                hour["meta"].update(run=candidate["_id"], version="z-repair", attempt="new-attempt")
                self.reader.records["hours"].append(hour)
        replay = recorded()
        self.assertEqual(replay["focus"]["version"], "z-repair")
        self.assertEqual({hour["meta"]["version"] for hour in replay["hours"]}, {self.baseline["_id"], "z-repair"})

    def test_parent_is_preserved_when_it_is_not_the_frozen_baseline(self):
        ancestor = deepcopy(self.baseline)
        ancestor.update(_id="ancestor", author="supervisor", parent=self.baseline["_id"], status="retired")
        self.reader.records["harness_versions"].append(ancestor)
        parent_run = deepcopy(next(run for run in self.reader.records["runs"]
                                   if run["version"] == self.baseline["_id"] and run["scenario"] == SCENARIO))
        parent_run.update(_id=f"ancestor:{SCENARIO}", version="ancestor")
        self.reader.records["runs"].append(parent_run)
        self.repair["parent"] = "ancestor"
        replay = recorded()
        self.assertEqual(next(version for version in replay["versions"] if version["_id"] == self.repair["_id"])["parent"], "ancestor")
        self.assertEqual({hour["meta"]["version"] for hour in replay["hours"]}, {self.baseline["_id"], self.repair["_id"]})

    def test_duplicate_version_scenario_run_is_rejected(self):
        duplicate = deepcopy(self.reader.records["runs"][0])
        duplicate["_id"] = "duplicate-summary"
        self.reader.records["runs"].append(duplicate)
        with self.assertRaisesRegex(ValueError, "Duplicate or unlinked run"):
            recorded()

    def test_missing_target_run_is_rejected(self):
        self.reader.records["runs"] = [run for run in self.reader.records["runs"]
                                      if not (run["version"] == self.repair["_id"] and run["scenario"] == SCENARIO)]
        with self.assertRaisesRegex(ValueError, "No accepted repair"):
            recorded()

    def test_missing_parent_is_rejected(self):
        self.repair["parent"] = "unrecorded-parent"
        with self.assertRaisesRegex(ValueError, "Matching parent"):
            recorded()

    def test_missing_frozen_baseline_is_rejected(self):
        self.baseline["author"] = "control"
        with self.assertRaisesRegex(ValueError, "One matching frozen baseline"):
            recorded()

    def test_incompatible_identity_is_rejected(self):
        run = next(run for run in self.reader.records["runs"]
                   if run["version"] == self.repair["_id"] and run["scenario"] == SCENARIO)
        run["identity"]["manifest_sha256"] = "different-manifest"
        with self.assertRaisesRegex(ValueError, "Matching parent"):
            recorded()

    def test_incomplete_duplicate_or_mismatched_hours_are_rejected(self):
        original = deepcopy(self.reader.records["hours"])
        for failure in ("missing", "duplicate", "different inputs"):
            with self.subTest(failure=failure):
                self.reader.records["hours"] = deepcopy(original)
                if failure == "missing":
                    self.reader.records["hours"].pop()
                elif failure == "duplicate":
                    self.reader.records["hours"].append(deepcopy(original[0]))
                else:
                    self.reader.records["hours"][0]["price"] += 1
                with self.assertRaises(ValueError):
                    recorded()

    def test_only_the_attempt_pointed_to_by_each_summary_is_exported(self):
        old_hour = deepcopy(self.reader.records["hours"][0])
        old_hour["meta"]["attempt"] = "stale-attempt"
        old_hour["price"] = -999
        self.reader.records["hours"].append(old_hour)
        old_miss = deepcopy(self.reader.records["misses"][0])
        old_miss["attempt"] = "stale-attempt"
        old_miss["detail"] = "stale evidence"
        self.reader.records["misses"].append(old_miss)
        replay = recorded()
        self.assertEqual(len(replay["hours"]), len(self.fixture["hours"]))
        self.assertFalse(any(hour["price"] == -999 for hour in replay["hours"]))
        self.assertFalse(any(miss["detail"] == "stale evidence" for miss in replay["misses"]))

    def test_failed_export_preserves_the_existing_artifact(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "public/replay.json"
            output.parent.mkdir()
            output.write_text("existing reviewed replay\n")
            self.reader.records["hours"].pop()
            with self.assertRaisesRegex(ValueError, "Incomplete selected hours"):
                export(output=output)
            self.assertEqual(output.read_text(), "existing reviewed replay\n")
            self.assertTrue(self.reader.closed)

    def test_bad_job_evidence_preserves_the_existing_artifact(self):
        original = deepcopy(self.reader.records["runs"])
        for failure in ("missing", "truncated", "duplicate", "different workload", "missing outcome", "missing diagnosis", "missing total"):
            with self.subTest(failure=failure), TemporaryDirectory() as directory:
                self.reader.records["runs"] = deepcopy(original)
                candidate = next(run for run in self.reader.records["runs"]
                                 if run["version"] == self.repair["_id"] and run["scenario"] == SCENARIO)
                if failure == "missing":
                    del candidate["jobs"]
                elif failure == "truncated":
                    candidate["jobs"].pop()
                elif failure == "duplicate":
                    candidate["jobs"][1] = deepcopy(candidate["jobs"][0])
                elif failure == "different workload":
                    candidate["jobs"][0]["work_kwh"] += 1
                elif failure == "missing outcome":
                    del candidate["jobs"][0]["done_h"]
                elif failure == "missing diagnosis":
                    del candidate["diagnosis"]
                else:
                    del candidate["totals"]["training_energy_cost"]
                output = Path(directory) / "public/replay.json"
                output.parent.mkdir()
                output.write_text("existing reviewed replay\n")
                with self.assertRaises(ValueError):
                    export(output=output)
                self.assertEqual(output.read_text(), "existing reviewed replay\n")

    def test_export_writes_the_reader_result_atomically(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "public/replay.json"
            export(output=output)
            replay = json.loads(output.read_text())
            self.assertEqual(replay["source"], "recorded evaluation replay")
            self.assertEqual(replay["focus"], {"version": self.repair["_id"], "scenario": SCENARIO})
            self.assertFalse((Path(directory) / ".replay.tmp").exists())


if __name__ == "__main__":
    unittest.main()
