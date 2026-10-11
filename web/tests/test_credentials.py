import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from web.scripts.export_replay import export


class CredentialCanaryTests(unittest.TestCase):
    def test_credentials_abort_before_any_replay_write(self):
        canaries = ["sk-" + "ant-canary-only", "mongodb" + "://canary:password@example.invalid/db",
                    "mongodb+srv" + "://canary:password@example.invalid/db", "-----BEGIN " + "PRIVATE KEY-----",
                    "-----BEGIN RSA " + "PRIVATE KEY-----", "-----BEGIN OPENSSH " + "PRIVATE KEY-----", "rdk" + "_canary_only"]
        for canary in canaries:
            for key in (False, True):
                with self.subTest(pattern=canaries.index(canary), key=key), TemporaryDirectory() as directory:
                    output = Path(directory) / "public/replay.json"
                    output.parent.mkdir()
                    original = b"existing reviewed replay\n"
                    output.write_bytes(original)
                    value = {canary: "ordinary text"} if key else {"rationale": f"prefix {canary} suffix"}
                    replay = {"versions": [{"nested": [value]}]}
                    with patch("web.scripts.export_replay.recorded", return_value=replay):
                        with self.assertRaises(ValueError) as caught:
                            export(output=output)
                    message = str(caught.exception)
                    self.assertIn('$["versions"][0]["nested"][0]', message)
                    self.assertIn("[key #0]" if key else '["rationale"]', message)
                    self.assertNotIn(canary, message)
                    self.assertEqual(output.read_bytes(), original)
                    self.assertFalse((Path(directory) / ".replay.tmp").exists())

    def test_safe_replay_is_written(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "public/replay.json"
            replay = {"versions": [{"rationale": "No credentials in this explanation."}]}
            with patch("web.scripts.export_replay.recorded", return_value=replay):
                export(output=output)
            self.assertEqual(json.loads(output.read_text()), replay)


if __name__ == "__main__":
    unittest.main()
