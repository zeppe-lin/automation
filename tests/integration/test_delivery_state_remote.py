#!/usr/bin/env python3

import os
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from automation import gitstate


class RemoteDeliveryStateIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.remote = self.root / "state.git"
        self.first = self.root / "first"
        self.second = self.root / "second"

        subprocess.run(["git", "init", "--bare", "-q", str(self.remote)], check=True)
        subprocess.run(["git", "init", "-q", str(self.first)], check=True)
        subprocess.run(["git", "-C", str(self.first), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(self.first), "config", "user.email", "test@example.invalid"], check=True)
        (self.first / "seed").write_text("seed\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.first), "add", "seed"], check=True)
        subprocess.run(["git", "-C", str(self.first), "commit", "-qm", "seed"], check=True)
        subprocess.run(["git", "-C", str(self.first), "remote", "add", "origin", str(self.remote)], check=True)
        subprocess.run(["git", "-C", str(self.first), "push", "-q", "origin", "HEAD:refs/heads/master"], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def environment(repository, run_id):
        return {
            "AUTOMATION_STATE_REPOSITORY": str(repository),
            "AUTOMATION_STATE_REMOTE": "origin",
            "AUTOMATION_RUN_ID": run_id,
            "AUTOMATION_RUN_ATTEMPT": "1",
        }


    def test_remote_claim_uses_compare_and_swap_against_stale_observation(self):
        event_id = (
            "push:zeppe-lin/example:refs/heads/master:"
            + "3" * 40
            + ":"
            + "4" * 40
        )
        key = gitstate.push_key(
            "zeppe-lin/example", event_id, "mail-dev", "b" * 40, 1
        )
        subprocess.run(["git", "clone", "-q", str(self.remote), str(self.second)], check=True)
        first_ledger = gitstate.DeliveryLedger.from_environment(
            self.environment(self.first, "first-claim")
        )
        second_ledger = gitstate.DeliveryLedger.from_environment(
            self.environment(self.second, "stale-claim")
        )
        self.assertTrue(first_ledger.acquire_claim(key))

        # Simulate a controller that observed the claim ref as absent just
        # before another workspace won it. The remote force-with-lease must
        # still reject the stale create.
        with mock.patch.object(second_ledger, "ref_value", return_value=None):
            self.assertFalse(second_ledger.acquire_claim(key))

        remote_claims = subprocess.run(
            ["git", "ls-remote", "--refs", str(self.remote), key.claim_ref],
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()
        self.assertEqual(len(remote_claims), 1)

    def test_remote_ledger_is_shared_across_fresh_workspaces(self):
        event_id = (
            "push:zeppe-lin/example:refs/heads/master:"
            + "1" * 40
            + ":"
            + "2" * 40
        )
        key = gitstate.push_key(
            "zeppe-lin/example", event_id, "mail-dev", "a" * 40, 1
        )
        first_ledger = gitstate.DeliveryLedger.from_environment(
            self.environment(self.first, "first-run")
        )
        self.assertEqual(first_ledger.claim(key)[0], 0)
        self.assertEqual(first_ledger.mark_delivered(key)[0], 0)

        remote_refs = subprocess.run(
            ["git", "ls-remote", "--refs", str(self.remote), "refs/automation/*"],
            check=True, capture_output=True, text=True,
        ).stdout
        self.assertIn(key.delivered_ref, remote_refs)
        self.assertIn(key.attempts_prefix + "first-run-1", remote_refs)

        subprocess.run(["git", "clone", "-q", str(self.remote), str(self.second)], check=True)
        second_ledger = gitstate.DeliveryLedger.from_environment(
            self.environment(self.second, "second-run")
        )
        status, message = second_ledger.claim(key)
        self.assertEqual(status, gitstate.ALREADY_DELIVERED)
        self.assertEqual(message, "already delivered")


if __name__ == "__main__":
    unittest.main()
