#!/usr/bin/env python3
"""Render a normalized release manifest for each delivery destination.

Rendering is deterministic and performs no network I/O. Rendered artifacts are
public release data and must never contain transport credentials.
"""


import json
import re
import sys
from pathlib import Path


CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_header(value):
    value = CONTROL_RE.sub("", str(value)).replace("\r", " ").replace("\n", " ")
    return " ".join(value.split())


def limit_utf8(text, limit):
    data = text.encode("utf-8")
    if len(data) <= limit:
        return text

    suffix = "..."
    budget = max(0, limit - len(suffix))
    clipped = data[:budget]
    while clipped:
        try:
            return clipped.decode("utf-8") + suffix
        except UnicodeDecodeError:
            clipped = clipped[:-1]
    return suffix[:limit]


def render(manifest):
    if manifest.get("schema") != 1 or manifest.get("event") != "release":
        raise ValueError("unsupported release manifest")

    project = clean_header(manifest["project"])
    tag = clean_header(manifest["tag"])
    title = clean_header(manifest["title"])
    repository = clean_header(manifest["repository"])
    release_url = clean_header(manifest["release_url"])
    event_id = clean_header(manifest["event_id"])
    notes = manifest["notes"].rstrip() + "\n"

    user_body = (
        f"{project} {tag} has been released.\n\n"
        f"{notes}\n"
        f"Release: {release_url}\n"
    )
    dev_body = (
        f"Release published: {project} {tag}\n"
        f"Repository: https://github.com/{repository}\n"
        f"Release: {release_url}\n\n"
        f"{notes}"
    )

    user = {
        "schema": 1,
        "event_id": event_id,
        "destination": "mail-user",
        "subject": f"[release][{project}] {tag}",
        "body": user_body,
    }
    dev = {
        "schema": 1,
        "event_id": event_id,
        "destination": "mail-dev",
        "subject": f"[release][{project}] {tag}: {title}",
        "body": dev_body,
    }

    irc = CONTROL_RE.sub("", f"[release] {project} {tag} released — {release_url}")
    irc = limit_utf8(" ".join(irc.replace("\r", " ").replace("\n", " ").split()), 360)

    return user, dev, irc + "\n"


def main():
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} MANIFEST OUTPUT-DIR", file=sys.stderr)
        return 2

    try:
        manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        user, dev, irc = render(manifest)
        output = Path(sys.argv[2])
        output.mkdir(parents=True, exist_ok=True)
        (output / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (output / "mail-user.json").write_text(
            json.dumps(user, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (output / "mail-dev.json").write_text(
            json.dumps(dev, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (output / "irc.txt").write_text(irc, encoding="utf-8")
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
