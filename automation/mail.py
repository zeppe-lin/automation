"""SMTP transport for rendered automation messages."""

import hashlib
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, getaddresses

from .common import env_default, env_required, parse_port


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


def tls_context(env):
    cafile = env.get("AUTOMATION_CA_FILE", "").strip() or None
    return ssl.create_default_context(cafile=cafile)


def smtp_connection(host, port, security, env, timeout=30):
    context = tls_context(env)
    if security == "ssl":
        return smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)
    if security == "starttls":
        smtp = smtplib.SMTP(host, port, timeout=timeout)
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.ehlo()
        return smtp
    raise ValueError("SMTP_SECURITY must be ssl or starttls")


def send(payload, env):
    host = env_required("SMTP_HOST", env)
    port = parse_port("SMTP_PORT", env_default("SMTP_PORT", "465", env))
    security = env_default("SMTP_SECURITY", "ssl", env).lower()
    sender = env_required("MAIL_FROM", env)
    recipient_text = env_required("MAIL_TO", env)
    username = env.get("SMTP_USERNAME", "").strip()
    password = env.get("SMTP_PASSWORD", "")
    if bool(username) != bool(password):
        raise ValueError("SMTP_USERNAME and SMTP_PASSWORD must be configured together")

    msg, envelope_sender, to = build_message(payload, sender, recipient_text)
    with smtp_connection(host, port, security, env) as smtp:
        if username:
            smtp.login(username, password)
        refused = smtp.send_message(msg, from_addr=envelope_sender, to_addrs=to)
        if refused:
            raise ValueError(f"SMTP refused {len(refused)} recipient(s)")
    return len(to)


def report_transport_error(error):
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
