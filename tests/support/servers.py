#!/usr/bin/env python3
"""Loopback TLS protocol fixtures for local transport qualification.

These servers are test infrastructure only. They bind to localhost, use a
repository-owned test certificate/private key, accept synthetic credentials,
and never contact external services.
"""

import base64
import socket
import ssl
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CERT = ROOT / "fixtures" / "tls" / "localhost.crt"
KEY = ROOT / "fixtures" / "tls" / "localhost.key"


def server_context():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(CERT, KEY)
    return context


class TLSFixture:
    def __init__(self, connections=1):
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.thread = None
        self.error = None
        self.connections = connections
        self.connection_number = 0

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return self

    def close(self):
        self.sock.close()
        if self.thread:
            self.thread.join(timeout=5)
        if self.error:
            raise self.error

    def _run(self):
        try:
            for index in range(1, self.connections + 1):
                raw, _ = self.sock.accept()
                self.connection_number = index
                with server_context().wrap_socket(raw, server_side=True) as conn:
                    self.handle(conn)
        except Exception as error:  # fixture must report thread failures
            self.error = error


class SMTPServer(TLSFixture):
    def __init__(
        self,
        username="tester",
        password="synthetic-password",
        connections=1,
        disconnect_after_data=None,
    ):
        super().__init__(connections=connections)
        self.username = username
        self.password = password
        self.message = b""
        self.messages = []
        self.commands = []
        self.disconnect_after_data = disconnect_after_data

    def handle(self, conn):
        file = conn.makefile("rwb", buffering=0)
        file.write(b"220 localhost test SMTP\r\n")
        auth_stage = 0
        data_mode = False
        data = []
        while True:
            line = file.readline()
            if not line:
                return
            stripped = line.rstrip(b"\r\n")
            if data_mode:
                if stripped == b".":
                    self.message = b"\n".join(data) + b"\n"
                    self.messages.append(self.message)
                    if self.disconnect_after_data == self.connection_number:
                        return
                    file.write(b"250 queued\r\n")
                    data_mode = False
                    continue
                if stripped.startswith(b".."):
                    stripped = stripped[1:]
                data.append(stripped)
                continue

            text = stripped.decode("utf-8", "replace")
            self.commands.append(text)
            upper = text.upper()
            if upper.startswith("EHLO"):
                file.write(b"250-localhost\r\n250-AUTH PLAIN LOGIN\r\n250 SIZE 1048576\r\n")
            elif upper.startswith("AUTH PLAIN"):
                parts = text.split(" ", 2)
                token = parts[2] if len(parts) == 3 else ""
                if not token:
                    file.write(b"334 \r\n")
                    auth_stage = 1
                    continue
                self._plain_auth(file, token)
            elif upper == "AUTH LOGIN":
                file.write(b"334 VXNlcm5hbWU6\r\n")
                auth_stage = 2
            elif auth_stage == 1:
                auth_stage = 0
                self._plain_auth(file, text)
            elif auth_stage == 2:
                self._login_user = base64.b64decode(stripped).decode()
                file.write(b"334 UGFzc3dvcmQ6\r\n")
                auth_stage = 3
            elif auth_stage == 3:
                auth_stage = 0
                password = base64.b64decode(stripped).decode()
                if self._login_user == self.username and password == self.password:
                    file.write(b"235 authenticated\r\n")
                else:
                    file.write(b"535 authentication failed\r\n")
            elif upper.startswith("MAIL FROM:") or upper.startswith("RCPT TO:"):
                file.write(b"250 ok\r\n")
            elif upper == "DATA":
                file.write(b"354 end with dot\r\n")
                data_mode = True
                data = []
            elif upper == "QUIT":
                file.write(b"221 bye\r\n")
                return
            else:
                file.write(b"250 ok\r\n")

    def _plain_auth(self, file, token):
        try:
            _, username, password = base64.b64decode(token).decode().split("\0", 2)
        except Exception:
            file.write(b"535 authentication failed\r\n")
            return
        if username == self.username and password == self.password:
            file.write(b"235 authenticated\r\n")
        else:
            file.write(b"535 authentication failed\r\n")


class IRCServer(TLSFixture):
    def __init__(
        self,
        nick="zpln-test",
        account="tester",
        password="synthetic-password",
        connections=1,
    ):
        super().__init__(connections=connections)
        self.nick = nick
        self.account = account
        self.password = password
        self.commands = []
        self.messages = []

    def handle(self, conn):
        file = conn.makefile("rwb", buffering=0)
        while True:
            line = file.readline()
            if not line:
                return
            text = line.rstrip(b"\r\n").decode("utf-8")
            self.commands.append(text)
            if text == "CAP LS 302":
                file.write(b":srv CAP * LS :sasl\r\n")
            elif text == "CAP REQ :sasl":
                file.write(b":srv CAP * ACK :sasl\r\n")
            elif text == "AUTHENTICATE PLAIN":
                file.write(b"AUTHENTICATE +\r\n")
            elif text.startswith("AUTHENTICATE ") and text != "AUTHENTICATE +":
                raw = base64.b64decode(text.split(" ", 1)[1]).decode()
                _, account, password = raw.split("\0", 2)
                if account == self.account and password == self.password:
                    file.write(f":srv 903 {self.nick} :SASL successful\r\n".encode())
                else:
                    file.write(f":srv 904 {self.nick} :SASL failed\r\n".encode())
            elif text == "CAP END":
                file.write(f":srv 001 {self.nick} :Welcome\r\n".encode())
            elif text.startswith("JOIN "):
                channel = text.split(" ", 1)[1]
                file.write(f":{self.nick}!u@h JOIN :{channel}\r\n".encode())
            elif text.startswith("PRIVMSG "):
                self.messages.append(text)
            elif text.startswith("QUIT "):
                return
