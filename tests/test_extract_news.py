#!/usr/bin/env python3

import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "actions" / "extract-news" / "extract-news.py"


class ExtractNewsTest(unittest.TestCase):
    def run_extract(self, tag, news):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            news_path = tmpdir / "NEWS.md"
            output_path = tmpdir / "release.md"
            news_path.write_text(news, encoding="utf-8")

            result = subprocess.run(
                [str(SCRIPT), tag, str(news_path), str(output_path)],
                check=False,
                capture_output=True,
                text=True,
            )

            output = None
            if output_path.exists():
                output = output_path.read_text(encoding="utf-8")

            return result, output

    def test_extracts_two_component_project_version(self):
        result, output = self.run_extract(
            "v6.3",
            "# NEWS\n\n## pkgman 6.3 — Unreleased\n\nFirst.\n\n## pkgman 6.2 — 2025-12-12\n\nOld.\n",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(output, "First.\n")

    def test_extracts_three_component_bare_version(self):
        result, output = self.run_extract(
            "v1.0.0",
            "# NEWS\n\n## 1.0.0 - 2026-08-26\n\nRelease body.\n",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(output, "Release body.\n")

    def test_preserves_subheadings_inside_release(self):
        result, output = self.run_extract(
            "v2.1.0",
            "# NEWS\n\n## tool 2.1.0 — Unreleased\n\n### Changes\n\n* One.\n\n### Fixes\n\n* Two.\n",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(output, "### Changes\n\n* One.\n\n### Fixes\n\n* Two.\n")

    def test_rejects_missing_version(self):
        result, output = self.run_extract(
            "v6.3",
            "# NEWS\n\n## pkgman 6.2 — 2025-12-12\n\nOld.\n",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIsNone(output)
        self.assertIn("no section for version 6.3", result.stderr)

    def test_rejects_duplicate_version(self):
        result, output = self.run_extract(
            "v6.3",
            "## pkgman 6.3 — Unreleased\n\nOne.\n\n## pkgman 6.3 — Later\n\nTwo.\n",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIsNone(output)
        self.assertIn("multiple sections for version 6.3", result.stderr)

    def test_rejects_empty_section(self):
        result, output = self.run_extract(
            "v6.3",
            "## pkgman 6.3 — Unreleased\n\n## pkgman 6.2 — 2025-12-12\n\nOld.\n",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIsNone(output)
        self.assertIn("section for version 6.3 is empty", result.stderr)

    def test_rejects_unsupported_tag(self):
        result, output = self.run_extract(
            "release-6.3",
            "## pkgman 6.3 — Unreleased\n\nBody.\n",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIsNone(output)
        self.assertIn("unsupported release tag", result.stderr)


if __name__ == "__main__":
    unittest.main()
