#!/usr/bin/env python3
"""Deliver one already-rendered release destination.

The command owns the claim -> external effect -> delivered transition. Forge
workflows provide credentials and state-repository configuration only; they do
not reimplement the state machine.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ALREADY_DELIVERED = 20
UNRESOLVED_ATTEMPT = 21


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("delivery_dir")
    parser.add_argument("destination", choices=("mail-user", "mail-dev", "irc"))
    parser.add_argument(
        "--force",
        action="store_true",
        default=os.environ.get("AUTOMATION_FORCE_REPLAY", "").lower() == "true",
    )
    return parser.parse_args(argv)


def invoke_state(command, manifest, destination, force=False):
    argv = [
        sys.executable,
        str(ROOT / "delivery-state.py"),
        command,
        manifest["repository"],
        manifest["tag"],
        destination,
    ]
    if force:
        argv.append("--force")
    return subprocess.run(argv, check=False).returncode



def require_environment(destination):
    if destination.startswith("mail-"):
        required = ("SMTP_HOST", "MAIL_FROM", "MAIL_TO")
        for name in required:
            if not os.environ.get(name, "").strip():
                raise ValueError(f"{name} is required")
        username = os.environ.get("SMTP_USERNAME", "").strip()
        password = os.environ.get("SMTP_PASSWORD", "")
        if bool(username) != bool(password):
            raise ValueError("SMTP_USERNAME and SMTP_PASSWORD must be configured together")
        return

    for name in ("IRC_HOST", "IRC_CHANNEL", "IRC_NICK", "IRC_SASL_PASSWORD"):
        if not os.environ.get(name, "").strip():
            raise ValueError(f"{name} is required")


def run(args):
    delivery = Path(args.delivery_dir)
    manifest = json.loads((delivery / "manifest.json").read_text(encoding="utf-8"))
    require_environment(args.destination)

    status = invoke_state("claim", manifest, args.destination, args.force)
    if status == ALREADY_DELIVERED:
        return 0
    if status == UNRESOLVED_ATTEMPT:
        return 1
    if status != 0:
        return status

    if args.destination == "irc":
        transport = [sys.executable, str(ROOT / "send-irc.py"), str(delivery / "irc.txt")]
    else:
        transport = [
            sys.executable,
            str(ROOT / "send-mail.py"),
            str(delivery / f"{args.destination}.json"),
        ]

    subprocess.run(transport, check=True)
    status = invoke_state("delivered", manifest, args.destination)
    if status != 0:
        return status
    return 0


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        return run(args)
    except (OSError, KeyError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"error: release delivery failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
