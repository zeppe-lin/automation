"""Release delivery state machine."""

import json
import os
from pathlib import Path

from . import gitstate
from .irc import send as send_irc
from .mail import send as send_mail


def require_environment(destination, env=os.environ):
    if destination.startswith("mail-"):
        for name in ("SMTP_HOST", "MAIL_FROM", "MAIL_TO"):
            if not env.get(name, "").strip():
                raise ValueError(f"{name} is required")
        username = env.get("SMTP_USERNAME", "").strip()
        password = env.get("SMTP_PASSWORD", "")
        if bool(username) != bool(password):
            raise ValueError("SMTP_USERNAME and SMTP_PASSWORD must be configured together")
        return

    for name in ("IRC_HOST", "IRC_CHANNEL", "IRC_NICK", "IRC_SASL_PASSWORD"):
        if not env.get(name, "").strip():
            raise ValueError(f"{name} is required")


def deliver_release(delivery_dir, destination, force=False, env=os.environ):
    if destination not in gitstate.DESTINATIONS:
        raise ValueError(f"unsupported destination: {destination}")
    delivery = Path(delivery_dir)
    manifest = json.loads((delivery / "manifest.json").read_text(encoding="utf-8"))
    require_environment(destination, env)

    status, message = gitstate.claim(
        manifest["repository"], manifest["tag"], destination, force, env
    )
    if status == gitstate.ALREADY_DELIVERED:
        return 0, message
    if status != 0:
        return status, message

    if destination == "irc":
        text = (delivery / "irc.txt").read_text(encoding="utf-8").strip()
        if not text or "\r" in text or "\n" in text:
            raise ValueError("IRC message must contain exactly one non-empty line")
        send_irc(text, env)
    else:
        payload = json.loads(
            (delivery / f"{destination}.json").read_text(encoding="utf-8")
        )
        send_mail(payload, env)

    status, delivered_message = gitstate.mark_delivered(
        manifest["repository"], manifest["tag"], destination, env
    )
    return status, delivered_message
