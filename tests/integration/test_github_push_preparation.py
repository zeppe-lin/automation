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

PREPARE = ROOT / "libexec" / "prepare-github-push.py"


class GitHubPushPreparationIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.remote = self.root / "remote.git"
        subprocess.run(["git", "init", "--bare", "--quiet", str(self.remote)], check=True)
        self.work = GitFixture(self.root / "work")
        self.work.run("remote", "add", "origin", str(self.remote))
        self.base = self.work.commit("base: establish history")
        self.work.run("push", "-q", "-u", "origin", "master")

    def tearDown(self):
        self.tmp.cleanup()

    def github_push(self, before, after, ref="refs/heads/master", **extra):
        zero = "0" * len(before)
        payload = {
            "ref": ref,
            "before": before,
            "after": after,
            "created": before == zero,
            "deleted": after == zero,
            "forced": False,
            "compare": "https://github.com/zeppe-lin/example/compare/provider-data",
            "repository": {
                "full_name": "zeppe-lin/example",
                "html_url": "https://github.com/zeppe-lin/example",
            },
            # Provider commit data is deliberately incomplete.  The central
            # preparation must recover complete history from Git.
            "commits": [],
        }
        payload.update(extra)
        return payload

    def dispatch(self, push):
        # Exercise the real queue-side provider normalizer by invoking its
        # importable interface, then model the event GitHub delivers centrally.
        from automation.providers.github import normalize_push_event, repository_dispatch_payload

        queued = repository_dispatch_payload(normalize_push_event(push))
        return {"action": queued["event_type"], "client_payload": queued["client_payload"]}

    def prepare(self, push, name="case"):
        event = self.root / f"{name}-dispatch.json"
        source = self.root / f"{name}-source.git"
        output = self.root / f"{name}-delivery"
        event.write_text(json.dumps(self.dispatch(push)), encoding="utf-8")
        result = subprocess.run(
            [
                str(PREPARE),
                str(event),
                str(source),
                str(output),
                "--remote",
                str(self.remote),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads((output / "manifest.json").read_text(encoding="utf-8")), output

    def test_normal_push_ignores_provider_commit_list_and_preserves_order(self):
        commits = [self.work.commit(f"ordinary: change {index}") for index in range(8)]
        self.work.run("push", "-q", "origin", "master")
        push = self.github_push(self.base, commits[-1])
        push["commits"] = [{"id": commits[-1], "message": "only one provider entry"}]
        manifest, output = self.prepare(push, "normal")
        self.assertEqual([item["sha"] for item in manifest["commits"]], commits)
        self.assertEqual(len(list((output / "mail-dev").glob("*.json"))), 8)

    def test_force_push_fetches_pre_push_object_and_derives_forced_from_git(self):
        old_tip = self.work.commit("old: tip")
        self.work.run("push", "-q", "origin", "master")
        self.work.reset_hard(self.base)
        new_tip = self.work.commit("replacement: tip")
        self.work.run("push", "-q", "--force", "origin", "master")
        push = self.github_push(old_tip, new_tip, forced=False)
        manifest, _ = self.prepare(push, "force")
        self.assertTrue(manifest["forced"])
        self.assertEqual([item["sha"] for item in manifest["commits"]], [new_tip])

    def test_deleted_branch_is_prepared_after_ref_has_disappeared(self):
        self.work.checkout("-b", "retired")
        tip = self.work.commit("retired: work")
        self.work.run("push", "-q", "-u", "origin", "retired")
        self.work.checkout("master")
        self.work.run("push", "-q", "origin", "--delete", "retired")
        manifest, output = self.prepare(
            self.github_push(tip, "0" * 40, "refs/heads/retired"), "delete"
        )
        self.assertEqual(manifest["change"], "delete")
        self.assertEqual(manifest["commits"], [])
        self.assertFalse((output / "irc.txt").exists())

    def test_new_branch_and_tag_events_use_real_remote_objects(self):
        self.work.checkout("-b", "feature")
        one = self.work.commit("feature: one")
        two = self.work.commit("feature: two")
        self.work.run("push", "-q", "-u", "origin", "feature")
        branch, _ = self.prepare(
            self.github_push("0" * 40, two, "refs/heads/feature"), "branch-create"
        )
        self.assertEqual([item["sha"] for item in branch["commits"]], [one, two])

        tag_oid = self.work.tag("v1.0", annotated=True)
        self.work.run("push", "-q", "origin", "refs/tags/v1.0")
        tag, _ = self.prepare(
            self.github_push("0" * 40, tag_oid, "refs/tags/v1.0"), "tag-create"
        )
        self.assertEqual((tag["ref_kind"], tag["change"]), ("tag", "create"))
        self.assertEqual(tag["commits"], [])

    def test_large_push_is_not_bounded_by_github_commits_array(self):
        commits = [self.work.commit(f"bulk: {index}") for index in range(40)]
        self.work.run("push", "-q", "origin", "master")
        push = self.github_push(self.base, commits[-1])
        push["commits"] = [{"id": oid, "message": "truncated"} for oid in commits[:2]]
        manifest, _ = self.prepare(push, "large")
        self.assertEqual(manifest["commit_count"], 40)
        self.assertEqual([item["sha"] for item in manifest["commits"]], commits)


if __name__ == "__main__":
    unittest.main()
