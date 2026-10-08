"""Thin GitHub adapters used at the forge boundary."""

import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .common import validate_release_tag, validate_repository
from .release import normalize_github_release


def fetch_release(repository, tag, token=None):
    owner, name = validate_repository(repository)
    validate_release_tag(tag)
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
        raise ValueError(f"GitHub release lookup failed: HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise ValueError("GitHub release lookup failed") from error
    return normalize_github_release(repository, tag, payload)


def gh(*args, check=True, env=None):
    return subprocess.run(["gh", *args], check=check, env=env)


def publish_release(tag, notes, title=None, prerelease=False, env=os.environ):
    if not env.get("GH_TOKEN", "").strip():
        raise ValueError("GH_TOKEN is required")
    validate_release_tag(tag)
    if gh("release", "view", tag, check=False, env=env).returncode == 0:
        return False

    command = [
        "release", "create", tag,
        "--verify-tag", "--fail-on-no-commits",
        "--title", title or tag, "--notes-file", str(notes),
    ]
    if prerelease:
        command.append("--prerelease")
    gh(*command, env=env)
    return True


def queue_release(repository, tag, automation_repository="zeppe-lin/automation", env=os.environ):
    if not env.get("GH_TOKEN", "").strip():
        raise ValueError("GH_TOKEN is required")
    validate_repository(repository)
    validate_release_tag(tag)
    validate_repository(automation_repository)

    payload = {
        "event_type": "release-published",
        "client_payload": {"repository": repository, "tag": tag},
    }
    with tempfile.TemporaryDirectory(prefix="automation-dispatch-") as tmp:
        path = Path(tmp) / "payload.json"
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        gh(
            "api", "--method", "POST",
            f"repos/{automation_repository}/dispatches",
            "--input", str(path),
            env=env,
        )
