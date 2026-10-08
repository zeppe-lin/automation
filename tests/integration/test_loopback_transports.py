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
