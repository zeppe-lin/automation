import argparse
import os
import sys

from automation.github import queue_release
from ._util import error


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("repository")
    parser.add_argument("tag")
    parser.add_argument("--automation-repository", default="zeppe-lin/automation")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        queue_release(args.repository, args.tag, args.automation_repository, os.environ)
    except (OSError, ValueError) as exc:
        return error(f"release delivery queue failed: {exc}")
    return 0
