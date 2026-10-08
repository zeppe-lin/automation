"""Acquire the Git objects required to interpret one push transition.

This module owns mutable repository acquisition.  ``automation.gitrepo`` remains
read-only observation code.  Materialization deliberately creates a bare
repository so source-tree hooks, filters, and checked-out files never enter the
trusted automation workspace.
"""

import os
import subprocess
from pathlib import Path

from .gitrepo import GitRepository


class GitMaterializationError(ValueError):
    pass


def _git_env():
    env = os.environ.copy()
    # Only protocols needed by the central GitHub adapter and local fixture
    # remotes are admitted.  In particular, ext:: helpers must never execute.
    env["GIT_ALLOW_PROTOCOL"] = "https:file"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["LC_ALL"] = "C"
    return env


def _run(repository, *args, check=True):
    command = ["git"]
    if repository is not None:
        command += ["-C", str(repository)]
    command += list(args)
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_git_env(),
    )
    if check and result.returncode != 0:
        raise GitMaterializationError("Git repository materialization failed")
    return result


def _ensure_empty_destination(destination):
    destination = Path(destination)
    if destination.exists():
        if not destination.is_dir() or any(destination.iterdir()):
            raise GitMaterializationError(
                f"materialization destination is not empty: {destination}"
            )
    else:
        destination.mkdir(parents=True)
    return destination


def _fetch_required_object(repository, oid):
    repo = GitRepository(repository)
    if oid == repo.zero_oid or repo.object_exists(oid):
        return
    result = _run(
        repository,
        "fetch",
        "--quiet",
        "--no-tags",
        "--no-recurse-submodules",
        "origin",
        oid,
        check=False,
    )
    if result.returncode != 0 or not repo.object_exists(oid):
        raise GitMaterializationError(f"required Git object is unavailable: {oid}")


def materialize_push(remote_url, envelope, destination):
    """Create a bare event workspace containing refs and push endpoint objects."""

    if not isinstance(remote_url, (str, os.PathLike)) or not str(remote_url):
        raise GitMaterializationError("Git remote URL is required")
    destination = _ensure_empty_destination(destination)
    _run(None, "init", "--bare", "--quiet", str(destination))
    _run(destination, "remote", "add", "origin", str(remote_url))

    # Fetch all current branch/tag refs for branch-creation reachability.  The
    # event endpoint objects are fetched explicitly below because force pushes
    # and deletions can make the pre-push object unreachable from current refs.
    _run(
        destination,
        "fetch",
        "--quiet",
        "--force",
        "--prune",
        "--no-recurse-submodules",
        "origin",
        "+refs/heads/*:refs/heads/*",
        "+refs/tags/*:refs/tags/*",
    )

    repo = GitRepository(destination)
    before = repo.validate_oid(str(envelope.get("before", "")), allow_zero=True)
    after = repo.validate_oid(str(envelope.get("after", "")), allow_zero=True)
    _fetch_required_object(destination, before)
    _fetch_required_object(destination, after)
    return destination
