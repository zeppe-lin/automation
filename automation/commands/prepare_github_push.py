import argparse
import json
import sys
from pathlib import Path

from automation.materialize import materialize_push
from automation.pipeline import prepare_push
from automation.policy import PolicyError
from automation.providers.github import clone_url, envelope_from_repository_dispatch
from ._util import error


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("dispatch_json")
    parser.add_argument("git_repository")
    parser.add_argument("output_dir")
    parser.add_argument("--remote")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        payload = json.loads(Path(args.dispatch_json).read_text(encoding="utf-8"))
        envelope = envelope_from_repository_dispatch(payload)
        remote = args.remote or clone_url(envelope["repository"])
        materialize_push(remote, envelope, args.git_repository)
        manifest = prepare_push(args.git_repository, envelope, args.output_dir)
    except (OSError, ValueError, PolicyError, json.JSONDecodeError) as exc:
        return error(f"GitHub push preparation failed: {exc}")
    print(manifest["event_id"])
    return 0
