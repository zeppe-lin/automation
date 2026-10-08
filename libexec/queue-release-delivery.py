#!/usr/bin/env python3
"""Queue one published release for central announcement delivery."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("repository")
    parser.add_argument("tag")
    parser.add_argument("--automation-repository", default="zeppe-lin/automation")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not os.environ.get("GH_TOKEN", "").strip():
        print("error: GH_TOKEN is required", file=sys.stderr)
        return 1
    payload = {
        "event_type": "release-published",
        "client_payload": {"repository": args.repository, "tag": args.tag},
    }
    try:
        with tempfile.TemporaryDirectory(prefix="automation-dispatch-") as tmp:
            path = Path(tmp) / "payload.json"
            path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            subprocess.run(
                [
                    "gh", "api", "--method", "POST",
                    f"repos/{args.automation_repository}/dispatches",
                    "--input", str(path),
                ],
                check=True,
            )
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"error: release delivery queue failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
