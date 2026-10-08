#!/usr/bin/env python3

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREPARE = ROOT / "libexec" / "prepare-release.py"


class ReleaseCommandsTest(unittest.TestCase):
    def test_prepare_is_fully_offline_with_fixture_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            fixture = tmpdir / "release.json"
            output = tmpdir / "output"
            fixture.write_text(
                json.dumps(
                    {
                        "tag_name": "v6.3",
                        "name": "v6.3",
                        "draft": False,
                        "prerelease": False,
                        "html_url": "https://github.com/zeppe-lin/pkgman/releases/tag/v6.3",
                        "published_at": "2026-10-08T12:00:00Z",
                        "body": "### Changes\n\n* One.\n",
                    }
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    str(PREPARE),
                    "zeppe-lin/pkgman",
                    "v6.3",
                    str(output),
                    "--release-json",
                    str(fixture),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((output / "manifest.json").is_file())
            self.assertTrue((output / "mail-user.json").is_file())
            self.assertTrue((output / "mail-dev.json").is_file())
            self.assertTrue((output / "irc.txt").is_file())


if __name__ == "__main__":
    unittest.main()
