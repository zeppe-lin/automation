import argparse
import json
import sys
from pathlib import Path

from automation.policy import PolicyError, classify_push
from automation.push import collect_push
from ._util import error
from automation.artifacts import write_push_artifacts


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
        manifest = classify_push(collect_push(args.git_repository, envelope))
        write_push_artifacts(manifest, args.output_dir)
    except (OSError, ValueError, PolicyError, json.JSONDecodeError) as exc:
        return error(exc)
    print(manifest["event_id"])
    return 0
