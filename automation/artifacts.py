"""Filesystem representation of deterministic automation artifacts.

Renderers produce data.  This module owns the on-disk layout consumed by local
operators, workflow artifacts, and delivery commands.  Command adapters should
not duplicate that layout policy.
"""

import json
from pathlib import Path

from .release import render_release
from .render import IRC_TEMPLATE_VERSION, render_push


def write_json(path, value):
    Path(path).write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_release_artifacts(manifest, output_dir):
    user, dev, irc = render_release(manifest)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "manifest.json", manifest)
    write_json(output / "mail-user.json", user)
    write_json(output / "mail-dev.json", dev)
    (output / "irc.txt").write_text(irc, encoding="utf-8")


def _plan_entry(artifact, payload):
    return {
        "artifact": artifact,
        "event_id": payload["event_id"],
        "item_id": payload["item_id"],
        "template": payload["template"],
    }


def write_push_artifacts(manifest, output_dir):
    dev, user, irc, requirements = render_push(manifest)
    output = Path(output_dir)
    dev_dir = output / "mail-dev"
    user_dir = output / "mail-user"
    dev_dir.mkdir(parents=True, exist_ok=True)
    user_dir.mkdir(parents=True, exist_ok=True)

    write_json(output / "manifest.json", manifest)
    write_json(output / "requirements.json", requirements)

    plan = {
        "schema": 1,
        "event": "push-delivery",
        "event_id": manifest["event_id"],
        "repository": manifest["repository"],
        "deliveries": {"mail-dev": [], "mail-user": [], "irc": []},
    }

    for index, payload in enumerate(dev, 1):
        relative = f"mail-dev/{index:04d}.json"
        write_json(output / relative, payload)
        plan["deliveries"]["mail-dev"].append(_plan_entry(relative, payload))

    user_index = 0
    for commit_index, commit in enumerate(manifest["commits"], 1):
        if "mail-user" not in commit["classification"]["destinations"]:
            continue
        payload = user[user_index]
        user_index += 1
        relative = f"mail-user/{commit_index:04d}.json"
        write_json(output / relative, payload)
        plan["deliveries"]["mail-user"].append(_plan_entry(relative, payload))

    if irc is not None:
        (output / "irc.txt").write_text(irc, encoding="utf-8")
        plan["deliveries"]["irc"].append(
            {
                "artifact": "irc.txt",
                "event_id": manifest["event_id"],
                "item_id": "push",
                "template": IRC_TEMPLATE_VERSION,
            }
        )

    write_json(output / "delivery-plan.json", plan)
