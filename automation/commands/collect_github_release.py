import argparse
import json
import os
import sys
from pathlib import Path

from automation.github import fetch_release
from automation.release import normalize_github_release
from ._util import error


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("repository")
    parser.add_argument("tag")
    parser.add_argument("output")
    parser.add_argument("--release-json", metavar="FILE")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.release_json:
            payload = json.loads(Path(args.release_json).read_text(encoding="utf-8"))
            manifest = normalize_github_release(args.repository, args.tag, payload)
        else:
            manifest = fetch_release(args.repository, args.tag, os.environ.get("GITHUB_TOKEN"))
        Path(args.output).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return error(exc)
    print(manifest["event_id"])
    return 0
