import json
import sys
from pathlib import Path

from automation.artifacts import write_release_artifacts
from ._util import error


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(f"usage: {sys.argv[0]} MANIFEST OUTPUT-DIR", file=sys.stderr)
        return 2
    try:
        manifest = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
        write_release_artifacts(manifest, argv[1])
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        return error(exc)
    return 0
