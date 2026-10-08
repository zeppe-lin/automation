"""Codebook event classification and routing rules that are normative today.

This module deliberately implements only doctrine that the Codebook states
unambiguously. Trailer cardinality and durable-artifact path rules remain a
Codebook issue rather than being invented here.
"""

import re

TAGS = ("news", "security", "breaking", "deprecation")
TAG_INDEX = {tag: index for index, tag in enumerate(TAGS)}
TRAILERS = ("Affected", "Action", "News", "Migration", "Release-Note", "Reference")
LEADING_TAG_RE = re.compile(r"^\[([^\]\r\n]+)\]")


class PolicyError(ValueError):
    pass


def classify_subject(subject):
    # Scan the complete leading bracket run before deciding where maintained
    # event tags stop. Unknown human prefixes remain permitted, but they must
    # not be able to hide a maintained or retired automation tag behind them.
    tokens = []
    offset = 0
    rest = subject
    while rest.startswith("["):
        match = LEADING_TAG_RE.match(rest)
        if not match:
            break
        token = match.group(1)
        tokens.append((token, offset, offset + match.end()))
        offset += match.end()
        rest = rest[match.end():]

    for token, _, _ in tokens:
        lower = token.lower()
        if lower == "notify":
            raise PolicyError("[notify] is obsolete and invalid for new commits")
        if lower in TAG_INDEX and token != lower:
            raise PolicyError(f"event tag must use exact lowercase spelling: [{token}]")

    tags = []
    consumed = 0
    saw_unknown = False
    for token, _, end in tokens:
        lower = token.lower()
        if lower not in TAG_INDEX:
            saw_unknown = True
            continue
        if saw_unknown:
            raise PolicyError("maintained event tags must precede unknown bracket prefixes")
        tags.append(lower)
        consumed = end

    if len(tags) != len(set(tags)):
        raise PolicyError("event tag is repeated")
    positions = [TAG_INDEX[tag] for tag in tags]
    if positions != sorted(positions):
        raise PolicyError("event tags are not in canonical Codebook order")
    if "breaking" in tags and "news" not in tags:
        raise PolicyError("[breaking] must be combined with [news]")

    summary = subject[consumed:] if tags else subject
    return tags, summary.lstrip()


def recognized_trailers(trailers):
    result = {}
    for key in TRAILERS:
        values = trailers.get(key, [])
        if values:
            result[key] = list(values)
    return result


def route(tags):
    destinations = ["mail-dev", "irc"]
    requirements = []
    if tags:
        destinations.insert(1, "mail-user")
    if "news" in tags:
        requirements.append("system-news")
    if "breaking" in tags:
        requirements.append("release-note-review")
    return destinations, requirements


def classify_commit(commit):
    tags, summary = classify_subject(commit["title"])
    destinations, requirements = route(tags)
    classified = dict(commit)
    classified["classification"] = {
        "tags": tags,
        "summary": summary,
        "trailers": recognized_trailers(commit.get("trailers", {})),
        "destinations": destinations,
        "requirements": requirements,
    }
    return classified


def classify_push(manifest):
    if manifest.get("schema") != 1 or manifest.get("event") != "push":
        raise PolicyError("unsupported event manifest")
    classified = dict(manifest)
    classified["commits"] = [classify_commit(commit) for commit in manifest["commits"]]
    classified["routing"] = {
        "mail-dev": sum(
            "mail-dev" in commit["classification"]["destinations"]
            for commit in classified["commits"]
        ),
        "mail-user": sum(
            "mail-user" in commit["classification"]["destinations"]
            for commit in classified["commits"]
        ),
        "irc": bool(classified["commits"]) or classified.get("before") != classified.get("after"),
        "system-news-checks": sum(
            "system-news" in commit["classification"]["requirements"]
            for commit in classified["commits"]
        ),
        "release-note-reviews": sum(
            "release-note-review" in commit["classification"]["requirements"]
            for commit in classified["commits"]
        ),
    }
    return classified
