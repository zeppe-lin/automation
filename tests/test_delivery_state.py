#!/usr/bin/env python3

import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "delivery_state", ROOT / "libexec" / "delivery-state.py"
)
state = importlib.util.module_from_spec(spec)
spec.loader.exec_module(state)


class DeliveryStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.invalid"], check=True)
        (self.repo / "seed").write_text("seed\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "seed"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "seed"], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def environment(self):
        return {
            "AUTOMATION_STATE_REPOSITORY": str(self.repo),
            "AUTOMATION_RUN_ID": "123",
            "AUTOMATION_RUN_ATTEMPT": "2",
        }

    def refs(self):
        result = subprocess.run(
            ["git", "-C", str(self.repo), "for-each-ref", "--format=%(refname)", "refs/automation"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.splitlines()

    def test_claim_records_attempt(self):
        with mock.patch.dict(os.environ, self.environment(), clear=False):
            result = state.claim("zeppe-lin/pkgman", "v6.3", "irc")
        self.assertEqual(result, 0)
        self.assertIn(
            "refs/automation/delivery/release/zeppe-lin/pkgman/v6.3/irc/attempts/123-2",
            self.refs(),
        )

    def test_claim_skips_already_delivered(self):
        with mock.patch.dict(os.environ, self.environment(), clear=False):
            self.assertEqual(state.mark_delivered("zeppe-lin/pkgman", "v6.3", "mail-user"), 0)
            self.assertEqual(
                state.claim("zeppe-lin/pkgman", "v6.3", "mail-user"),
                state.ALREADY_DELIVERED,
            )

    def test_claim_blocks_unresolved_attempt(self):
        with mock.patch.dict(os.environ, self.environment(), clear=False):
            self.assertEqual(state.claim("zeppe-lin/pkgman", "v6.3", "mail-dev"), 0)
            self.assertEqual(
                state.claim("zeppe-lin/pkgman", "v6.3", "mail-dev"),
                state.UNRESOLVED_ATTEMPT,
            )
            self.assertEqual(
                state.claim("zeppe-lin/pkgman", "v6.3", "mail-dev", force=True),
                0,
            )

    def test_ref_namespace_rejects_untrusted_source(self):
        with self.assertRaisesRegex(ValueError, "invalid source repository"):
            state.ref_base("other/pkgman", "v6.3", "irc")
        with self.assertRaisesRegex(ValueError, "invalid release tag"):
            state.ref_base("zeppe-lin/pkgman", "v6.3/evil", "irc")


if __name__ == "__main__":
    unittest.main()
