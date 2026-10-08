"""Durable delivery evidence stored in ordinary Git refs.

The delivery ledger records controller knowledge, not transport truth.  An
attempt ref is written before external I/O.  A delivered ref is written only
after the transport returns success.  If an attempt exists without a delivered
ref, the external effect is uncertain and automatic replay is refused.
"""

from dataclasses import dataclass
import hashlib
import os
import re
import subprocess
from pathlib import Path

from .common import validate_release_tag, validate_repository

ALREADY_DELIVERED = 20
UNRESOLVED_ATTEMPT = 21
DESTINATIONS = {"mail-user", "mail-dev", "irc"}
TOKEN_RE = re.compile(r"^[A-Za-z0-9._-]+$")
OID_RE = re.compile(r"^[0-9a-fA-F]{40,64}$")


@dataclass(frozen=True)
class DeliveryKey:
    """Stable identity for one externally visible delivery effect."""

    ref_base: str

    @property
    def delivered_ref(self):
        return self.ref_base + "/delivered"

    @property
    def attempts_prefix(self):
        return self.ref_base + "/attempts/"

    def attempt_ref(self, run_id, run_attempt):
        return f"{self.attempts_prefix}{run_id}-{run_attempt}"


class DeliveryLedger:
    """Git-backed claim/delivered state for external effects."""

    def __init__(self, repository, remote, sha, run_id, run_attempt):
        self.repository = validate_git_repository(repository)
        self.remote = remote
        self.sha = sha
        self.run_id = run_id
        self.run_attempt = run_attempt

    @classmethod
    def from_environment(cls, env=os.environ):
        repository = validate_git_repository(
            env.get("AUTOMATION_STATE_REPOSITORY", ".")
        )
        remote = env.get("AUTOMATION_STATE_REMOTE", "").strip() or None
        sha = env.get("AUTOMATION_STATE_SHA", "").strip()
        if not sha:
            sha = run_git(repository, "rev-parse", "HEAD").stdout.strip()
        if not OID_RE.fullmatch(sha):
            raise ValueError("AUTOMATION_STATE_SHA is not a valid object id")

        run_id = env.get("AUTOMATION_RUN_ID", "local").strip() or "local"
        run_attempt = env.get("AUTOMATION_RUN_ATTEMPT", "1").strip() or "1"
        for name, value in (
            ("AUTOMATION_RUN_ID", run_id),
            ("AUTOMATION_RUN_ATTEMPT", run_attempt),
        ):
            if not TOKEN_RE.fullmatch(value):
                raise ValueError(f"{name} contains invalid characters")
        return cls(repository, remote, sha, run_id, run_attempt)

    def refs(self, prefix):
        if self.remote:
            return remote_refs(self.repository, self.remote, prefix)
        return local_refs(self.repository, prefix)

    def write_ref(self, ref):
        run_git(self.repository, "update-ref", ref, self.sha)
        if self.remote:
            result = run_git(
                self.repository,
                "push",
                self.remote,
                f"{ref}:{ref}",
                check=False,
            )
            if result.returncode != 0:
                run_git(self.repository, "update-ref", "-d", ref, check=False)
                raise ValueError("failed to publish delivery-state ref")

    def claim(self, key, force=False):
        if key.delivered_ref in self.refs(key.delivered_ref):
            return ALREADY_DELIVERED, "already delivered"

        attempts = self.refs(key.attempts_prefix)
        if attempts and not force:
            return UNRESOLVED_ATTEMPT, (
                "unresolved prior delivery attempt; explicit replay is required"
            )

        attempt_ref = key.attempt_ref(self.run_id, self.run_attempt)
        self.write_ref(attempt_ref)
        return 0, "claimed " + attempt_ref

    def mark_delivered(self, key):
        if key.delivered_ref in self.refs(key.delivered_ref):
            return 0, "already delivered"
        self.write_ref(key.delivered_ref)
        return 0, "marked delivered " + key.delivered_ref


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


def _validate_destination(destination):
    if destination not in DESTINATIONS:
        raise ValueError(f"unsupported destination: {destination}")
    return destination


def release_key(source_repository, tag, destination):
    try:
        owner, name = validate_repository(source_repository)
    except ValueError as error:
        raise ValueError(f"invalid source repository: {source_repository}") from error
    try:
        validate_release_tag(tag)
    except ValueError as error:
        raise ValueError(f"invalid release tag: {tag}") from error
    _validate_destination(destination)
    return DeliveryKey(
        f"refs/automation/delivery/release/{owner}/{name}/{tag}/{destination}"
    )


def push_key(
    source_repository,
    event_id,
    destination,
    item_id,
    template_version=1,
):
    """Return a stable ledger key for one push delivery item.

    ``event_id`` is hashed because provider-neutral event IDs contain ref names
    and punctuation that do not belong in a Git ref.  The full SHA-256 digest
    is deterministic and can always be recomputed from ``manifest.json``.
    """

    try:
        owner, name = validate_repository(source_repository)
    except ValueError as error:
        raise ValueError(f"invalid source repository: {source_repository}") from error
    _validate_destination(destination)
    expected = f"push:{source_repository}:"
    if not isinstance(event_id, str) or not event_id.startswith(expected):
        raise ValueError("push event ID does not match source repository")
    if not isinstance(item_id, str) or not TOKEN_RE.fullmatch(item_id):
        raise ValueError("invalid push delivery item ID")
    if destination.startswith("mail-") and not OID_RE.fullmatch(item_id):
        raise ValueError("mail delivery item ID must be a Git object ID")
    if destination == "irc" and item_id != "push":
        raise ValueError("IRC push delivery item ID must be 'push'")
    if not isinstance(template_version, int) or template_version < 1:
        raise ValueError("invalid delivery template version")

    event_digest = hashlib.sha256(event_id.encode("utf-8")).hexdigest()
    return DeliveryKey(
        "refs/automation/delivery/push/"
        f"{owner}/{name}/{event_digest}/{destination}/{item_id}/template-{template_version}"
    )


# Release compatibility helpers.  Release and push delivery both use the same
# ledger implementation; these preserve the established local command API.
def ref_base(source_repository, tag, destination):
    return release_key(source_repository, tag, destination).ref_base


def state_context(env=os.environ):
    ledger = DeliveryLedger.from_environment(env)
    return (
        ledger.repository,
        ledger.remote,
        ledger.sha,
        ledger.run_id,
        ledger.run_attempt,
    )


def claim(source_repository, tag, destination, force=False, env=os.environ):
    return DeliveryLedger.from_environment(env).claim(
        release_key(source_repository, tag, destination), force
    )


def mark_delivered(source_repository, tag, destination, env=os.environ):
    return DeliveryLedger.from_environment(env).mark_delivered(
        release_key(source_repository, tag, destination)
    )
