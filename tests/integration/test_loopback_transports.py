#!/usr/bin/env python3

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUPPORT = ROOT / "tests" / "support"
import sys
sys.path.insert(0, str(SUPPORT))
from servers import IRCServer, SMTPServer  # noqa: E402

CERT = ROOT / "tests" / "fixtures" / "tls" / "localhost.crt"


class LoopbackTransportTest(unittest.TestCase):
    def test_mail_client_submits_over_verified_tls(self):
        server = SMTPServer().start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                message = Path(tmp) / "mail.json"
                message.write_text(json.dumps({
                    "schema": 1,
                    "event_id": "release:zeppe-lin/pkgman:v6.3",
                    "destination": "mail-user",
                    "subject": "[release][pkgman] v6.3",
                    "body": "Synthetic release.\n",
                }), encoding="utf-8")
                env = os.environ.copy()
                env.update({
                    "SMTP_HOST": "localhost",
                    "SMTP_PORT": str(server.port),
                    "SMTP_SECURITY": "ssl",
                    "SMTP_USERNAME": "tester",
                    "SMTP_PASSWORD": "synthetic-password",
                    "MAIL_FROM": "Zeppe-Lin Test <sender@example.invalid>",
                    "MAIL_TO": "users@example.invalid",
                    "AUTOMATION_CA_FILE": str(CERT),
                })
                result = subprocess.run(
                    [str(ROOT / "libexec" / "send-mail.py"), str(message)],
                    env=env, check=False, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
        finally:
            server.close()
        self.assertIn(b"Synthetic release.", server.message)
        self.assertNotIn("synthetic-password", "\n".join(server.commands))


    def test_transport_authentication_failures_do_not_log_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            mail_message = tmp / "mail.json"
            mail_message.write_text(json.dumps({
                "schema": 1,
                "event_id": "release:zeppe-lin/pkgman:v6.3",
                "destination": "mail-user",
                "subject": "[release][pkgman] v6.3",
                "body": "Synthetic release.\n",
            }), encoding="utf-8")
            smtp = SMTPServer(password="server-side-password").start()
            try:
                mail_env = os.environ.copy()
                mail_env.update({
                    "SMTP_HOST": "localhost",
                    "SMTP_PORT": str(smtp.port),
                    "SMTP_SECURITY": "ssl",
                    "SMTP_USERNAME": "tester",
                    "SMTP_PASSWORD": "client-secret-password",
                    "MAIL_FROM": "sender@example.invalid",
                    "MAIL_TO": "users@example.invalid",
                    "AUTOMATION_CA_FILE": str(CERT),
                })
                mail_result = subprocess.run(
                    [str(ROOT / "libexec" / "send-mail.py"), str(mail_message)],
                    env=mail_env, check=False, capture_output=True, text=True,
                )
                self.assertNotEqual(mail_result.returncode, 0)
                mail_log = mail_result.stdout + mail_result.stderr
                self.assertNotIn("client-secret-password", mail_log)
                self.assertIn("SMTP authentication failed", mail_result.stderr)
            finally:
                smtp.close()

            irc_message = tmp / "irc.txt"
            irc_message.write_text("synthetic IRC message\n", encoding="utf-8")
            irc = IRCServer(password="server-side-password").start()
            try:
                irc_env = os.environ.copy()
                irc_env.update({
                    "IRC_HOST": "localhost",
                    "IRC_PORT": str(irc.port),
                    "IRC_CHANNEL": "#zeppe-lin-test",
                    "IRC_NICK": "zpln-test",
                    "IRC_SASL_USERNAME": "tester",
                    "IRC_SASL_PASSWORD": "client-secret-password",
                    "AUTOMATION_CA_FILE": str(CERT),
                })
                irc_result = subprocess.run(
                    [str(ROOT / "libexec" / "send-irc.py"), str(irc_message)],
                    env=irc_env, check=False, capture_output=True, text=True,
                )
                self.assertNotEqual(irc_result.returncode, 0)
                irc_log = irc_result.stdout + irc_result.stderr
                self.assertNotIn("client-secret-password", irc_log)
                self.assertNotIn("Y2xpZW50LXNlY3JldC1wYXNzd29yZA==", irc_log)
                self.assertIn("IRC authentication failed: 904", irc_result.stderr)
            finally:
                irc.close()

    def test_irc_client_submits_over_verified_tls_and_sasl(self):
        server = IRCServer().start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                message = Path(tmp) / "irc.txt"
                message.write_text("[release] pkgman v6.3 released — https://example.invalid/r\n", encoding="utf-8")
                env = os.environ.copy()
                env.update({
                    "IRC_HOST": "localhost",
                    "IRC_PORT": str(server.port),
                    "IRC_CHANNEL": "#zeppe-lin-test",
                    "IRC_NICK": "zpln-test",
                    "IRC_SASL_USERNAME": "tester",
                    "IRC_SASL_PASSWORD": "synthetic-password",
                    "AUTOMATION_CA_FILE": str(CERT),
                })
                result = subprocess.run(
                    [str(ROOT / "libexec" / "send-irc.py"), str(message)],
                    env=env, check=False, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
        finally:
            server.close()
        self.assertEqual(len(server.messages), 1)
        self.assertIn("pkgman v6.3 released", server.messages[0])


if __name__ == "__main__":
    unittest.main()
