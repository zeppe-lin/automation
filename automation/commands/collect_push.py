import argparse
import json
import sys
from pathlib import Path

from automation.push import collect_push
from ._util import error


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("git_repository")
    parser.add_argument("event_json")
    parser.add_argument("output")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        envelope = json.loads(Path(args.event_json).read_text(encoding="utf-8"))
        manifest = collect_push(args.git_repository, envelope)
        Path(args.output).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return error(exc)
    print(manifest["event_id"])
    return 0
