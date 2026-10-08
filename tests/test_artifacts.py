#!/usr/bin/env python3

import json
import tempfile
import unittest
from pathlib import Path

from automation.artifacts import write_push_artifacts
from automation.policy import classify_push


class PushArtifactTest(unittest.TestCase):
    def manifest(self):
        return classify_push({
            "schema": 1,
            "event": "push",
            "event_id": "push:zeppe-lin/example:refs/heads/master:" + "1" * 40 + ":" + "2" * 40,
            "repository": "zeppe-lin/example",
            "repository_url": "https://github.com/zeppe-lin/example",
            "ref": "refs/heads/master",
            "ref_kind": "branch",
            "change": "update",
            "before": "1" * 40,
            "after": "2" * 40,
            "forced": False,
            "compare_url": "https://github.com/zeppe-lin/example/compare/x",
            "commit_count": 2,
            "commits": [
                {
                    "sha": "a" * 40,
                    "short_sha": "a" * 12,
                    "parents": [],
                    "title": "ordinary: one",
                    "body": "",
                    "author_name": "Test",
                    "author_email": "test@example.invalid",
                    "authored_at": "2026-10-08T00:00:00Z",
                    "trailers": {},
                    "diffstat": " one | 1 +",
                    "commit_url": "https://github.com/zeppe-lin/example/commit/" + "a" * 40,
                },
                {
                    "sha": "b" * 40,
                    "short_sha": "b" * 12,
                    "parents": ["a" * 40],
                    "title": "[news] operator: act",
                    "body": "Affected: test\nAction: act\nNews: .news/test",
                    "author_name": "Test",
                    "author_email": "test@example.invalid",
                    "authored_at": "2026-10-08T00:00:00Z",
                    "trailers": {
                        "Affected": ["test"],
                        "Action": ["act"],
                        "News": [".news/test"],
                    },
                    "diffstat": " two | 1 +",
                    "commit_url": "https://github.com/zeppe-lin/example/commit/" + "b" * 40,
                },
            ],
        })

    def test_push_artifact_plan_preserves_destination_order_and_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            manifest = self.manifest()
            write_push_artifacts(manifest, output)
            plan = json.loads((output / "delivery-plan.json").read_text(encoding="utf-8"))

            self.assertEqual(
                [entry["item_id"] for entry in plan["deliveries"]["mail-dev"]],
                ["a" * 40, "b" * 40],
            )
            self.assertEqual(
                [entry["item_id"] for entry in plan["deliveries"]["mail-user"]],
                ["b" * 40],
            )
            self.assertEqual(plan["deliveries"]["irc"][0]["item_id"], "push")
            self.assertEqual(plan["deliveries"]["mail-dev"][0]["template"], 1)
            self.assertEqual(plan["deliveries"]["mail-user"][0]["template"], 1)
            self.assertEqual(plan["deliveries"]["irc"][0]["template"], 2)
            payload = json.loads((output / "mail-dev/0001.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["item_id"], "a" * 40)
            self.assertEqual(payload["template"], 1)


if __name__ == "__main__":
    unittest.main()
