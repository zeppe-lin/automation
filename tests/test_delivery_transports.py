#!/usr/bin/env python3

import socket
import smtplib
import threading
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


from automation import irc, mail


class MailTransportTest(unittest.TestCase):
    def payload(self):
        return {
            "schema": 1,
            "event_id": "release:zeppe-lin/pkgman:v6.3",
            "destination": "mail-user",
            "subject": "[release][pkgman] v6.3",
            "body": "Release body.\n",
        }

    def test_message_id_is_stable(self):
        first, _, _ = mail.build_message(
            self.payload(), "announce@example.org", "users@example.org"
        )
        second, _, _ = mail.build_message(
            self.payload(), "announce@example.org", "users@example.org"
        )
        self.assertEqual(first["Message-ID"], second["Message-ID"])
        self.assertEqual(
            first["X-Zeppe-Lin-Event-ID"], "release:zeppe-lin/pkgman:v6.3"
        )

    def test_recipient_list_is_parsed_as_addresses(self):
        _, sender, to = mail.build_message(
            self.payload(),
            "Zeppe-Lin <announce@example.org>",
            "Users <users@example.org>, dev@example.org",
        )
        self.assertEqual(sender, "announce@example.org")
        self.assertEqual(to, ["users@example.org", "dev@example.org"])

    def test_plain_smtp_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ssl or starttls"):
            mail.smtp_connection("example.invalid", 25, "plain", {})

    def test_remote_smtp_text_is_not_logged(self):
        error = smtplib.SMTPAuthenticationError(535, b"secret echoed by server")
        self.assertEqual(mail.report_transport_error(error), "SMTP authentication failed")
        self.assertNotIn("secret", mail.report_transport_error(error))


class IRCTransportTest(unittest.TestCase):
    def test_sasl_join_and_single_privmsg(self):
        client_sock, server_sock = socket.socketpair()
        commands = []

        def server():
            buffer = b""
            nick = "zpln-bot"
            try:
                while True:
                    chunk = server_sock.recv(4096)
                    if not chunk:
                        return
                    buffer += chunk
                    while b"\n" in buffer:
                        raw, buffer = buffer.split(b"\n", 1)
                        line = raw.rstrip(b"\r").decode()
                        commands.append(line)
                        if line == "CAP LS 302":
                            server_sock.sendall(b":srv CAP * LS :sasl\r\n")
                        elif line == "CAP REQ :sasl":
                            server_sock.sendall(b":srv CAP * ACK :sasl\r\n")
                        elif line == "AUTHENTICATE PLAIN":
                            server_sock.sendall(b"AUTHENTICATE +\r\n")
                        elif line.startswith("AUTHENTICATE ") and line != "AUTHENTICATE +":
                            server_sock.sendall(
                                f":srv 903 {nick} :SASL authentication successful\r\n".encode()
                            )
                        elif line == "CAP END":
                            server_sock.sendall(f":srv 001 {nick} :Welcome\r\n".encode())
                        elif line == "JOIN #zeppe-lin":
                            server_sock.sendall(
                                f":{nick}!u@h JOIN :#zeppe-lin\r\n".encode()
                            )
                        elif line.startswith("QUIT "):
                            return
            finally:
                server_sock.close()

        thread = threading.Thread(target=server)
        thread.start()
        try:
            client = irc.IRCClient(client_sock, "zpln-bot", "#zeppe-lin")
            client.authenticate("zpln-bot", "account", "secret")
            client.publish("[release] pkgman v6.3 released — https://example.invalid/r")
        finally:
            client_sock.close()
            thread.join(timeout=5)

        privmsgs = [line for line in commands if line.startswith("PRIVMSG ")]
        self.assertEqual(len(privmsgs), 1)
        self.assertEqual(
            privmsgs[0],
            "PRIVMSG #zeppe-lin :[release] pkgman v6.3 released — https://example.invalid/r",
        )


if __name__ == "__main__":
    unittest.main()
