#!/usr/bin/env python3

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


collect = load("collect_release", "libexec/collect-github-release.py")
render = load("render_release", "libexec/render-release.py")


class CollectReleaseTest(unittest.TestCase):
    def payload(self):
        return {
            "tag_name": "v6.3",
            "name": "v6.3",
            "draft": False,
            "prerelease": False,
            "html_url": "https://github.com/zeppe-lin/pkgman/releases/tag/v6.3",
            "published_at": "2026-10-06T12:00:00Z",
            "body": "### Changes\n\n* One.\n",
        }

    def test_normalizes_verified_release(self):
        result = collect.normalize_release("zeppe-lin/pkgman", "v6.3", self.payload())
        self.assertEqual(result["event_id"], "release:zeppe-lin/pkgman:v6.3")
        self.assertEqual(result["project"], "pkgman")
        self.assertEqual(result["notes"], "### Changes\n\n* One.\n")

    def test_rejects_repository_outside_project(self):
        with self.assertRaisesRegex(ValueError, "owner is not allowed"):
            collect.normalize_release("other/pkgman", "v6.3", self.payload())

    def test_rejects_mismatched_release_tag(self):
        payload = self.payload()
        payload["tag_name"] = "v6.2"
        with self.assertRaisesRegex(ValueError, "does not match"):
            collect.normalize_release("zeppe-lin/pkgman", "v6.3", payload)

    def test_rejects_draft_or_empty_release(self):
        payload = self.payload()
        payload["draft"] = True
        with self.assertRaisesRegex(ValueError, "draft"):
            collect.normalize_release("zeppe-lin/pkgman", "v6.3", payload)

        payload = self.payload()
        payload["body"] = "  "
        with self.assertRaisesRegex(ValueError, "no release notes"):
            collect.normalize_release("zeppe-lin/pkgman", "v6.3", payload)


class RenderReleaseTest(unittest.TestCase):
    def manifest(self):
        return {
            "schema": 1,
            "event": "release",
            "event_id": "release:zeppe-lin/pkgman:v6.3",
            "repository": "zeppe-lin/pkgman",
            "project": "pkgman",
            "tag": "v6.3",
            "title": "v6.3",
            "release_url": "https://github.com/zeppe-lin/pkgman/releases/tag/v6.3",
            "notes": "### Changes\n\n* One.\n",
        }

    def test_renders_separate_channel_payloads(self):
        user, dev, irc_line = render.render(self.manifest())
        self.assertEqual(user["subject"], "[release][pkgman] v6.3")
        self.assertIn("pkgman v6.3 has been released.", user["body"])
        self.assertIn("Repository: https://github.com/zeppe-lin/pkgman", dev["body"])
        self.assertEqual(
            irc_line,
            "[release] pkgman v6.3 released — https://github.com/zeppe-lin/pkgman/releases/tag/v6.3\n",
        )

    def test_strips_control_characters_from_headers_and_irc(self):
        manifest = self.manifest()
        manifest["project"] = "pkg\x01man\nnoise"
        user, _, irc_line = render.render(manifest)
        self.assertNotIn("\x01", user["subject"])
        self.assertNotIn("\nnoise", user["subject"])
        self.assertNotIn("\x01", irc_line)
        self.assertEqual(irc_line.count("\n"), 1)

    def test_utf8_limit_does_not_split_characters(self):
        value = "Ж" * 400
        result = render.limit_utf8(value, 31)
        self.assertLessEqual(len(result.encode("utf-8")), 31)
        result.encode("utf-8")


if __name__ == "__main__":
    unittest.main()
