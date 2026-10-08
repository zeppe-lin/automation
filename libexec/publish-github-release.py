#!/usr/bin/env python3
"""Publish one GitHub Release from an already-rendered notes file.

The command is intentionally a thin GitHub adapter. Release-note extraction is
a separate local projection and the caller supplies the checked-out tag.
"""

import argparse
import os
import subprocess
import sys


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


def gh(*args, check=True):
    return subprocess.run(["gh", *args], check=check)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not os.environ.get("GH_TOKEN", "").strip():
        print("error: GH_TOKEN is required", file=sys.stderr)
        return 1
    title = args.name or args.tag
    if gh("release", "view", args.tag, check=False).returncode == 0:
        print(f"release {args.tag} is already published; leaving it unchanged")
        return 0
    command = [
        "release", "create", args.tag,
        "--verify-tag", "--fail-on-no-commits",
        "--title", title, "--notes-file", args.notes,
    ]
    if args.prerelease:
        command.append("--prerelease")
    try:
        gh(*command)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"error: GitHub release publication failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
