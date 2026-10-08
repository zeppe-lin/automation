"""Command-line error reporting helpers."""

import sys


def error(message):
    print(f"error: {message}", file=sys.stderr)
    return 1
