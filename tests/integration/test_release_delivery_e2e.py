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
from servers import SMTPServer  # noqa: E402

CERT = ROOT / "tests" / "fixtures" / "tls" / "localhost.crt"
PREPARE = ROOT / "libexec" / "prepare-release.py"
DELIVER = ROOT / "libexec" / "deliver-release.py"


class ReleaseDeliveryEndToEndTest(unittest.TestCase):
    def init_state_repo(self, directory):
        repo = Path(directory) / "state"
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
        (repo / "seed").write_text("seed\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "seed"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "seed"], check=True)
        return repo

    def test_prepare_deliver_and_duplicate_guard_are_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            state = self.init_state_repo(tmpdir)
            release = tmpdir / "release.json"
            output = tmpdir / "delivery"
            release.write_text(json.dumps({
                "tag_name": "v6.3",
                "name": "pkgman v6.3",
                "draft": False,
                "prerelease": False,
                "html_url": "https://github.com/zeppe-lin/pkgman/releases/tag/v6.3",
                "published_at": "2026-10-08T12:00:00Z",
                "body": "### Changes\n\n* Synthetic local release.\n",
            }), encoding="utf-8")

            prepared = subprocess.run(
                [str(PREPARE), "zeppe-lin/pkgman", "v6.3", str(output), "--release-json", str(release)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(prepared.returncode, 0, prepared.stderr)

            server = SMTPServer().start()
            try:
                env = os.environ.copy()
                env.update({
                    "AUTOMATION_STATE_REPOSITORY": str(state),
                    "AUTOMATION_RUN_ID": "local-e2e",
                    "AUTOMATION_RUN_ATTEMPT": "1",
                    "SMTP_HOST": "localhost",
                    "SMTP_PORT": str(server.port),
                    "SMTP_SECURITY": "ssl",
                    "SMTP_USERNAME": "tester",
                    "SMTP_PASSWORD": "synthetic-password",
                    "MAIL_FROM": "Zeppe-Lin Test <sender@example.invalid>",
                    "MAIL_TO": "users@example.invalid",
                    "AUTOMATION_CA_FILE": str(CERT),
                })
                delivered = subprocess.run(
                    [str(DELIVER), str(output), "mail-user"],
                    env=env, check=False, capture_output=True, text=True,
                )
                self.assertEqual(delivered.returncode, 0, delivered.stderr)
            finally:
                server.close()

            refs = subprocess.run(
                ["git", "-C", str(state), "for-each-ref", "--format=%(refname)", "refs/automation"],
                check=True, capture_output=True, text=True,
            ).stdout
            self.assertIn("/attempts/local-e2e-1", refs)
            self.assertIn("/delivered", refs)
            self.assertIn(b"Synthetic local release.", server.message)

            duplicate = subprocess.run(
                [str(DELIVER), str(output), "mail-user"],
                env=env, check=False, capture_output=True, text=True,
            )
            self.assertEqual(duplicate.returncode, 0, duplicate.stderr)
            self.assertIn("already delivered", duplicate.stdout)


if __name__ == "__main__":
    unittest.main()
