#!/usr/bin/env python3
"""Submit one rendered release mail message over authenticated TLS SMTP.

Configuration is read only from environment variables. Credentials are never
accepted on the command line and remote SMTP response text is not emitted to
stdout or stderr.
"""

import hashlib
import json
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import formatdate, getaddresses
from pathlib import Path


def env_required(name):
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


def recipients(value):
    addresses = [address for _, address in getaddresses([value]) if address]
    if not addresses:
        raise ValueError("MAIL_TO has no valid recipients")
    for address in addresses:
        if "\r" in address or "\n" in address:
            raise ValueError("MAIL_TO contains an invalid address")
    return addresses


def sender_address(value):
    if "\r" in value or "\n" in value:
        raise ValueError("MAIL_FROM contains an invalid address")
    parsed = [address for _, address in getaddresses([value]) if address]
    if len(parsed) != 1:
        raise ValueError("MAIL_FROM must contain exactly one address")
    return parsed[0]


def message_id(event_id, destination, sender):
    digest = hashlib.sha256(f"{event_id}\0{destination}".encode()).hexdigest()[:32]
    domain = sender.rsplit("@", 1)[1] if "@" in sender else "invalid.local"
    return f"<zeppe-lin-{digest}@{domain}>"


def build_message(payload, sender, recipient_text):
    if payload.get("schema") != 1:
        raise ValueError("unsupported mail payload")

    to = recipients(recipient_text)
    envelope_sender = sender_address(sender)
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(to)
    msg["Subject"] = payload["subject"]
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = message_id(
        payload["event_id"], payload["destination"], envelope_sender
    )
    msg["X-Zeppe-Lin-Event-ID"] = payload["event_id"]
    msg.set_content(payload["body"], charset="utf-8")
    return msg, envelope_sender, to


def tls_context():
    cafile = os.environ.get("AUTOMATION_CA_FILE", "").strip() or None
    return ssl.create_default_context(cafile=cafile)


def smtp_connection(host, port, security, timeout=30):
    context = tls_context()
    if security == "ssl":
        return smtplib.SMTP_SSL(
            host, port, timeout=timeout, context=context
        )

    if security == "starttls":
        smtp = smtplib.SMTP(host, port, timeout=timeout)
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.ehlo()
        return smtp

    raise ValueError("SMTP_SECURITY must be ssl or starttls")


def send(payload, env=os.environ):
    host = env_required("SMTP_HOST")
    port = parse_port("SMTP_PORT", env_default("SMTP_PORT", "465"))
    security = env_default("SMTP_SECURITY", "ssl").lower()
    sender = env_required("MAIL_FROM")
    recipient_text = env_required("MAIL_TO")
    username = env.get("SMTP_USERNAME", "").strip()
    password = env.get("SMTP_PASSWORD", "")

    if username and not password:
        raise ValueError("SMTP_PASSWORD is required when SMTP_USERNAME is set")
    if password and not username:
        raise ValueError("SMTP_USERNAME is required when SMTP_PASSWORD is set")

    msg, envelope_sender, to = build_message(payload, sender, recipient_text)
    with smtp_connection(host, port, security) as smtp:
        if username:
            smtp.login(username, password)
        refused = smtp.send_message(msg, from_addr=envelope_sender, to_addrs=to)
        if refused:
            raise ValueError(f"SMTP refused {len(refused)} recipient(s)")
    return len(to)


def report_transport_error(error):
    """Return a useful diagnostic without printing remote SMTP response text."""
    if isinstance(error, smtplib.SMTPAuthenticationError):
        return "SMTP authentication failed"
    if isinstance(error, smtplib.SMTPResponseException):
        return f"SMTP server rejected the request (status {error.smtp_code})"
    if isinstance(error, smtplib.SMTPServerDisconnected):
        return "SMTP server disconnected"
    if isinstance(error, smtplib.SMTPException):
        return "SMTP protocol failure"
    if isinstance(error, (TimeoutError, OSError)):
        return "SMTP connection or TLS failure"
    return str(error)


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} MESSAGE.json", file=sys.stderr)
        return 2

    try:
        payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        count = send(payload)
    except (OSError, ValueError, json.JSONDecodeError, smtplib.SMTPException) as error:
        print(f"error: {report_transport_error(error)}", file=sys.stderr)
        return 1

    print(f"submitted mail to {count} recipient(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
