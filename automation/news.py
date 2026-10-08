"""NEWS.md release-section projection."""

from .common import validate_release_tag


def heading_version(line):
    if not line.startswith("## "):
        return None

    heading = line[3:].strip()
    for separator in (" — ", " - "):
        if separator in heading:
            heading = heading.split(separator, 1)[0].rstrip()
            break
    if not heading:
        return None
    return heading.split()[-1]


def extract_release(text, version):
    lines = text.splitlines(keepends=True)
    starts = [
        index + 1
        for index, line in enumerate(lines)
        if heading_version(line.rstrip("\r\n")) == version
    ]

    if not starts:
        raise ValueError(f"NEWS.md has no section for version {version}")
    if len(starts) != 1:
        raise ValueError(f"NEWS.md has multiple sections for version {version}")

    start = starts[0]
    end = next(
        (index for index in range(start, len(lines)) if lines[index].startswith("## ")),
        len(lines),
    )
    body = "".join(lines[start:end]).strip()
    if not body:
        raise ValueError(f"NEWS.md section for version {version} is empty")
    return body + "\n"


def extract_tag(text, tag):
    return extract_release(text, validate_release_tag(tag))
