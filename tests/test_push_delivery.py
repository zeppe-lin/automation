#!/usr/bin/env python3

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from automation import gitstate
from automation.artifacts import write_push_artifacts
from automation.delivery import deliver_push
from automation.policy import classify_push


class PushDeliveryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state = self.root / "state"
        subprocess.run(["git", "init", "-q", str(self.state)], check=True)
        subprocess.run(["git", "-C", str(self.state), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(self.state), "config", "user.email", "test@example.invalid"], check=True)
        (self.state / "seed").write_text("seed\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.state), "add", "seed"], check=True)
        subprocess.run(["git", "-C", str(self.state), "commit", "-qm", "seed"], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def environment(self):
        return {
            "AUTOMATION_STATE_REPOSITORY": str(self.state),
            "AUTOMATION_RUN_ID": "push-unit",
            "AUTOMATION_RUN_ATTEMPT": "1",
            "SMTP_HOST": "example.invalid",
            "MAIL_FROM": "sender@example.invalid",
            "MAIL_TO": "dev@example.invalid",
        }

    def manifest(self):
        sha = "a" * 40
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
            "commit_count": 1,
            "commits": [{
                "sha": sha,
                "short_sha": sha[:12],
                "parents": [],
                "title": "ordinary: one",
                "body": "",
                "author_name": "Test",
                "author_email": "test@example.invalid",
                "authored_at": "2026-10-08T00:00:00Z",
                "trailers": {},
                "diffstat": " one | 1 +",
                "commit_url": "https://github.com/zeppe-lin/example/commit/" + sha,
            }],
        })

    def test_mail_payload_must_match_delivery_plan_before_claim(self):
        output = self.root / "delivery"
        write_push_artifacts(self.manifest(), output)
        payload_path = output / "mail-dev/0001.json"
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload["item_id"] = "b" * 40
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        with mock.patch.dict(os.environ, self.environment(), clear=True):
            with self.assertRaisesRegex(ValueError, "item_id does not match"):
                deliver_push(output, "mail-dev", env=os.environ)

        refs = subprocess.run(
            ["git", "-C", str(self.state), "for-each-ref", "--format=%(refname)", "refs/automation"],
            check=True, capture_output=True, text=True,
        ).stdout
        self.assertEqual(refs, "")


    def test_delivery_plan_cannot_escape_artifact_directory(self):
        output = self.root / "delivery"
        write_push_artifacts(self.manifest(), output)
        plan_path = output / "delivery-plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["deliveries"]["mail-dev"][0]["artifact"] = "../outside.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "escapes delivery directory"):
            deliver_push(output, "mail-dev", env={})

        refs = subprocess.run(
            ["git", "-C", str(self.state), "for-each-ref", "--format=%(refname)", "refs/automation"],
            check=True, capture_output=True, text=True,
        ).stdout
        self.assertEqual(refs, "")

    def test_empty_user_route_needs_no_transport_credentials_or_state(self):
        output = self.root / "delivery"
        write_push_artifacts(self.manifest(), output)
        status, message = deliver_push(output, "mail-user", env={})
        self.assertEqual(status, 0)
        self.assertEqual(message, "mail-user: nothing to deliver")



    def test_manifest_policy_projection_is_revalidated_before_claim(self):
        output = self.root / "delivery-policy"
        write_push_artifacts(self.manifest(), output)
        manifest_path = output / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["commits"][0]["classification"]["destinations"].append("mail-user")
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        with mock.patch.dict(os.environ, self.environment(), clear=True):
            with self.assertRaisesRegex(ValueError, "classification is not derived"):
                deliver_push(output, "mail-dev", env=os.environ)

        refs = subprocess.run(
            ["git", "-C", str(self.state), "for-each-ref", "--format=%(refname)", "refs/automation"],
            check=True, capture_output=True, text=True,
        ).stdout
        self.assertEqual(refs, "")

    def test_delivery_plan_order_is_bound_to_manifest_before_claim(self):
        manifest = self.manifest()
        second = dict(manifest["commits"][0])
        second["sha"] = "b" * 40
        second["short_sha"] = second["sha"][:12]
        second["title"] = "ordinary: two"
        second["commit_url"] = "https://github.com/zeppe-lin/example/commit/" + second["sha"]
        manifest["commits"].append(second)
        manifest["commit_count"] = 2
        manifest = classify_push(manifest)

        output = self.root / "delivery-order"
        write_push_artifacts(manifest, output)
        plan_path = output / "delivery-plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["deliveries"]["mail-dev"].reverse()
        plan_path.write_text(json.dumps(plan), encoding="utf-8")

        with mock.patch.dict(os.environ, self.environment(), clear=True):
            with self.assertRaisesRegex(ValueError, "order does not match"):
                deliver_push(output, "mail-dev", env=os.environ)

        refs = subprocess.run(
            ["git", "-C", str(self.state), "for-each-ref", "--format=%(refname)", "refs/automation"],
            check=True, capture_output=True, text=True,
        ).stdout
        self.assertEqual(refs, "")

    def test_delivery_plan_event_identity_is_bound_to_manifest_before_claim(self):
        output = self.root / "delivery-identity"
        write_push_artifacts(self.manifest(), output)
        plan_path = output / "delivery-plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["deliveries"]["mail-dev"][0]["event_id"] += ":forged"
        payload_path = output / "mail-dev/0001.json"
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload["event_id"] = plan["deliveries"]["mail-dev"][0]["event_id"]
        payload_path.write_text(json.dumps(payload), encoding="utf-8")
        plan_path.write_text(json.dumps(plan), encoding="utf-8")

        with mock.patch.dict(os.environ, self.environment(), clear=True):
            with self.assertRaisesRegex(ValueError, "event ID does not match manifest item"):
                deliver_push(output, "mail-dev", env=os.environ)

    def test_push_key_separates_events_and_template_versions(self):
        manifest = self.manifest()
        one = gitstate.push_key(
            manifest["repository"], manifest["event_id"], "mail-dev", "a" * 40, 1
        )
        other_event = gitstate.push_key(
            manifest["repository"], manifest["event_id"] + "-other", "mail-dev", "a" * 40, 1
        )
        other_template = gitstate.push_key(
            manifest["repository"], manifest["event_id"], "mail-dev", "a" * 40, 2
        )
        self.assertNotEqual(one.ref_base, other_event.ref_base)
        self.assertNotEqual(one.ref_base, other_template.ref_base)
        self.assertNotIn("refs/heads/master", one.ref_base)


if __name__ == "__main__":
    unittest.main()
