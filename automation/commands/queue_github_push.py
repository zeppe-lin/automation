import argparse
import json
import os
import sys
from pathlib import Path

from automation.github import queue_push
from ._util import error


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("event_json")
    parser.add_argument("--automation-repository", default="zeppe-lin/automation")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        payload = json.loads(Path(args.event_json).read_text(encoding="utf-8"))
        envelope = queue_push(payload, args.automation_repository, os.environ)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return error(f"GitHub push queue failed: {exc}")
    print(f"queued {envelope['repository']} {envelope['ref']}")
    return 0
