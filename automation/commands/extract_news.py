import sys
from pathlib import Path

from automation.common import validate_release_tag
from automation.news import extract_release
from ._util import error


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 3:
        print(f"usage: {sys.argv[0]} TAG NEWS OUTPUT", file=sys.stderr)
        return 2
    tag, news_path, output_path = argv
    try:
        version = validate_release_tag(tag)
        text = Path(news_path).read_text(encoding="utf-8")
        Path(output_path).write_text(extract_release(text, version), encoding="utf-8")
    except (OSError, ValueError) as exc:
        return error(exc)
    print(f"release notes: {version}")
    return 0
