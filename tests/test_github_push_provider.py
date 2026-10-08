#!/usr/bin/env python3

import json
import unittest
from pathlib import Path

from automation.providers.github import (
    envelope_from_repository_dispatch,
    normalize_push_event,
    repository_dispatch_payload,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "github" / "push-normal.json"


class GitHubPushProviderTest(unittest.TestCase):
    def payload(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_normalizes_only_push_coordinates(self):
        envelope = normalize_push_event(self.payload())
        self.assertEqual(
            envelope,
            {
                "schema": 1,
                "event": "push",
                "repository": "zeppe-lin/example",
                "repository_url": "https://github.com/zeppe-lin/example",
                "ref": "refs/heads/master",
                "before": "1" * 40,
                "after": "2" * 40,
                "compare_url": "https://github.com/zeppe-lin/example/compare/1111111...2222222",
            },
        )
        self.assertNotIn("commits", envelope)
        self.assertNotIn("forced", envelope)

    def test_repository_dispatch_round_trip_preserves_only_envelope(self):
        envelope = normalize_push_event(self.payload())
        outgoing = repository_dispatch_payload(envelope)
        received = {
            "action": outgoing["event_type"],
            "client_payload": outgoing["client_payload"],
        }
        self.assertEqual(envelope_from_repository_dispatch(received), envelope)

    def test_creation_and_deletion_hints_must_match_coordinates(self):
        payload = self.payload()
        payload["created"] = True
        with self.assertRaisesRegex(ValueError, "contradicts"):
            normalize_push_event(payload)

    def test_repository_identity_cannot_redirect_presentation_urls(self):
        payload = self.payload()
        payload["repository"]["html_url"] = "https://example.invalid/zeppe-lin/example"
        with self.assertRaisesRegex(ValueError, "does not match"):
            normalize_push_event(payload)

    def test_unsupported_ref_is_rejected_before_dispatch(self):
        payload = self.payload()
        payload["ref"] = "refs/pull/1/head"
        with self.assertRaisesRegex(ValueError, "unsupported ref"):
            normalize_push_event(payload)


if __name__ == "__main__":
    unittest.main()
