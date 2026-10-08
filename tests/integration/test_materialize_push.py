#!/usr/bin/env python3

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "support"))
from gitrepo import GitFixture  # noqa: E402

from automation.gitrepo import GitRepository
from automation.materialize import GitMaterializationError, materialize_push


class PushMaterializationIntegrationTest(unittest.TestCase):
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

    def envelope(self, before, after, ref="refs/heads/master"):
        return {"before": before, "after": after, "ref": ref}

    def materialize(self, envelope, name="materialized.git"):
        target = self.root / name
        materialize_push(str(self.remote), envelope, target)
        return GitRepository(target)

    def test_fetches_current_refs_and_normal_update_endpoints(self):
        after = self.work.commit("normal: update")
        self.work.run("push", "-q", "origin", "master")
        repo = self.materialize(self.envelope(self.base, after))
        self.assertTrue(repo.object_exists(self.base, commit=True))
        self.assertTrue(repo.object_exists(after, commit=True))
        self.assertEqual(repo.run("rev-parse", "refs/heads/master").stdout.strip(), after)

    def test_force_push_preserves_unreachable_before_object(self):
        old_tip = self.work.commit("old: tip")
        self.work.run("push", "-q", "origin", "master")
        self.work.reset_hard(self.base)
        new_tip = self.work.commit("replacement: tip")
        self.work.run("push", "-q", "--force", "origin", "master")

        repo = self.materialize(self.envelope(old_tip, new_tip))
        self.assertTrue(repo.object_exists(old_tip, commit=True))
        self.assertTrue(repo.object_exists(new_tip, commit=True))

    def test_deleted_branch_preserves_unreachable_before_object(self):
        self.work.checkout("-b", "retired")
        tip = self.work.commit("retired: one")
        self.work.run("push", "-q", "-u", "origin", "retired")
        self.work.checkout("master")
        self.work.run("push", "-q", "origin", "--delete", "retired")

        repo = self.materialize(
            self.envelope(tip, "0" * 40, "refs/heads/retired")
        )
        self.assertTrue(repo.object_exists(tip, commit=True))
        self.assertNotEqual(
            repo.run("show-ref", "--verify", "refs/heads/retired", check=False).returncode,
            0,
        )

    def test_rejects_ext_transport_without_executing_helper(self):
        marker = self.root / "MUST-NOT-EXIST"
        remote = f"ext::sh -c 'touch {marker}'"
        with self.assertRaises(GitMaterializationError):
            materialize_push(
                remote, self.envelope(self.base, self.base), self.root / "blocked.git"
            )
        self.assertFalse(marker.exists())

    def test_refuses_nonempty_destination(self):
        target = self.root / "occupied"
        target.mkdir()
        (target / "file").write_text("occupied", encoding="utf-8")
        with self.assertRaisesRegex(GitMaterializationError, "not empty"):
            materialize_push(
                str(self.remote), self.envelope(self.base, self.base), target
            )


if __name__ == "__main__":
    unittest.main()
