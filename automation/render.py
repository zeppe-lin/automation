"""Deterministic channel rendering for classified push manifests."""

from .common import CONTROL_RE, clean_header, limit_utf8
from .policy import TAGS


def _ref_label(ref):
    for prefix in ("refs/heads/", "refs/tags/"):
        if ref.startswith(prefix):
            return ref[len(prefix):]
    return ref


def _repository_url(manifest):
    return manifest.get("repository_url") or f"https://github.com/{manifest['repository']}"


def _event_id(manifest, commit):
    return f"{manifest['event_id']}:commit:{commit['sha']}"


def _message_text(commit):
    text = commit["title"]
    if commit.get("body"):
        text += "\n\n" + commit["body"]
    return text.rstrip() + "\n"


def render_development_mail(manifest, commit):
    project = clean_header(manifest["repository"].split("/", 1)[1])
    ref = clean_header(_ref_label(manifest["ref"]))
    title = clean_header(commit["title"])
    author = clean_header(f"{commit['author_name']} <{commit['author_email']}>")
    repository_url = clean_header(_repository_url(manifest))
    commit_url = clean_header(commit.get("commit_url") or f"{repository_url}/commit/{commit['sha']}")

    body = (
        f"Commit: {commit['sha']}\n"
        f"Author: {author}\n"
        f"Ref: {manifest['ref']}\n"
        f"Repository: {repository_url}\n\n"
        f"{_message_text(commit)}"
    )
    if commit.get("diffstat"):
        body += "\n" + commit["diffstat"].rstrip() + "\n"
    body += f"\n{commit_url}\n"
    return {
        "schema": 1,
        "event_id": _event_id(manifest, commit),
        "destination": "mail-dev",
        "subject": f"[{project}:{ref}] {commit['short_sha']}: {title}",
        "body": body,
    }


def _trailer_lines(classification):
    trailers = classification.get("trailers", {})
    lines = []
    for key in ("Affected", "Action", "News", "Migration", "Release-Note"):
        for value in trailers.get(key, []):
            lines.append(f"{key}: {value}")
    references = trailers.get("Reference", [])
    if references:
        lines.append("References:")
        lines.extend(f"  {value}" for value in references)
    return lines



def _body_without_trailer_block(commit):
    body = commit.get("body", "").rstrip("\n")
    if not body or not commit.get("trailers"):
        return body
    lines = body.splitlines()
    blank = max((index for index, line in enumerate(lines) if not line.strip()), default=-1)
    candidate = lines[blank + 1 :]
    if not candidate:
        return body
    trailer_like = True
    for line in candidate:
        if not line.strip():
            trailer_like = False
            break
        if line[:1].isspace():
            continue
        key, separator, _ = line.partition(":")
        if not separator or not key or any(ch.isspace() for ch in key):
            trailer_like = False
            break
    if not trailer_like:
        return body
    return "\n".join(lines[:blank]).rstrip()

def render_user_mail(manifest, commit):
    classification = commit["classification"]
    if "mail-user" not in classification["destinations"]:
        raise ValueError("commit is not routed to the user mailing list")

    project = clean_header(manifest["repository"].split("/", 1)[1])
    tags = "".join(f"[{tag}]" for tag in classification["tags"])
    summary = clean_header(classification["summary"] or commit["title"])
    repository_url = clean_header(_repository_url(manifest))
    commit_url = clean_header(commit.get("commit_url") or f"{repository_url}/commit/{commit['sha']}")
    lines = _trailer_lines(classification)

    body = summary + "\n\n"
    if lines:
        body += "\n".join(lines) + "\n\n"
    details = _body_without_trailer_block(commit)
    if details:
        body += details + "\n\n"
    body += f"Commit: {commit_url}\n"

    return {
        "schema": 1,
        "event_id": _event_id(manifest, commit),
        "destination": "mail-user",
        "subject": f"{tags}[{project}] {summary}",
        "body": body,
    }


def render_irc(manifest):
    commits = manifest["commits"]
    if not commits:
        return None

    project = clean_header(manifest["repository"].split("/", 1)[1])
    ref = clean_header(_ref_label(manifest["ref"]))
    seen = {tag for commit in commits for tag in commit["classification"]["tags"]}
    prefix = "".join(f"[{tag}]" for tag in TAGS if tag in seen)
    if manifest.get("forced"):
        prefix += "[force-push]"

    summaries = [
        clean_header(commit["classification"]["summary"] or commit["title"])
        for commit in commits
    ]
    shown = summaries[:2]
    detail = "; ".join(shown)
    if len(summaries) > len(shown):
        detail += f"; +{len(summaries) - len(shown)} more"

    url = manifest.get("compare_url")
    if not url:
        last = commits[-1]
        url = last.get("commit_url") or _repository_url(manifest)
    label = f"{prefix} " if prefix else ""
    line = f"{label}{project}:{ref}: {len(commits)} commit(s): {detail} — {url}"
    line = CONTROL_RE.sub("", " ".join(line.replace("\r", " ").replace("\n", " ").split()))
    return limit_utf8(line, 360) + "\n"


def render_requirements(manifest):
    result = []
    for commit in manifest["commits"]:
        requirements = commit["classification"]["requirements"]
        if requirements:
            result.append({
                "sha": commit["sha"],
                "short_sha": commit["short_sha"],
                "title": commit["title"],
                "requirements": list(requirements),
                "trailers": dict(commit["classification"].get("trailers", {})),
            })
    return result


def render_push(manifest):
    if manifest.get("schema") != 1 or manifest.get("event") != "push":
        raise ValueError("unsupported push manifest")
    dev = [render_development_mail(manifest, commit) for commit in manifest["commits"]]
    user = [
        render_user_mail(manifest, commit)
        for commit in manifest["commits"]
        if "mail-user" in commit["classification"]["destinations"]
    ]
    return dev, user, render_irc(manifest), render_requirements(manifest)
