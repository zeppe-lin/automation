#!/usr/bin/env python3
"""Submit one rendered release announcement to IRC over TLS and SASL PLAIN.

The SASL credential is read only from the environment. The client never logs
protocol traffic because the AUTHENTICATE payload is a transformed credential
which GitHub's ordinary secret masking cannot be relied on to recognize.
"""

import base64
import os
import socket
import ssl
import sys
import time
from pathlib import Path


FAIL_NUMERICS = {"904", "905", "906", "907"}


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def env_default(name, default):
    value = os.environ.get(name, "").strip()
    return value or default


def parse_port(name, value):
    try:
        port = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if not 1 <= port <= 65535:
        raise ValueError(f"{name} must be between 1 and 65535")
    return port


def irc_token(name, value):
    if not value or any(char.isspace() for char in value) or "\r" in value or "\n" in value:
        raise ValueError(f"{name} contains an invalid IRC token")
    return value


def parse_command(line):
    rest = line
    if rest.startswith(":"):
        _, _, rest = rest.partition(" ")
    return rest.split(" ", 1)[0]


class IRCClient:
    def __init__(self, sock, nick, channel):
        self.sock = sock
        self.nick = nick
        self.channel = channel
        self.buffer = b""

    def send_line(self, line):
        data = line.encode("utf-8")
        if b"\r" in data or b"\n" in data:
            raise ValueError("IRC command contains a newline")
        if len(data) > 510:
            raise ValueError("IRC command exceeds protocol line limit")
        self.sock.sendall(data + b"\r\n")

    def read_line(self, deadline):
        while b"\n" not in self.buffer:
            timeout = deadline - time.monotonic()
            if timeout <= 0:
                raise TimeoutError("IRC server response timed out")
            self.sock.settimeout(timeout)
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("IRC server closed the connection")
            self.buffer += chunk

        raw, self.buffer = self.buffer.split(b"\n", 1)
        line = raw.rstrip(b"\r").decode("utf-8", "replace")
        if parse_command(line) == "PING":
            payload = line.split(" ", 1)[1] if " " in line else ""
            self.send_line(f"PONG {payload}")
            return self.read_line(deadline)
        return line

    def wait_for(self, accepted, deadline):
        while True:
            line = self.read_line(deadline)
            command = parse_command(line)
            if command in FAIL_NUMERICS:
                raise ConnectionError(f"IRC authentication failed: {command}")
            if command in accepted:
                return line

    def authenticate(self, username, sasl_user, sasl_password):
        deadline = time.monotonic() + 20
        self.send_line("CAP LS 302")
        self.send_line(f"NICK {self.nick}")
        self.send_line(f"USER {username} 0 * :Zeppe-Lin automation")

        capabilities = []
        while True:
            cap_line = self.wait_for({"CAP"}, deadline)
            capabilities.append(cap_line.lower())
            if " LS * :" not in cap_line:
                break
        if not any("sasl" in line for line in capabilities):
            raise ConnectionError("IRC server does not advertise SASL")

        self.send_line("CAP REQ :sasl")
        while True:
            line = self.wait_for({"CAP"}, deadline)
            if " ACK " in line and "sasl" in line.lower():
                break
            if " NAK " in line:
                raise ConnectionError("IRC server rejected SASL capability")

        self.send_line("AUTHENTICATE PLAIN")
        self.wait_for({"AUTHENTICATE"}, deadline)

        auth = base64.b64encode(
            f"\0{sasl_user}\0{sasl_password}".encode("utf-8")
        ).decode("ascii")
        for offset in range(0, len(auth), 400):
            self.send_line("AUTHENTICATE " + auth[offset : offset + 400])
        if len(auth) % 400 == 0:
            self.send_line("AUTHENTICATE +")

        self.wait_for({"903"}, deadline)
        self.send_line("CAP END")
        self.wait_for({"001"}, deadline)

    def publish(self, message):
        deadline = time.monotonic() + 20
        self.send_line(f"JOIN {self.channel}")

        while True:
            line = self.read_line(deadline)
            command = parse_command(line)
            if command == "366" or (
                command == "JOIN" and line.lstrip(":").startswith(self.nick + "!")
            ):
                break
            if command in {"403", "404", "405", "471", "473", "474", "475"}:
                raise ConnectionError(f"IRC channel join failed: {command}")

        prefix = f"PRIVMSG {self.channel} :"
        max_payload = 510 - len(prefix.encode("utf-8"))
        data = message.encode("utf-8")
        if len(data) > max_payload:
            data = data[: max(0, max_payload - 3)]
            while data:
                try:
                    message = data.decode("utf-8") + "..."
                    break
                except UnicodeDecodeError:
                    data = data[:-1]
        self.send_line(prefix + message)
        self.send_line("QUIT :release announcement submitted")


def connect(host, port):
    sock = socket.create_connection((host, port), timeout=20)
    context = ssl.create_default_context()
    return context.wrap_socket(sock, server_hostname=host)


def send(message):
    host = required("IRC_HOST")
    port = parse_port("IRC_PORT", env_default("IRC_PORT", "6697"))
    channel = irc_token("IRC_CHANNEL", required("IRC_CHANNEL"))
    nick = irc_token("IRC_NICK", required("IRC_NICK"))
    username = irc_token("IRC_USERNAME", env_default("IRC_USERNAME", nick))
    sasl_user = irc_token("IRC_SASL_USERNAME", env_default("IRC_SASL_USERNAME", nick))
    sasl_password = required("IRC_SASL_PASSWORD")

    sock = connect(host, port)
    try:
        client = IRCClient(sock, nick, channel)
        client.authenticate(username, sasl_user, sasl_password)
        client.publish(message)
    finally:
        sock.close()


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} MESSAGE.txt", file=sys.stderr)
        return 2

    try:
        message = Path(sys.argv[1]).read_text(encoding="utf-8").strip()
        if not message:
            raise ValueError("IRC message is empty")
        if "\r" in message or "\n" in message:
            raise ValueError("IRC message must contain exactly one line")
        send(message)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except TimeoutError:
        print("error: IRC server response timed out", file=sys.stderr)
        return 1
    except ConnectionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except OSError:
        print("error: IRC connection or TLS failure", file=sys.stderr)
        return 1

    print("submitted IRC announcement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
