"""GitHub event normalization.

GitHub event payloads are provider evidence, not repository history.  This
module extracts only the push coordinates and presentation metadata needed by
the provider-neutral collector.  Commit lists and provider-derived force-push
classification are deliberately ignored.
"""

import re

from automation.common import validate_repository

PUSH_DISPATCH_TYPE = "push-observed"
OID_RE = re.compile(r"^[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?$")


def _push_oid(value, name):
    if not isinstance(value, str) or not OID_RE.fullmatch(value):
        raise ValueError(f"GitHub push has invalid {name} object id")
    return value.lower()


def _push_ref(value):
    if not isinstance(value, str) or not (
        value.startswith("refs/heads/") or value.startswith("refs/tags/")
    ):
        raise ValueError("GitHub push has unsupported ref")
    if "\x00" in value or "\r" in value or "\n" in value:
        raise ValueError("GitHub push has invalid ref")
    return value


def _repository(payload):
    repository = payload.get("repository")
    if not isinstance(repository, dict):
        raise ValueError("GitHub push has no repository object")
    full_name = repository.get("full_name")
    validate_repository(full_name)
    canonical_url = f"https://github.com/{full_name}"
    html_url = repository.get("html_url")
    if html_url not in (None, "", canonical_url):
        raise ValueError("GitHub repository URL does not match repository identity")
    return full_name, canonical_url


def _compare_url(payload, repository_url):
    value = payload.get("compare")
    if value in (None, ""):
        return None
    if not isinstance(value, str) or not value.startswith(repository_url + "/compare/"):
        raise ValueError("GitHub compare URL does not match repository identity")
    if "\x00" in value or "\r" in value or "\n" in value:
        raise ValueError("GitHub push has invalid compare URL")
    return value


def _validate_boolean_hint(payload, name, expected):
    if name not in payload:
        return
    value = payload[name]
    if not isinstance(value, bool):
        raise ValueError(f"GitHub push has invalid {name} flag")
    if value != expected:
        raise ValueError(f"GitHub push {name} flag contradicts object coordinates")


def normalize_push_event(payload):
    """Translate a GitHub push payload into the schema-1 neutral envelope."""

    if not isinstance(payload, dict):
        raise ValueError("GitHub push event is not an object")
    repository, repository_url = _repository(payload)
    ref = _push_ref(payload.get("ref"))
    before = _push_oid(payload.get("before"), "before")
    after = _push_oid(payload.get("after"), "after")
    if len(before) != len(after):
        raise ValueError("GitHub push object ids use inconsistent formats")

    zero = "0" * len(before)
    created = before == zero
    deleted = after == zero
    if created and deleted:
        raise ValueError("GitHub push cannot create and delete the same ref")
    _validate_boolean_hint(payload, "created", created)
    _validate_boolean_hint(payload, "deleted", deleted)
    if "forced" in payload and not isinstance(payload["forced"], bool):
        raise ValueError("GitHub push has invalid forced flag")

    # `commits`, `head_commit`, and `forced` are intentionally not propagated.
    # Git is authority for history, commit metadata, and ancestry.
    return {
        "schema": 1,
        "event": "push",
        "repository": repository,
        "repository_url": repository_url,
        "ref": ref,
        "before": before,
        "after": after,
        "compare_url": _compare_url(payload, repository_url),
    }


def validate_dispatched_envelope(envelope):
    """Validate the small neutral envelope before repository materialization."""

    if not isinstance(envelope, dict):
        raise ValueError("push dispatch envelope is not an object")
    if envelope.get("schema") != 1 or envelope.get("event") != "push":
        raise ValueError("unsupported push dispatch envelope")
    repository = envelope.get("repository")
    validate_repository(repository)
    canonical_url = f"https://github.com/{repository}"
    if envelope.get("repository_url") != canonical_url:
        raise ValueError("push dispatch repository URL is not canonical")
    _push_ref(envelope.get("ref"))
    before = _push_oid(envelope.get("before"), "before")
    after = _push_oid(envelope.get("after"), "after")
    if len(before) != len(after):
        raise ValueError("push dispatch object ids use inconsistent formats")
    if set(before) == {"0"} and set(after) == {"0"}:
        raise ValueError("push dispatch cannot create and delete the same ref")
    compare_url = envelope.get("compare_url")
    if compare_url is not None:
        if not isinstance(compare_url, str) or not compare_url.startswith(
            canonical_url + "/compare/"
        ):
            raise ValueError("push dispatch compare URL is not canonical")
    return dict(envelope)


def repository_dispatch_payload(envelope):
    return {
        "event_type": PUSH_DISPATCH_TYPE,
        "client_payload": {"envelope": validate_dispatched_envelope(envelope)},
    }


def envelope_from_repository_dispatch(payload):
    if not isinstance(payload, dict) or payload.get("action") != PUSH_DISPATCH_TYPE:
        raise ValueError("unsupported GitHub repository dispatch")
    client_payload = payload.get("client_payload")
    if not isinstance(client_payload, dict):
        raise ValueError("GitHub repository dispatch has no client payload")
    return validate_dispatched_envelope(client_payload.get("envelope"))


def clone_url(repository):
    """Return the canonical public Git URL for one admitted GitHub repository."""

    validate_repository(repository)
    return f"https://github.com/{repository}.git"
