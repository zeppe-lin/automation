#!/usr/bin/env python3
"""Collect one published Zeppe-Lin GitHub Release into a normalized manifest.

Caller-supplied dispatch fields identify only the repository and tag. Release
prose is fetched again from GitHub so the published release remains delivery
authority.
"""


import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


REPOSITORY_RE = re.compile(r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<name>[A-Za-z0-9_.-]+)$")
TAG_RE = re.compile(r"^v[0-9][0-9A-Za-z]*(?:\.[0-9A-Za-z]+)+(?:[-+._][0-9A-Za-z.-]+)?$")


def validate_request(repository, tag, allowed_owner="zeppe-lin"):
    match = REPOSITORY_RE.fullmatch(repository)
    if not match:
        raise ValueError(f"invalid repository: {repository}")
    if match.group("owner") != allowed_owner:
        raise ValueError(f"repository owner is not allowed: {match.group('owner')}")
    if not TAG_RE.fullmatch(tag):
        raise ValueError(f"unsupported release tag: {tag}")
    return match.group("owner"), match.group("name")


def normalize_release(repository, tag, payload, allowed_owner="zeppe-lin"):
    owner, name = validate_request(repository, tag, allowed_owner)

    if payload.get("tag_name") != tag:
        raise ValueError("GitHub release tag does not match requested tag")
    if payload.get("draft"):
        raise ValueError("GitHub release is still a draft")

    body = payload.get("body")
    if not isinstance(body, str) or not body.strip():
        raise ValueError("GitHub release has no release notes")

    html_url = payload.get("html_url")
    if not isinstance(html_url, str) or not html_url.startswith("https://github.com/"):
        raise ValueError("GitHub release has no valid release URL")

    title = payload.get("name")
    if not isinstance(title, str) or not title.strip():
        title = tag

    return {
        "schema": 1,
        "event": "release",
        "event_id": f"release:{repository}:{tag}",
        "repository": repository,
        "project": name,
        "tag": tag,
        "title": title.strip(),
        "release_url": html_url,
        "published_at": payload.get("published_at"),
        "prerelease": bool(payload.get("prerelease")),
        "notes": body.strip() + "\n",
    }


def fetch_release(repository, tag, token=None):
    owner, name = validate_request(repository, tag)
    url = (
        "https://api.github.com/repos/"
        f"{urllib.parse.quote(owner, safe='')}/"
        f"{urllib.parse.quote(name, safe='')}/releases/tags/"
        f"{urllib.parse.quote(tag, safe='')}"
    )

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "zeppe-lin-automation",
        "X-GitHub-Api-Version": "2026-03-10",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        raise ValueError(
            f"GitHub release lookup failed: HTTP {error.code}"
        ) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise ValueError(f"GitHub release lookup failed: {error}") from error

    return normalize_release(repository, tag, payload)


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("repository")
    parser.add_argument("tag")
    parser.add_argument("output")
    parser.add_argument(
        "--release-json",
        metavar="FILE",
        help="normalize a local GitHub Release payload instead of using the network",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.release_json:
            payload = json.loads(Path(args.release_json).read_text(encoding="utf-8"))
            manifest = normalize_release(args.repository, args.tag, payload)
        else:
            manifest = fetch_release(
                args.repository, args.tag, os.environ.get("GITHUB_TOKEN")
            )
        Path(args.output).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(manifest["event_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
