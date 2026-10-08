import argparse
import json
import sys
from pathlib import Path

from automation.pipeline import prepare_push
from automation.policy import PolicyError
from ._util import error


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("git_repository")
    parser.add_argument("event_json")
    parser.add_argument("output_dir")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        envelope = json.loads(Path(args.event_json).read_text(encoding="utf-8"))
        manifest = prepare_push(args.git_repository, envelope, args.output_dir)
    except (OSError, ValueError, PolicyError, json.JSONDecodeError) as exc:
        return error(exc)
    print(manifest["event_id"])
    return 0
