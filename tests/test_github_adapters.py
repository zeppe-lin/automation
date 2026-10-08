#!/usr/bin/env python3

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class GitHubAdapterTest(unittest.TestCase):
    def fake_gh(self, directory):
        log = Path(directory) / "gh.log"
        script = Path(directory) / "gh"
        script.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" >>\"$FAKE_GH_LOG\"\n"
            "previous=''\n"
            "for arg in \"$@\"; do\n"
            "  if [ \"$previous\" = '--input' ] && [ -n \"${FAKE_GH_INPUT:-}\" ]; then cp \"$arg\" \"$FAKE_GH_INPUT\"; fi\n"
            "  previous=$arg\n"
            "done\n"
            "if [ \"$1 $2\" = 'release view' ]; then\n"
            "  code=${FAKE_RELEASE_EXISTS:-1}\n"
            "  if [ \"$code\" -eq 0 ]; then printf '%s\\n' \"$FAKE_RELEASE_JSON\"; fi\n"
            "  exit \"$code\"\n"
            "fi\n"
            "exit 0\n",
            encoding="utf-8",
        )
        script.chmod(0o755)
        return log

    def environment(self, directory, log):
        env = os.environ.copy()
        env["PATH"] = str(directory) + os.pathsep + env["PATH"]
        env["FAKE_GH_LOG"] = str(log)
        env["GH_TOKEN"] = "synthetic-token"
        return env

    def test_publish_command_is_locally_testable_with_fake_gh(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            log = self.fake_gh(tmpdir)
            notes = tmpdir / "notes.md"
            notes.write_text("Release notes.\n", encoding="utf-8")
            result = subprocess.run(
                [str(ROOT / "libexec" / "publish-github-release.py"), "v6.3", str(notes), "--name", "pkgman v6.3"],
                env=self.environment(tmpdir, log), check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            commands = log.read_text(encoding="utf-8")
            self.assertIn("release view v6.3", commands)
            self.assertIn("release create v6.3", commands)
            self.assertNotIn("synthetic-token", commands)



    def test_existing_release_must_match_news_before_idempotent_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            log = self.fake_gh(tmpdir)
            notes = tmpdir / "notes.md"
            notes.write_text("Release notes.\n", encoding="utf-8")
            env = self.environment(tmpdir, log)
            env["FAKE_RELEASE_EXISTS"] = "0"
            env["FAKE_RELEASE_JSON"] = json.dumps({
                "tagName": "v6.3",
                "name": "pkgman v6.3",
                "body": "Release notes.\n",
                "isDraft": False,
                "isPrerelease": False,
            })
            result = subprocess.run(
                [str(ROOT / "libexec" / "publish-github-release.py"), "v6.3", str(notes), "--name", "pkgman v6.3"],
                env=env, check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("already published", result.stdout)
            self.assertNotIn("release create", log.read_text(encoding="utf-8"))

            env["FAKE_RELEASE_JSON"] = json.dumps({
                "tagName": "v6.3",
                "name": "pkgman v6.3",
                "body": "Stale notes.\n",
                "isDraft": False,
                "isPrerelease": False,
            })
            mismatch = subprocess.run(
                [str(ROOT / "libexec" / "publish-github-release.py"), "v6.3", str(notes), "--name", "pkgman v6.3"],
                env=env, check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(mismatch.returncode, 0)
            self.assertIn("notes differ from NEWS", mismatch.stderr)

    def test_push_dispatch_contains_only_normalized_coordinates(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            log = self.fake_gh(tmpdir)
            captured = tmpdir / "dispatch.json"
            env = self.environment(tmpdir, log)
            env["FAKE_GH_INPUT"] = str(captured)
            source = ROOT / "tests" / "fixtures" / "github" / "push-normal.json"
            result = subprocess.run(
                [str(ROOT / "libexec" / "queue-github-push.py"), str(source)],
                env=env, check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(captured.read_text(encoding="utf-8"))
            self.assertEqual(payload["event_type"], "push-observed")
            envelope = payload["client_payload"]["envelope"]
            self.assertEqual(envelope["repository"], "zeppe-lin/example")
            self.assertNotIn("commits", envelope)
            self.assertNotIn("forced", envelope)
            self.assertNotIn("synthetic-token", captured.read_text(encoding="utf-8"))
            self.assertNotIn("synthetic-token", log.read_text(encoding="utf-8"))

    def test_dispatch_payload_is_data_not_shell_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            log = self.fake_gh(tmpdir)
            env = self.environment(tmpdir, log)
            result = subprocess.run(
                [str(ROOT / "libexec" / "queue-release-delivery.py"), "zeppe-lin/pkgman", "v6.3"],
                env=env, check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("repos/zeppe-lin/automation/dispatches", log.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
