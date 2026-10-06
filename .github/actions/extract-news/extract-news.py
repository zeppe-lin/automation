#!/usr/bin/env python3

import re
import sys
from pathlib import Path


TAG_RE = re.compile(
    r"^v(?P<version>"
    r"[0-9][0-9A-Za-z]*"
    r"(?:\.[0-9A-Za-z]+)+"
    r"(?:[-+._][0-9A-Za-z.-]+)?"
    r")$"
)


def heading_version(line):
    if not line.startswith("## "):
        return None

    heading = line[3:].strip()

    for separator in (" — ", " - "):
        if separator in heading:
            heading = heading.split(separator, 1)[0].rstrip()
            break

    if not heading:
        return None

    return heading.split()[-1]


def extract_release(text, version):
    lines = text.splitlines(keepends=True)
    starts = []

    for index, line in enumerate(lines):
        if heading_version(line.rstrip("\r\n")) == version:
            starts.append(index + 1)

    if not starts:
        raise ValueError(f"NEWS.md has no section for version {version}")

    if len(starts) != 1:
        raise ValueError(f"NEWS.md has multiple sections for version {version}")

    start = starts[0]
    end = len(lines)

    for index in range(start, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break

    body = "".join(lines[start:end]).strip()

    if not body:
        raise ValueError(f"NEWS.md section for version {version} is empty")

    return body + "\n"


def main():
    if len(sys.argv) != 4:
        print(f"usage: {sys.argv[0]} TAG NEWS OUTPUT", file=sys.stderr)
        return 2

    tag, news_path, output_path = sys.argv[1:]
    match = TAG_RE.fullmatch(tag)

    if not match:
        print(f"error: unsupported release tag: {tag}", file=sys.stderr)
        return 1

    version = match.group("version")

    try:
        text = Path(news_path).read_text(encoding="utf-8")
        release = extract_release(text, version)
        Path(output_path).write_text(release, encoding="utf-8")
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"release notes: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
