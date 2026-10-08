import json
import sys
from pathlib import Path

from automation.release import render_release
from ._util import error


def write_artifacts(manifest, output_dir):
    user, dev, irc = render_release(manifest)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for name, value in (
        ("manifest.json", manifest),
        ("mail-user.json", user),
        ("mail-dev.json", dev),
    ):
        (output / name).write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    (output / "irc.txt").write_text(irc, encoding="utf-8")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(f"usage: {sys.argv[0]} MANIFEST OUTPUT-DIR", file=sys.stderr)
        return 2
    try:
        manifest = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
        write_artifacts(manifest, argv[1])
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        return error(exc)
    return 0
