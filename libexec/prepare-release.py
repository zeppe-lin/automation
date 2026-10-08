#!/usr/bin/env python3
"""Collect and render one release announcement.

This is the local preparation entry point used by forge adapters. With
--release-json it performs no network I/O, which is the supported fixture and
dry-run path for local qualification.
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("repository")
    parser.add_argument("tag")
    parser.add_argument("output_dir")
    parser.add_argument("--release-json", metavar="FILE")
    return parser.parse_args(argv)


def run(args):
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="automation-release-") as tmp:
        manifest = Path(tmp) / "manifest.json"
        collect = [
            sys.executable,
            str(ROOT / "collect-github-release.py"),
            args.repository,
            args.tag,
            str(manifest),
        ]
        if args.release_json:
            collect.extend(["--release-json", args.release_json])
        subprocess.run(collect, check=True)
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "render-release.py"),
                str(manifest),
                str(output),
            ],
            check=True,
        )


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        run(args)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"error: release preparation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
