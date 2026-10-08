#!/usr/bin/env python3

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
ACTIONS = ROOT / ".github" / "actions"
SHA_USE = re.compile(r"^\s*uses:\s+[^./][^@]*@([0-9a-f]{40})\s*(?:#.*)?$", re.MULTILINE)
UNPINNED_USE = re.compile(r"^\s*uses:\s+([^./][^@]*)@([^\s#]+)", re.MULTILINE)


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
        workflow = (WORKFLOWS / "deliver-release.yml").read_text(encoding="utf-8")
        run_lines = [line.strip() for line in workflow.splitlines() if line.strip().startswith("run:")]
        self.assertTrue(run_lines)
        for line in run_lines:
            self.assertIn("libexec/", line)


if __name__ == "__main__":
    unittest.main()
