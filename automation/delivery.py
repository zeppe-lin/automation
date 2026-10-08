"""Delivery controllers for rendered release and push artifacts.

Rendering and transport are separate authorities.  These controllers bind a
rendered artifact to durable Git evidence, serialize effects within one
destination, and refuse to infer success after an uncertain transport attempt.
"""

import json
import os
import smtplib
from pathlib import Path, PurePosixPath

from . import gitstate
from .irc import send as send_irc
from .mail import send as send_mail
from .render import IRC_TEMPLATE_VERSION, MAIL_DEV_TEMPLATE_VERSION, MAIL_USER_TEMPLATE_VERSION
from .policy import classify_push

DELIVERY_ERRORS = (OSError, KeyError, ValueError, json.JSONDecodeError, smtplib.SMTPException)


def require_environment(destination, env=os.environ):
    if destination.startswith("mail-"):
        for name in ("SMTP_HOST", "MAIL_FROM", "MAIL_TO"):
            if not env.get(name, "").strip():
                raise ValueError(f"{name} is required")
        username = env.get("SMTP_USERNAME", "").strip()
        password = env.get("SMTP_PASSWORD", "")
        if bool(username) != bool(password):
            raise ValueError(
                "SMTP_USERNAME and SMTP_PASSWORD must be configured together"
            )
        return

    for name in ("IRC_HOST", "IRC_CHANNEL", "IRC_NICK", "IRC_SASL_PASSWORD"):
        if not env.get(name, "").strip():
            raise ValueError(f"{name} is required")


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _artifact_path(delivery, relative):
    if not isinstance(relative, str) or not relative:
        raise ValueError("delivery plan contains an invalid artifact path")
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ValueError("delivery plan artifact escapes delivery directory")
    root = Path(delivery).resolve()
    target = (root / Path(*path.parts)).resolve()
    try:
        target.relative_to(root)
    except ValueError as error:
        raise ValueError("delivery plan artifact escapes delivery directory") from error
    return target


def _validate_push_plan(delivery, destination):
    manifest = _read_json(Path(delivery) / "manifest.json")
    plan = _read_json(Path(delivery) / "delivery-plan.json")
    if manifest.get("schema") != 1 or manifest.get("event") != "push":
        raise ValueError("unsupported push manifest")
    if plan.get("schema") != 1 or plan.get("event") != "push-delivery":
        raise ValueError("unsupported push delivery plan")
    if plan.get("event_id") != manifest.get("event_id"):
        raise ValueError("delivery plan event ID does not match manifest")
    if plan.get("repository") != manifest.get("repository"):
        raise ValueError("delivery plan repository does not match manifest")
    if manifest.get("commit_count") != len(manifest.get("commits", [])):
        raise ValueError("push manifest commit count is inconsistent")

    reclassified = classify_push(manifest)
    if reclassified.get("routing") != manifest.get("routing"):
        raise ValueError("push manifest routing is not derived from commit policy")
    for actual, expected in zip(manifest.get("commits", []), reclassified["commits"]):
        if actual.get("classification") != expected.get("classification"):
            raise ValueError("push manifest classification is not derived from commit policy")

    deliveries = plan.get("deliveries")
    if not isinstance(deliveries, dict) or destination not in deliveries:
        raise ValueError(f"delivery plan has no {destination} destination")
    entries = deliveries[destination]
    if not isinstance(entries, list):
        raise ValueError("delivery plan destination is not an ordered list")

    if destination == "mail-dev":
        expected_items = [commit["sha"] for commit in manifest.get("commits", [])]
    elif destination == "mail-user":
        expected_items = [
            commit["sha"]
            for commit in manifest.get("commits", [])
            if "mail-user" in commit.get("classification", {}).get("destinations", [])
        ]
    else:
        expected_items = ["push"] if (
            bool(manifest.get("commits")) or manifest.get("before") != manifest.get("after")
        ) else []

    seen = set()
    validated = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("delivery plan entry is not an object")
        artifact = _artifact_path(delivery, entry.get("artifact"))
        event_id = entry.get("event_id")
        item_id = entry.get("item_id")
        template = entry.get("template")
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("delivery plan entry has no event ID")
        if not isinstance(item_id, str) or not item_id:
            raise ValueError("delivery plan entry has no item ID")
        if not isinstance(template, int) or template < 1:
            raise ValueError("delivery plan entry has invalid template version")
        identity = (event_id, item_id, template)
        if identity in seen:
            raise ValueError("delivery plan contains a duplicate item")
        seen.add(identity)
        validated.append(
            {
                "artifact": artifact,
                "event_id": event_id,
                "item_id": item_id,
                "template": template,
            }
        )

    actual_items = [entry["item_id"] for entry in validated]
    if actual_items != expected_items:
        raise ValueError("delivery plan order does not match manifest routing")
    for entry in validated:
        expected_event = (
            manifest["event_id"]
            if destination == "irc"
            else f"{manifest['event_id']}:commit:{entry['item_id']}"
        )
        if entry["event_id"] != expected_event:
            raise ValueError("delivery plan event ID does not match manifest item")
        expected_template = {
            "mail-dev": MAIL_DEV_TEMPLATE_VERSION,
            "mail-user": MAIL_USER_TEMPLATE_VERSION,
            "irc": IRC_TEMPLATE_VERSION,
        }[destination]
        if entry["template"] != expected_template:
            raise ValueError("delivery plan template does not match renderer version")
    return manifest, validated


