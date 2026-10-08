"""Durable delivery evidence stored in ordinary Git refs."""

import os
import re
import subprocess
from pathlib import Path

from .common import validate_release_tag, validate_repository

ALREADY_DELIVERED = 20
UNRESOLVED_ATTEMPT = 21
DESTINATIONS = {"mail-user", "mail-dev", "irc"}


def run_git(repository, *args, check=True, input_text=None):
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=False,
        capture_output=True,
        text=True,
        input=input_text,
    )
    if check and result.returncode != 0:
        raise ValueError("git delivery-state operation failed")
    return result


def validate_git_repository(repository):
    repository = Path(repository)
    if run_git(repository, "rev-parse", "--git-dir", check=False).returncode != 0:
        raise ValueError(f"not a Git repository: {repository}")
    return repository


def ref_base(source_repository, tag, destination):
    try:
        owner, name = validate_repository(source_repository)
    except ValueError as error:
        raise ValueError(f"invalid source repository: {source_repository}") from error
    try:
        validate_release_tag(tag)
    except ValueError as error:
        raise ValueError(f"invalid release tag: {tag}") from error
    if destination not in DESTINATIONS:
        raise ValueError(f"unsupported destination: {destination}")
    return f"refs/automation/delivery/release/{owner}/{name}/{tag}/{destination}"


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
    return remote_refs(repository, remote, prefix) if remote else local_refs(repository, prefix)


def write_ref(repository, remote, ref, sha):
    run_git(repository, "update-ref", ref, sha)
    if remote:
        result = run_git(repository, "push", remote, f"{ref}:{ref}", check=False)
        if result.returncode != 0:
            run_git(repository, "update-ref", "-d", ref, check=False)
            raise ValueError("failed to publish delivery-state ref")


def state_context(env=os.environ):
    repository = validate_git_repository(env.get("AUTOMATION_STATE_REPOSITORY", "."))
    remote = env.get("AUTOMATION_STATE_REMOTE", "").strip() or None
    sha = env.get("AUTOMATION_STATE_SHA", "").strip()
    if not sha:
        sha = run_git(repository, "rev-parse", "HEAD").stdout.strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", sha):
        raise ValueError("AUTOMATION_STATE_SHA is not a valid object id")

    run_id = env.get("AUTOMATION_RUN_ID", "local").strip() or "local"
    run_attempt = env.get("AUTOMATION_RUN_ATTEMPT", "1").strip() or "1"
    for name, value in (("AUTOMATION_RUN_ID", run_id), ("AUTOMATION_RUN_ATTEMPT", run_attempt)):
        if not re.fullmatch(r"[A-Za-z0-9._-]+", value):
            raise ValueError(f"{name} contains invalid characters")
    return repository, remote, sha, run_id, run_attempt


def claim(source_repository, tag, destination, force=False, env=os.environ):
    repository, remote, sha, run_id, run_attempt = state_context(env)
    base = ref_base(source_repository, tag, destination)
    delivered_ref = base + "/delivered"
    if delivered_ref in refs(repository, remote, delivered_ref):
        return ALREADY_DELIVERED, "already delivered"

    attempts = refs(repository, remote, base + "/attempts/")
    if attempts and not force:
        return UNRESOLVED_ATTEMPT, (
            "unresolved prior delivery attempt; explicit replay is required"
        )

    attempt_ref = f"{base}/attempts/{run_id}-{run_attempt}"
    write_ref(repository, remote, attempt_ref, sha)
    return 0, "claimed " + attempt_ref


def mark_delivered(source_repository, tag, destination, env=os.environ):
    repository, remote, sha, _, _ = state_context(env)
    base = ref_base(source_repository, tag, destination)
    delivered_ref = base + "/delivered"
    if delivered_ref in refs(repository, remote, delivered_ref):
        return 0, "already delivered"
    write_ref(repository, remote, delivered_ref, sha)
    return 0, "marked delivered " + delivered_ref
