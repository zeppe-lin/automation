import json
import os
import smtplib
import sys
from pathlib import Path

from automation.mail import report_transport_error, send


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(f"usage: {sys.argv[0]} MESSAGE.json", file=sys.stderr)
        return 2
    try:
        payload = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
        count = send(payload, os.environ)
    except (OSError, ValueError, json.JSONDecodeError, smtplib.SMTPException) as exc:
        print(f"error: {report_transport_error(exc)}", file=sys.stderr)
        return 1
    print(f"submitted mail to {count} recipient(s)")
    return 0
