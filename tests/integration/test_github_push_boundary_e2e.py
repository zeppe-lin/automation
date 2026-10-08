#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "support"))
from gitrepo import GitFixture  # noqa: E402

QUEUE = ROOT / "libexec" / "queue-github-push.py"
PREPARE = ROOT / "libexec" / "prepare-github-push.py"


class GitHubPushBoundaryEndToEndTest(unittest.TestCase):
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

    def fake_gh(self):
        captured = self.root / "repository-dispatch-request.json"
        executable = self.root / "gh"
        executable.write_text(
            "#!/bin/sh\n"
            "previous=''\n"
            "for arg in \"$@\"; do\n"
            "  if [ \"$previous\" = '--input' ]; then cp \"$arg\" \"$FAKE_GH_INPUT\"; fi\n"
            "  previous=$arg\n"
            "done\n"
            "exit 0\n",
            encoding="utf-8",
        )
        executable.chmod(0o755)
        return captured

    def push_payload(self, before, after, commits):
        return {
            "ref": "refs/heads/master",
            "before": before,
            "after": after,
            "created": False,
            "deleted": False,
            "forced": False,
            "compare": "https://github.com/zeppe-lin/example/compare/provider-data",
            "repository": {
                "full_name": "zeppe-lin/example",
                "html_url": "https://github.com/zeppe-lin/example",
            },
            "commits": commits,
        }

    def test_source_dispatch_and_central_prepare_share_only_coordinates(self):
        marker = self.root / "MUST-NOT-EXIST"
        commits = [
            self.work.commit(f"ordinary: change {index}")
            for index in range(12)
        ]
        self.work.run("push", "-q", "origin", "master")
        provider = self.push_payload(
            self.base,
            commits[-1],
            [
                {
                    "id": commits[-1],
                    "message": f"$(touch {marker}) provider text must not survive",
                }
            ],
        )
        source_event = self.root / "github-event.json"
        source_event.write_text(json.dumps(provider), encoding="utf-8")

        captured = self.fake_gh()
        env = os.environ.copy()
        env["PATH"] = str(self.root) + os.pathsep + env["PATH"]
        env["GH_TOKEN"] = "synthetic-dispatch-token"
        env["FAKE_GH_INPUT"] = str(captured)
        queued = subprocess.run(
            [str(QUEUE), str(source_event)],
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(queued.returncode, 0, queued.stderr)
        request = json.loads(captured.read_text(encoding="utf-8"))
        envelope = request["client_payload"]["envelope"]
        self.assertNotIn("commits", envelope)
        self.assertNotIn("forced", envelope)
        self.assertNotIn("synthetic-dispatch-token", captured.read_text(encoding="utf-8"))

        central_event = self.root / "central-event.json"
        central_event.write_text(
            json.dumps(
                {
                    "action": request["event_type"],
                    "client_payload": request["client_payload"],
                }
            ),
            encoding="utf-8",
        )
        output = self.root / "delivery"
        result = subprocess.run(
            [
                str(PREPARE),
                str(central_event),
                str(self.root / "source.git"),
                str(output),
                "--remote",
                str(self.remote),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual([item["sha"] for item in manifest["commits"]], commits)
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
