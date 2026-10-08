#!/usr/bin/env python3

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
ACTIONS = ROOT / ".github" / "actions"
UNPINNED_USE = re.compile(r"^\s*uses:\s+([^./][^@]*)@([^\s#]+)", re.MULTILINE)


def run_blocks(text):
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped.startswith("run:"):
            continue
        indent = len(line) - len(stripped)
        value = stripped[len("run:") :].strip()
        block = [value] if value not in {"", ">", ">-", "|", "|-"} else []
        cursor = index + 1
        while cursor < len(lines):
            child = lines[cursor]
            if child.strip() and len(child) - len(child.lstrip()) <= indent:
                break
            if child.strip():
                block.append(child.strip())
            cursor += 1
        yield " ".join(block)


class WorkflowPolicyTest(unittest.TestCase):
    def yaml_files(self):
        return list(WORKFLOWS.glob("*.yml")) + list(ACTIONS.glob("*/action.yml"))

    def test_workflow_templates_do_not_embed_programs(self):
        for path in self.yaml_files():
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertNotIn("<<'PY'", text)
                self.assertNotIn('<<"PY"', text)
                self.assertNotIn("python3 - ", text)
                self.assertNotIn("set -euo pipefail", text)

    def test_external_actions_are_pinned_to_full_commit_sha(self):
        for path in self.yaml_files():
            text = path.read_text(encoding="utf-8")
            for match in UNPINNED_USE.finditer(text):
                reference = match.group(2)
                with self.subTest(path=path, use=match.group(0)):
                    self.assertRegex(reference, r"^[0-9a-f]{40}$")

    def test_run_steps_delegate_to_repository_commands(self):
        for path in self.yaml_files():
            blocks = list(run_blocks(path.read_text(encoding="utf-8")))
            for block in blocks:
                with self.subTest(path=path, run=block):
                    self.assertIn("libexec/", block)
                    self.assertNotIn("&&", block)
                    self.assertNotIn(";", block)

    def test_central_delivery_workflows_use_real_queues(self):
        for name, group in (
            ("deliver-release.yml", "release-delivery"),
            ("deliver-push.yml", "push-delivery"),
        ):
            text = (WORKFLOWS / name).read_text(encoding="utf-8")
            with self.subTest(workflow=name):
                self.assertIn(f"group: {group}", text)
                self.assertIn("queue: max", text)
                self.assertIn("cancel-in-progress: false", text)

    def test_push_workflow_is_a_thin_central_adapter(self):
        text = (WORKFLOWS / "deliver-push.yml").read_text(encoding="utf-8")
        self.assertIn("push-observed", text)
        self.assertIn("libexec/prepare-github-push.py", text)
        self.assertEqual(text.count("libexec/deliver-push.py"), 3)
        self.assertIn("PUSH_DELIVERY_ENABLED", text)

    def test_queue_push_action_reads_provider_event_file(self):
        text = (ACTIONS / "queue-push" / "action.yml").read_text(encoding="utf-8")
        self.assertIn("$GITHUB_EVENT_PATH", text)
        self.assertIn("libexec/queue-github-push.py", text)
        self.assertNotIn("github.event.commits", text)


if __name__ == "__main__":
    unittest.main()
