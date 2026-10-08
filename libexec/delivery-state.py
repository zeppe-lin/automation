#!/usr/bin/env python3
"""Maintain durable release-delivery state in ordinary Git refs.

The command deliberately knows nothing about GitHub's API. It operates on a
local Git repository and may mirror refs to one configured remote. This keeps
the state machine locally testable while allowing GitHub Actions to use the
same code with the checked-out automation repository.
"""

import os
import re
import subprocess
import sys
from pathlib import Path


ALREADY_DELIVERED = 20
UNRESOLVED_ATTEMPT = 21
REPOSITORY_RE = re.compile(r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<name>[A-Za-z0-9_.-]+)$")
TAG_RE = re.compile(r"^v[0-9][0-9A-Za-z]*(?:\.[0-9A-Za-z]+)+(?:[-+._][0-9A-Za-z.-]+)?$")
DESTINATIONS = {"mail-user", "mail-dev", "irc"}


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def run_git(repository, *args, check=True):
    command = ["git", "-C", str(repository), *args]
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise ValueError("git delivery-state operation failed")
    return result


def validate_git_repository(repository):
    repository = Path(repository)
    result = run_git(repository, "rev-parse", "--git-dir", check=False)
    if result.returncode != 0:
        raise ValueError(f"not a Git repository: {repository}")
    return repository


def ref_base(source_repository, tag, destination):
    match = REPOSITORY_RE.fullmatch(source_repository)
    if not match or match.group("owner") != "zeppe-lin":
        raise ValueError(f"invalid source repository: {source_repository}")
    if not TAG_RE.fullmatch(tag):
        raise ValueError(f"invalid release tag: {tag}")
    if destination not in DESTINATIONS:
        raise ValueError(f"unsupported destination: {destination}")
    return (
        "refs/automation/delivery/release/"
        f"{match.group('owner')}/{match.group('name')}/{tag}/{destination}"
    )


def local_refs(repository, prefix):
    result = run_git(repository, "for-each-ref", "--format=%(refname)", prefix)
    return [line for line in result.stdout.splitlines() if line]


def remote_refs(repository, remote, prefix):
    result = run_git(repository, "ls-remote", "--refs", remote, prefix + "*")
    refs = []
    for line in result.stdout.splitlines():
        fields = line.split(None, 1)
        if len(fields) == 2:
            refs.append(fields[1])
    return refs


def refs(repository, remote, prefix):
    if remote:
        return remote_refs(repository, remote, prefix)
    return local_refs(repository, prefix)


def write_ref(repository, remote, ref, sha):
    run_git(repository, "update-ref", ref, sha)
    if remote:
        result = run_git(repository, "push", remote, f"{ref}:{ref}", check=False)
        if result.returncode != 0:
            run_git(repository, "update-ref", "-d", ref, check=False)
            raise ValueError("failed to publish delivery-state ref")


def state_context():
    repository = validate_git_repository(
        os.environ.get("AUTOMATION_STATE_REPOSITORY", ".")
    )
    remote = os.environ.get("AUTOMATION_STATE_REMOTE", "").strip() or None
    sha = os.environ.get("AUTOMATION_STATE_SHA", "").strip()
    if not sha:
        sha = run_git(repository, "rev-parse", "HEAD").stdout.strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", sha):
        raise ValueError("AUTOMATION_STATE_SHA is not a valid object id")
    run_id = os.environ.get("AUTOMATION_RUN_ID", "local").strip() or "local"
    run_attempt = os.environ.get("AUTOMATION_RUN_ATTEMPT", "1").strip() or "1"
    if not re.fullmatch(r"[A-Za-z0-9._-]+", run_id):
        raise ValueError("AUTOMATION_RUN_ID contains invalid characters")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", run_attempt):
        raise ValueError("AUTOMATION_RUN_ATTEMPT contains invalid characters")
    return repository, remote, sha, run_id, run_attempt


def claim(source_repository, tag, destination, force=False):
    repository, remote, sha, run_id, run_attempt = state_context()
    base = ref_base(source_repository, tag, destination)
    delivered_ref = base + "/delivered"

    if delivered_ref in refs(repository, remote, delivered_ref):
        print("already delivered")
        return ALREADY_DELIVERED

    attempts = refs(repository, remote, base + "/attempts/")
    if attempts and not force:
        print(
            "error: unresolved prior delivery attempt; explicit replay is required",
            file=sys.stderr,
        )
        return UNRESOLVED_ATTEMPT

    attempt_ref = f"{base}/attempts/{run_id}-{run_attempt}"
    write_ref(repository, remote, attempt_ref, sha)
    print("claimed " + attempt_ref)
    return 0


def mark_delivered(source_repository, tag, destination):
    repository, remote, sha, _, _ = state_context()
    base = ref_base(source_repository, tag, destination)
    delivered_ref = base + "/delivered"

    if delivered_ref in refs(repository, remote, delivered_ref):
        print("already delivered")
        return 0

    write_ref(repository, remote, delivered_ref, sha)
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
    force = sys.argv[5:] == ["--force"]
    if sys.argv[5:] and not force:
        print("error: unsupported argument", file=sys.stderr)
        return 2

    try:
        if command == "claim":
            return claim(repository, tag, destination, force)
        if command == "delivered":
            if force:
                print("error: --force is valid only with claim", file=sys.stderr)
                return 2
            return mark_delivered(repository, tag, destination)
        print(f"error: unsupported command: {command}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
