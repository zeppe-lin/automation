import os
import sys
from pathlib import Path

from automation.irc import send


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(f"usage: {sys.argv[0]} MESSAGE.txt", file=sys.stderr)
        return 2
    try:
        message = Path(argv[0]).read_text(encoding="utf-8").strip()
        if not message:
            raise ValueError("IRC message is empty")
        if "\r" in message or "\n" in message:
            raise ValueError("IRC message must contain exactly one line")
        send(message, os.environ)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except TimeoutError:
        print("error: IRC server response timed out", file=sys.stderr)
        return 1
    except ConnectionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError:
        print("error: IRC connection or TLS failure", file=sys.stderr)
        return 1
    print("submitted IRC announcement")
    return 0
