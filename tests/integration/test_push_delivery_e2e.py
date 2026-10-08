#!/usr/bin/env python3

from email import policy
from email.parser import BytesParser
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
from servers import IRCServer, SMTPServer  # noqa: E402

CERT = ROOT / "tests" / "fixtures" / "tls" / "localhost.crt"
PREPARE = ROOT / "libexec" / "prepare-push.py"
DELIVER = ROOT / "libexec" / "deliver-push.py"


class PushDeliveryEndToEndTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = GitFixture(self.root / "source")
        self.base = self.repo.commit("base: establish history")
        self.state = self.root / "state"
        subprocess.run(["git", "init", "-q", str(self.state)], check=True)
        subprocess.run(["git", "-C", str(self.state), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(self.state), "config", "user.email", "test@example.invalid"], check=True)
        (self.state / "seed").write_text("seed\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.state), "add", "seed"], check=True)
        subprocess.run(["git", "-C", str(self.state), "commit", "-qm", "seed"], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def prepare(self, after):
        event = self.root / "event.json"
        output = self.root / "delivery"
        event.write_text(json.dumps({
            "schema": 1,
            "event": "push",
            "repository": "zeppe-lin/example",
            "repository_url": "https://github.com/zeppe-lin/example",
            "ref": "refs/heads/master",
            "before": self.base,
            "after": after,
            "compare_url": "https://github.com/zeppe-lin/example/compare/local",
        }), encoding="utf-8")
        result = subprocess.run(
            [str(PREPARE), str(self.repo.path), str(event), str(output)],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return output

    def mail_env(self, server, run_id):
        env = os.environ.copy()
        env.update({
            "AUTOMATION_STATE_REPOSITORY": str(self.state),
            "AUTOMATION_RUN_ID": run_id,
            "AUTOMATION_RUN_ATTEMPT": "1",
            "SMTP_HOST": "localhost",
            "SMTP_PORT": str(server.port),
            "SMTP_SECURITY": "ssl",
            "SMTP_USERNAME": "tester",
            "SMTP_PASSWORD": "synthetic-password",
            "MAIL_FROM": "Zeppe-Lin Test <sender@example.invalid>",
            "MAIL_TO": "dev@example.invalid",
            "AUTOMATION_CA_FILE": str(CERT),
        })
        return env

    def state_refs(self):
        return subprocess.run(
            ["git", "-C", str(self.state), "for-each-ref", "--format=%(refname)", "refs/automation"],
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()

    @staticmethod
    def subjects(server):
        return [
            str(BytesParser(policy=policy.default).parsebytes(message)["Subject"])
            for message in server.messages
        ]

    def test_development_mail_is_ordered_and_uncertain_effect_blocks_tail(self):
        first = self.repo.commit("ordinary: first")
        second = self.repo.commit("ordinary: second")
        third = self.repo.commit("ordinary: third")
        output = self.prepare(third)

        first_server = SMTPServer(connections=2, disconnect_after_data=2).start()
        try:
            env = self.mail_env(first_server, "push-first")
            result = subprocess.run(
                [str(DELIVER), str(output), "mail-dev"],
                env=env, check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SMTP server disconnected", result.stderr)
        finally:
            first_server.close()

        self.assertEqual(
            self.subjects(first_server),
            [
                f"[example:master] {first[:12]}: ordinary: first",
                f"[example:master] {second[:12]}: ordinary: second",
            ],
        )
        refs = self.state_refs()
        self.assertEqual(sum(ref.endswith("/delivered") for ref in refs), 1)
        self.assertTrue(any(f"/{second}/template-1/attempts/" in ref for ref in refs))
        self.assertFalse(any(f"/{third}/template-1/attempts/" in ref for ref in refs))

        blocked_env = env.copy()
        blocked_env["SMTP_PORT"] = "1"
        blocked_env["AUTOMATION_RUN_ID"] = "push-blocked"
        blocked = subprocess.run(
            [str(DELIVER), str(output), "mail-dev"],
            env=blocked_env, check=False, capture_output=True, text=True,
        )
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("unresolved prior delivery attempt", blocked.stderr)
        self.assertFalse(any(f"/{third}/template-1/attempts/" in ref for ref in self.state_refs()))

        replay_server = SMTPServer(connections=2).start()
        try:
            replay_env = self.mail_env(replay_server, "push-replay")
            replay = subprocess.run(
                [str(DELIVER), str(output), "mail-dev", "--force"],
                env=replay_env, check=False, capture_output=True, text=True,
            )
            self.assertEqual(replay.returncode, 0, replay.stderr)
            self.assertIn("delivered 2, already delivered 1", replay.stdout)
        finally:
            replay_server.close()

        self.assertEqual(
            self.subjects(replay_server),
            [
                f"[example:master] {second[:12]}: ordinary: second",
                f"[example:master] {third[:12]}: ordinary: third",
            ],
        )
        self.assertEqual(sum(ref.endswith("/delivered") for ref in self.state_refs()), 3)

    def test_user_mail_delivers_only_semantically_routed_commits(self):
        self.repo.commit("ordinary: internal")
        tagged = self.repo.commit(
            "[news] service: administrator action\n\n"
            "Affected: test systems\n"
            "Action: restart service\n"
            "News: .news/test-service\n"
        )
        last = self.repo.commit("ordinary: follow-up")
        output = self.prepare(last)

        server = SMTPServer().start()
        try:
            env = self.mail_env(server, "push-user")
            env["MAIL_TO"] = "users@example.invalid"
            result = subprocess.run(
                [str(DELIVER), str(output), "mail-user"],
                env=env, check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        finally:
            server.close()

        self.assertEqual(len(server.messages), 1)
        self.assertEqual(
            self.subjects(server),
            ["[news][example] service: administrator action"],
        )
        body = BytesParser(policy=policy.default).parsebytes(server.messages[0]).get_body(
            preferencelist=("plain",)
        ).get_content()
        self.assertIn("Action: restart service", body)
        self.assertIn(tagged, body)

    def test_irc_push_summary_uses_real_tls_sasl_and_is_duplicate_guarded(self):
        after = self.repo.commit("ordinary: visible on IRC")
        output = self.prepare(after)

        server = IRCServer().start()
        try:
            env = os.environ.copy()
            env.update({
                "AUTOMATION_STATE_REPOSITORY": str(self.state),
                "AUTOMATION_RUN_ID": "push-irc",
                "AUTOMATION_RUN_ATTEMPT": "1",
                "IRC_HOST": "localhost",
                "IRC_PORT": str(server.port),
                "IRC_CHANNEL": "#zeppe-lin-test",
                "IRC_NICK": "zpln-test",
                "IRC_SASL_USERNAME": "tester",
                "IRC_SASL_PASSWORD": "synthetic-password",
                "AUTOMATION_CA_FILE": str(CERT),
            })
            result = subprocess.run(
                [str(DELIVER), str(output), "irc"],
                env=env, check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        finally:
            server.close()

        self.assertEqual(len(server.messages), 1)
        self.assertIn("ordinary: visible on IRC", server.messages[0])

        duplicate_env = env.copy()
        duplicate_env["IRC_PORT"] = "1"
        duplicate_env["AUTOMATION_RUN_ID"] = "push-irc-duplicate"
        duplicate = subprocess.run(
            [str(DELIVER), str(output), "irc"],
            env=duplicate_env, check=False, capture_output=True, text=True,
        )
        self.assertEqual(duplicate.returncode, 0, duplicate.stderr)
        self.assertIn("already delivered 1", duplicate.stdout)


if __name__ == "__main__":
    unittest.main()
