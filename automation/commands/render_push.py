import json
import sys
from pathlib import Path

from automation.render import render_push
from ._util import error


def write_artifacts(manifest, output_dir):
    dev, user, irc, requirements = render_push(manifest)
    output = Path(output_dir)
    dev_dir = output / "mail-dev"
    user_dir = output / "mail-user"
    dev_dir.mkdir(parents=True, exist_ok=True)
    user_dir.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "requirements.json").write_text(
        json.dumps(requirements, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for index, payload in enumerate(dev, 1):
        (dev_dir / f"{index:04d}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    user_index = 0
    for commit_index, commit in enumerate(manifest["commits"], 1):
        if "mail-user" not in commit["classification"]["destinations"]:
            continue
        payload = user[user_index]
        user_index += 1
        (user_dir / f"{commit_index:04d}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if irc is not None:
        (output / "irc.txt").write_text(irc, encoding="utf-8")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(f"usage: {sys.argv[0]} MANIFEST OUTPUT-DIR", file=sys.stderr)
        return 2
    try:
        manifest = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
        write_artifacts(manifest, argv[1])
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        return error(exc)
    return 0
