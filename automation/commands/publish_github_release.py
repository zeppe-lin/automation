import argparse
import os
import subprocess
import sys

from automation.github import publish_release
from ._util import error


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("tag")
    parser.add_argument("notes")
    parser.add_argument("--name", default=os.environ.get("RELEASE_NAME", ""))
    parser.add_argument(
        "--prerelease",
        action="store_true",
        default=os.environ.get("RELEASE_PRERELEASE", "").lower() == "true",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        created = publish_release(
            args.tag, args.notes, title=args.name or None,
            prerelease=args.prerelease, env=os.environ,
        )
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        return error(f"GitHub release publication failed: {exc}")
    if not created:
        print(f"release {args.tag} is already published; leaving it unchanged")
    return 0
