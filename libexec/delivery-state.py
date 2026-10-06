#!/usr/bin/env python3

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


ALREADY_DELIVERED = 20
UNRESOLVED_ATTEMPT = 21
REPOSITORY_RE = re.compile(r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<name>[A-Za-z0-9_.-]+)$")
TAG_RE = re.compile(r"^v[0-9][0-9A-Za-z]*(?:\.[0-9A-Za-z]+)+(?:[-+._][0-9A-Za-z.-]+)?$")


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def api(method, path, token, payload=None):
    url = "https://api.github.com" + path
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "zeppe-lin-automation",
            "X-GitHub-Api-Version": "2026-03-10",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status == 204:
                return None
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        detail = error.read().decode("utf-8", "replace")
        raise ValueError(f"GitHub state API failed: HTTP {error.code}: {detail}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise ValueError(f"GitHub state API failed: {error}") from error


def ref_base(source_repository, tag, destination):
    match = REPOSITORY_RE.fullmatch(source_repository)
    if not match or match.group("owner") != "zeppe-lin":
        raise ValueError(f"invalid source repository: {source_repository}")
    if not TAG_RE.fullmatch(tag):
        raise ValueError(f"invalid release tag: {tag}")
    return (
        "automation/delivery/release/"
        f"{match.group('owner')}/{match.group('name')}/{tag}/{destination}"
    )


def matching_refs(repository, prefix, token):
    quoted = urllib.parse.quote(prefix, safe="/")
    result = api("GET", f"/repos/{repository}/git/matching-refs/{quoted}", token)
    return result or []


def create_ref(repository, ref, sha, token):
    return api(
        "POST",
        f"/repos/{repository}/git/refs",
        token,
        {"ref": "refs/" + ref, "sha": sha},
    )


def claim(source_repository, tag, destination, force):
    state_repository = required("GITHUB_REPOSITORY")
    token = required("GITHUB_TOKEN")
    sha = required("GITHUB_SHA")
    run_id = required("GITHUB_RUN_ID")
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1").strip() or "1"

    base = ref_base(source_repository, tag, destination)
    delivered = matching_refs(state_repository, base + "/delivered", token)
    if any(item.get("ref") == "refs/" + base + "/delivered" for item in delivered):
        print("already delivered")
        return ALREADY_DELIVERED

    attempts = matching_refs(state_repository, base + "/attempts/", token)
    if attempts and not force:
        print(
            "error: unresolved prior delivery attempt; explicit replay is required",
            file=sys.stderr,
        )
        return UNRESOLVED_ATTEMPT

    attempt_ref = f"{base}/attempts/{run_id}-{run_attempt}"
    create_ref(state_repository, attempt_ref, sha, token)
    print("claimed " + attempt_ref)
    return 0


def mark_delivered(source_repository, tag, destination):
    state_repository = required("GITHUB_REPOSITORY")
    token = required("GITHUB_TOKEN")
    sha = required("GITHUB_SHA")
    base = ref_base(source_repository, tag, destination)
    delivered_ref = base + "/delivered"

    existing = matching_refs(state_repository, delivered_ref, token)
    if any(item.get("ref") == "refs/" + delivered_ref for item in existing):
        print("already delivered")
        return 0

    create_ref(state_repository, delivered_ref, sha, token)
    print("marked delivered " + delivered_ref)
    return 0


def main():
    if len(sys.argv) < 5:
        print(
            f"usage: {sys.argv[0]} claim|delivered REPOSITORY TAG DESTINATION [--force]",
            file=sys.stderr,
        )
        return 2

    command, repository, tag, destination = sys.argv[1:5]
    force = "--force" in sys.argv[5:]
    if destination not in {"mail-user", "mail-dev", "irc"}:
        print(f"error: unsupported destination: {destination}", file=sys.stderr)
        return 2

    try:
        if command == "claim":
            return claim(repository, tag, destination, force)
        if command == "delivered":
            return mark_delivered(repository, tag, destination)
        print(f"error: unsupported command: {command}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
