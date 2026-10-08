"""Normalized release manifests and deterministic channel rendering."""

from .common import CONTROL_RE, clean_header, limit_utf8, validate_release_tag, validate_repository


def normalize_github_release(repository, tag, payload, allowed_owner="zeppe-lin"):
    _, name = validate_repository(repository, allowed_owner)
    validate_release_tag(tag)

    if payload.get("tag_name") != tag:
        raise ValueError("GitHub release tag does not match requested tag")
    if payload.get("draft"):
        raise ValueError("GitHub release is still a draft")

    body = payload.get("body")
    if not isinstance(body, str) or not body.strip():
        raise ValueError("GitHub release has no release notes")

    html_url = payload.get("html_url")
    expected_url = f"https://github.com/{repository}/releases/tag/{tag}"
    if html_url != expected_url:
        raise ValueError("GitHub release URL does not match repository and tag")

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


def render_release(manifest):
    if manifest.get("schema") != 1 or manifest.get("event") != "release":
        raise ValueError("unsupported release manifest")

    project = clean_header(manifest["project"])
    tag = clean_header(manifest["tag"])
    title = clean_header(manifest["title"])
    repository = clean_header(manifest["repository"])
    release_url = clean_header(manifest["release_url"])
    event_id = clean_header(manifest["event_id"])
    notes = manifest["notes"].rstrip() + "\n"

    user = {
        "schema": 1,
        "event_id": event_id,
        "destination": "mail-user",
        "subject": f"[release][{project}] {tag}",
        "body": (
            f"{project} {tag} has been released.\n\n"
            f"{notes}\n"
            f"Release: {release_url}\n"
        ),
    }
    dev = {
        "schema": 1,
        "event_id": event_id,
        "destination": "mail-dev",
        "subject": f"[release][{project}] {tag}: {title}",
        "body": (
            f"Release published: {project} {tag}\n"
            f"Repository: https://github.com/{repository}\n"
            f"Release: {release_url}\n\n"
            f"{notes}"
        ),
    }

    irc = CONTROL_RE.sub("", f"[release] {project} {tag} released — {release_url}")
    irc = " ".join(irc.replace("\r", " ").replace("\n", " ").split())
    return user, dev, limit_utf8(irc, 360) + "\n"
