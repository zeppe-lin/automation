import argparse
import json
import os
import smtplib
import sys

from automation.delivery import deliver_release
from automation.gitstate import UNRESOLVED_ATTEMPT
from automation.mail import report_transport_error


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


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        status, message = deliver_release(
            args.delivery_dir, args.destination, args.force, os.environ
        )
    except (OSError, KeyError, ValueError, json.JSONDecodeError, smtplib.SMTPException) as exc:
        diagnostic = report_transport_error(exc) if isinstance(exc, smtplib.SMTPException) else str(exc)
        print(f"error: release delivery failed: {diagnostic}", file=sys.stderr)
        return 1
    if status == UNRESOLVED_ATTEMPT:
        print(f"error: {message}", file=sys.stderr)
        return 1
    print(message)
    return status
