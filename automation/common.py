"""Small shared validation and text helpers."""

import os
import re

CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
REPOSITORY_RE = re.compile(r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<name>[A-Za-z0-9_.-]+)$")
TAG_RE = re.compile(
    r"^v(?P<version>"
    r"[0-9][0-9A-Za-z]*"
    r"(?:\.[0-9A-Za-z]+)+"
    r"(?:[-+._][0-9A-Za-z.-]+)?"
    r")$"
)


def env_required(name, env=os.environ):
    value = env.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def env_default(name, default, env=os.environ):
    value = env.get(name, "").strip()
    return value or default


def parse_port(name, value):
    try:
        port = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if not 1 <= port <= 65535:
        raise ValueError(f"{name} must be between 1 and 65535")
    return port


def validate_repository(repository, allowed_owner="zeppe-lin"):
    match = REPOSITORY_RE.fullmatch(repository)
    if not match:
        raise ValueError(f"invalid repository: {repository}")
    if allowed_owner is not None and match.group("owner") != allowed_owner:
        raise ValueError(f"repository owner is not allowed: {match.group('owner')}")
    return match.group("owner"), match.group("name")


def validate_release_tag(tag):
    match = TAG_RE.fullmatch(tag)
    if not match:
        raise ValueError(f"unsupported release tag: {tag}")
    return match.group("version")


def clean_header(value):
    value = CONTROL_RE.sub("", str(value)).replace("\r", " ").replace("\n", " ")
    return " ".join(value.split())


def limit_utf8(text, limit, suffix="..."):
    data = text.encode("utf-8")
    if len(data) <= limit:
        return text

    budget = max(0, limit - len(suffix.encode("utf-8")))
    clipped = data[:budget]
    while clipped:
        try:
            return clipped.decode("utf-8") + suffix
        except UnicodeDecodeError:
            clipped = clipped[:-1]
    return suffix.encode("utf-8")[:limit].decode("utf-8", "ignore")
