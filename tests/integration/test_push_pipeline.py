#!/usr/bin/env python3

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "support"))
from gitrepo import GitFixture  # noqa: E402

PREPARE = ROOT / "libexec" / "prepare-push.py"


class PushPipelineIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = GitFixture(self.root / "repository")
        self.base = self.repo.commit("base: establish history")

    def tearDown(self):
        self.tmp.cleanup()

    def envelope(self, before, after):
        return {
            "schema": 1,
            "event": "push",
            "repository": "zeppe-lin/example",
            "repository_url": "https://github.com/zeppe-lin/example",
            "ref": "refs/heads/master",
            "before": before,
            "after": after,
            "compare_url": "https://github.com/zeppe-lin/example/compare/example",
        }

    def prepare(self, before, after):
        event = self.root / "event.json"
        output = self.root / "prepared"
        event.write_text(json.dumps(self.envelope(before, after)), encoding="utf-8")
        result = subprocess.run(
            [str(PREPARE), str(self.repo.path), str(event), str(output)],
            check=False, capture_output=True, text=True,
        )
        return result, output

    def test_real_history_classifies_routes_and_renders_in_commit_order(self):
        first = self.repo.commit(
            "ordinary: first change\n\nbody with `ticks`, $(), ::warning:: and UTF-8 Ж."
        )
        second = self.repo.commit(
            "[news][security] kernel: update security state\n\n"
            "Operator details.\n\n"
            "Affected: Zeppe-Lin 2.x\n"
            "Action: update, rebuild initramfs, reboot\n"
            "News: .news/2026-kernel\n"
            "Reference: CVE-2026-1000\n"
            "Reference: CVE-2026-1001\n"
        )
        result, output = self.prepare(self.base, second)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual([c["sha"] for c in manifest["commits"]], [first, second])
        self.assertEqual(manifest["routing"]["mail-dev"], 2)
        self.assertEqual(manifest["routing"]["mail-user"], 1)
        self.assertEqual(
            manifest["commits"][1]["classification"]["trailers"]["Reference"],
            ["CVE-2026-1000", "CVE-2026-1001"],
        )

        dev_files = sorted((output / "mail-dev").glob("*.json"))
        user_files = sorted((output / "mail-user").glob("*.json"))
        self.assertEqual([path.name for path in dev_files], ["0001.json", "0002.json"])
        self.assertEqual([path.name for path in user_files], ["0002.json"])
        dev_second = json.loads(dev_files[1].read_text(encoding="utf-8"))
        user_second = json.loads(user_files[0].read_text(encoding="utf-8"))
        self.assertIn("kernel: update security state", dev_second["body"])
        self.assertIn("Affected: Zeppe-Lin 2.x", user_second["body"])
        self.assertIn("Action: update, rebuild initramfs, reboot", user_second["body"])
        self.assertEqual(user_second["body"].count("Affected: Zeppe-Lin 2.x"), 1)
        self.assertTrue(
            (output / "irc.txt").read_text(encoding="utf-8").startswith("[news][security] example:master:")
        )
        requirements = json.loads(
            (output / "requirements.json").read_text(encoding="utf-8")
        )
        self.assertEqual(requirements[0]["requirements"], ["system-news"])

    def test_policy_failure_stops_before_rendering(self):
        after = self.repo.commit("[breaking] api: invalid unclassified migration")
        result, output = self.prepare(self.base, after)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be combined with [news]", result.stderr)
        self.assertFalse((output / "manifest.json").exists())

    def test_obsolete_notify_stops_before_rendering(self):
        after = self.repo.commit("[notify] package: old routing semantics")
        result, output = self.prepare(self.base, after)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("obsolete", result.stderr)
        self.assertFalse((output / "mail-dev").exists())


if __name__ == "__main__":
    unittest.main()
