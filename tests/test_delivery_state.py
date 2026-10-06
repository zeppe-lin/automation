#!/usr/bin/env python3

import importlib.util
import os
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
    def environment(self):
        return {
            "GITHUB_REPOSITORY": "zeppe-lin/automation",
            "GITHUB_TOKEN": "token",
            "GITHUB_SHA": "a" * 40,
            "GITHUB_RUN_ID": "123",
            "GITHUB_RUN_ATTEMPT": "2",
        }

    @mock.patch.object(state, "create_ref")
    @mock.patch.object(state, "matching_refs")
    def test_claim_records_attempt(self, matching, create):
        matching.side_effect = [[], []]
        with mock.patch.dict(os.environ, self.environment(), clear=False):
            result = state.claim("zeppe-lin/pkgman", "v6.3", "irc", False)
        self.assertEqual(result, 0)
        create.assert_called_once_with(
            "zeppe-lin/automation",
            "automation/delivery/release/zeppe-lin/pkgman/v6.3/irc/attempts/123-2",
            "a" * 40,
            "token",
        )

    @mock.patch.object(state, "matching_refs")
    def test_claim_skips_already_delivered(self, matching):
        ref = "refs/automation/delivery/release/zeppe-lin/pkgman/v6.3/mail-user/delivered"
        matching.return_value = [{"ref": ref}]
        with mock.patch.dict(os.environ, self.environment(), clear=False):
            result = state.claim("zeppe-lin/pkgman", "v6.3", "mail-user", False)
        self.assertEqual(result, state.ALREADY_DELIVERED)

    @mock.patch.object(state, "matching_refs")
    def test_claim_blocks_unresolved_attempt(self, matching):
        matching.side_effect = [[], [{"ref": "refs/automation/delivery/release/x"}]]
        with mock.patch.dict(os.environ, self.environment(), clear=False):
            result = state.claim("zeppe-lin/pkgman", "v6.3", "mail-dev", False)
        self.assertEqual(result, state.UNRESOLVED_ATTEMPT)

    def test_ref_namespace_rejects_untrusted_source(self):
        with self.assertRaisesRegex(ValueError, "invalid source repository"):
            state.ref_base("other/pkgman", "v6.3", "irc")
        with self.assertRaisesRegex(ValueError, "invalid release tag"):
            state.ref_base("zeppe-lin/pkgman", "v6.3/evil", "irc")


if __name__ == "__main__":
    unittest.main()
