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

COLLECT = ROOT / "libexec" / "collect-push.py"


class PushCollectionIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = GitFixture(self.root / "repository")
        self.base = self.repo.commit("base: establish history")

    def tearDown(self):
        self.tmp.cleanup()

    def envelope(self, before, after, ref="refs/heads/master"):
        return {
            "schema": 1,
            "event": "push",
            "repository": "zeppe-lin/example",
            "repository_url": "https://github.com/zeppe-lin/example",
            "ref": ref,
            "before": before,
            "after": after,
            "compare_url": "https://github.com/zeppe-lin/example/compare/example",
        }

    def collect(self, envelope):
        event = self.root / "event.json"
        output = self.root / "collected.json"
        event.write_text(json.dumps(envelope), encoding="utf-8")
        result = subprocess.run(
            [str(COLLECT), str(self.repo.path), str(event), str(output)],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(output.read_text(encoding="utf-8"))

    def test_commit_text_is_data_not_shell_source(self):
        marker = self.root / "SHOULD-NOT-EXIST"
        after = self.repo.commit(
            f"ordinary: $(touch {marker})\n\n`touch {marker}`\n::warning::not-a-command"
        )
        manifest = self.collect(self.envelope(self.base, after))
        self.assertFalse(marker.exists())
        self.assertIn("$(touch", manifest["commits"][0]["title"])

    def test_new_branch_collects_only_commits_unique_to_that_branch(self):
        self.repo.checkout("-b", "feature")
        first = self.repo.commit("feature: one")
        second = self.repo.commit("feature: two")
        manifest = self.collect(
            self.envelope("0" * 40, second, "refs/heads/feature")
        )
        self.assertEqual(manifest["change"], "create")
        self.assertEqual([c["sha"] for c in manifest["commits"]], [first, second])

    def test_new_branch_ignores_equivalent_remote_tracking_target(self):
        self.repo.checkout("-b", "feature")
        first = self.repo.commit("feature: one")
        second = self.repo.commit("feature: two")
        self.repo.run("update-ref", "refs/remotes/origin/feature", second)
        manifest = self.collect(
            self.envelope("0" * 40, second, "refs/heads/feature")
        )
        self.assertEqual([c["sha"] for c in manifest["commits"]], [first, second])

    def test_new_branch_pointing_at_existing_commit_has_no_new_commits(self):
        self.repo.branch("alias", self.base)
        manifest = self.collect(
            self.envelope("0" * 40, self.base, "refs/heads/alias")
        )
        self.assertEqual(manifest["commits"], [])

    def test_deleted_branch_is_explicit_and_does_not_replay_old_commits(self):
        self.repo.checkout("-b", "retired")
        tip = self.repo.commit("retired: temporary work")
        self.repo.checkout("master")
        self.repo.delete_branch("retired")
        manifest = self.collect(
            self.envelope(tip, "0" * 40, "refs/heads/retired")
        )
        self.assertEqual(manifest["change"], "delete")
        self.assertEqual(manifest["commits"], [])

    def test_empty_update_has_no_commits(self):
        manifest = self.collect(self.envelope(self.base, self.base))
        self.assertEqual(manifest["change"], "update")
        self.assertFalse(manifest["forced"])
        self.assertEqual(manifest["commit_count"], 0)

    def test_force_push_is_observed_from_git_graph(self):
        old_one = self.repo.commit("old: one")
        old_tip = self.repo.commit("old: two")
        self.repo.reset_hard(self.base)
        new_tip = self.repo.commit("replacement: one")
        manifest = self.collect(self.envelope(old_tip, new_tip))
        self.assertTrue(manifest["forced"])
        self.assertEqual([c["sha"] for c in manifest["commits"]], [new_tip])
        self.assertNotIn(old_one, [c["sha"] for c in manifest["commits"]])

    def test_tag_creation_and_deletion_do_not_replay_commit_history(self):
        tag_oid = self.repo.tag("v1.0", annotated=True)
        created = self.collect(
            self.envelope("0" * 40, tag_oid, "refs/tags/v1.0")
        )
        self.assertEqual((created["ref_kind"], created["change"]), ("tag", "create"))
        self.assertEqual(created["commits"], [])

        self.repo.run("tag", "-d", "v1.0")
        deleted = self.collect(
            self.envelope(tag_oid, "0" * 40, "refs/tags/v1.0")
        )
        self.assertEqual((deleted["ref_kind"], deleted["change"]), ("tag", "delete"))
        self.assertEqual(deleted["commits"], [])

    def test_large_push_is_enumerated_from_git_not_webhook_payload_limits(self):
        commits = [self.repo.commit(f"bulk: change {index}") for index in range(30)]
        manifest = self.collect(self.envelope(self.base, commits[-1]))
        self.assertEqual(manifest["commit_count"], 30)
        self.assertEqual([c["sha"] for c in manifest["commits"]], commits)

    def test_merge_and_revert_commits_remain_visible_history(self):
        self.repo.checkout("-b", "topic")
        topic = self.repo.commit("topic: add change", "topic.txt")
        self.repo.checkout("master")
        main = self.repo.commit("main: parallel change", "main.txt")
        self.repo.run("merge", "--no-ff", "-m", "merge: topic", "topic")
        merge = self.repo.oid()
        self.repo.run("revert", "--no-edit", topic)
        revert = self.repo.oid()

        manifest = self.collect(self.envelope(self.base, revert))
        shas = [c["sha"] for c in manifest["commits"]]
        for sha in (main, topic, merge, revert):
            self.assertIn(sha, shas)
        self.assertLess(shas.index(merge), shas.index(revert))
        merge_commit = next(c for c in manifest["commits"] if c["sha"] == merge)
        self.assertEqual(len(merge_commit["parents"]), 2)

    def test_missing_before_commit_fails_closed(self):
        after = self.repo.commit("ordinary: local tip")
        event = self.root / "missing-before.json"
        output = self.root / "must-not-exist.json"
        event.write_text(json.dumps(self.envelope("f" * 40, after)), encoding="utf-8")
        result = subprocess.run(
            [str(COLLECT), str(self.repo.path), str(event), str(output)],
            check=False, capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unavailable locally", result.stderr)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
