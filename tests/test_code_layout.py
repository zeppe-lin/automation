#!/usr/bin/env python3

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CodeLayoutTest(unittest.TestCase):
    def test_libexec_files_are_thin_command_adapters(self):
        for path in sorted((ROOT / "libexec").glob("*.py")):
            with self.subTest(command=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertLessEqual(
                    len(text.splitlines()), 20,
                    f"{path.name} contains implementation instead of adapter code",
                )
                tree = ast.parse(text)
                imported = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imported.update(alias.name.split(".", 1)[0] for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imported.add(node.module.split(".", 1)[0])
                self.assertTrue(
                    imported <= {"automation", "pathlib", "sys"},
                    f"{path.name} imports implementation dependency directly: {sorted(imported)}",
                )
                self.assertIn("automation.commands.", text)

    def test_workflow_does_not_call_python_modules_behind_library_boundary(self):
        for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("python3 -m automation.", text)


if __name__ == "__main__":
    unittest.main()