def _mail_payload(entry, destination):
    payload = _read_json(entry["artifact"])
    if payload.get("schema") != 1:
        raise ValueError("unsupported mail payload")
    if payload.get("destination") != destination:
        raise ValueError("mail payload destination does not match delivery plan")
    for field in ("event_id", "item_id", "template"):
        if payload.get(field) != entry[field]:
            raise ValueError(f"mail payload {field} does not match delivery plan")
    if not isinstance(payload.get("subject"), str) or not isinstance(
        payload.get("body"), str
    ):
        raise ValueError("mail payload is incomplete")
    return payload


def _irc_payload(entry):
    text = entry["artifact"].read_text(encoding="utf-8").strip()
    if not text or "\r" in text or "\n" in text:
        raise ValueError("IRC message must contain exactly one non-empty line")
    return text


def deliver_push(delivery_dir, destination, force=False, env=os.environ):
    """Deliver one push destination in plan order.

    Mail items are individual commit effects.  They are claimed, submitted, and
    marked delivered one at a time.  Failure or an unresolved prior attempt
    stops the sequence before later commits, preserving observable commit order.
    IRC has at most one push-level item and follows the same evidence protocol.
    """

    if destination not in gitstate.DESTINATIONS:
        raise ValueError(f"unsupported destination: {destination}")
    delivery = Path(delivery_dir)
    manifest, entries = _validate_push_plan(delivery, destination)
    if not entries:
        return 0, f"{destination}: nothing to deliver"

    require_environment(destination, env)
    ledger = gitstate.DeliveryLedger.from_environment(env)
    delivered = 0
    skipped = 0

    for entry in entries:
        if destination.startswith("mail-"):
            payload = _mail_payload(entry, destination)
        else:
            payload = _irc_payload(entry)

        key = gitstate.push_key(
            manifest["repository"],
            manifest["event_id"],
            destination,
            entry["item_id"],
            entry["template"],
        )
        status, message = ledger.claim(key, force)
        if status == gitstate.ALREADY_DELIVERED:
            skipped += 1
            continue
        if status != 0:
            return status, message

        if destination.startswith("mail-"):
            send_mail(payload, env)
        else:
            send_irc(payload, env)

        status, message = ledger.mark_delivered(key)
        if status != 0:
            return status, message
        delivered += 1

    return 0, f"{destination}: delivered {delivered}, already delivered {skipped}"


def deliver_release(delivery_dir, destination, force=False, env=os.environ):
    if destination not in gitstate.DESTINATIONS:
        raise ValueError(f"unsupported destination: {destination}")
    delivery = Path(delivery_dir)
    manifest = _read_json(delivery / "manifest.json")
    require_environment(destination, env)

    status, message = gitstate.claim(
        manifest["repository"], manifest["tag"], destination, force, env
    )
    if status == gitstate.ALREADY_DELIVERED:
        return 0, message
    if status != 0:
        return status, message

    if destination == "irc":
        text = (delivery / "irc.txt").read_text(encoding="utf-8").strip()
        if not text or "\r" in text or "\n" in text:
            raise ValueError("IRC message must contain exactly one non-empty line")
        send_irc(text, env)
    else:
        payload = _read_json(delivery / f"{destination}.json")
        send_mail(payload, env)

    status, delivered_message = gitstate.mark_delivered(
        manifest["repository"], manifest["tag"], destination, env
    )
    return status, delivered_message
