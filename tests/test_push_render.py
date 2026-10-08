#!/usr/bin/env python3

import unittest

from automation.render import render_push


class PushRenderTest(unittest.TestCase):
    def manifest(self):
        commits = []
        for index in range(3):
            tagged = index == 1
            tags = ["news", "breaking"] if tagged else []
            destinations = ["mail-dev", "mail-user", "irc"] if tagged else ["mail-dev", "irc"]
            requirements = ["system-news", "release-note-review"] if tagged else []
            commits.append({
                "sha": f"{index + 1:040x}",
                "short_sha": f"{index + 1:07x}",
                "parents": [],
                "title": ("[news][breaking] api: incompatible transition" if tagged else f"ordinary: change {index}"),
                "body": "Detailed body.",
                "author_name": "Maintainer",
                "author_email": "maintainer@example.invalid",
                "authored_at": "2026-10-08T12:00:00+00:00",
                "trailers": {},
                "diffstat": " file | 1 +\n 1 file changed, 1 insertion(+)",
                "commit_url": f"https://example.invalid/commit/{index + 1}",
                "classification": {
                    "tags": tags,
                    "summary": "api: incompatible transition" if tagged else f"ordinary: change {index}",
                    "trailers": {
                        "Affected": ["2.x systems"],
                        "Action": ["migrate configuration"],
                        "Migration": ["docs/migration.md"],
                    } if tagged else {},
                    "destinations": destinations,
                    "requirements": requirements,
                },
            })
        return {
            "schema": 1,
            "event": "push",
            "event_id": "push:zeppe-lin/example:refs/heads/master:a:b",
            "repository": "zeppe-lin/example",
            "repository_url": "https://github.com/zeppe-lin/example",
            "ref": "refs/heads/master",
            "forced": False,
            "compare_url": "https://github.com/zeppe-lin/example/compare/a...b",
            "commits": commits,
        }

    def test_renderers_are_channel_specific(self):
        dev, user, irc, requirements = render_push(self.manifest())
        self.assertEqual(len(dev), 3)
        self.assertEqual(len(user), 1)
        self.assertIn("Author: Maintainer", dev[0]["body"])
        self.assertIn("1 file changed", dev[0]["body"])
        self.assertIn("Affected: 2.x systems", user[0]["body"])
        self.assertIn("Action: migrate configuration", user[0]["body"])
        self.assertTrue(user[0]["subject"].startswith("[news][breaking][example]"))
        self.assertTrue(irc.startswith("[news][breaking] example:master:"))
        self.assertIn("+1 more", irc)
        self.assertEqual(requirements[0]["requirements"], ["system-news", "release-note-review"])

    def test_irc_summary_is_utf8_bounded(self):
        manifest = self.manifest()
        manifest["commits"][0]["classification"]["summary"] = "Ж" * 500
        _, _, irc, _ = render_push(manifest)
        self.assertLessEqual(len(irc.rstrip("\n").encode("utf-8")), 360)
        irc.encode("utf-8")

    def test_no_commit_push_has_no_irc_message(self):
        manifest = self.manifest()
        manifest["commits"] = []
        dev, user, irc, requirements = render_push(manifest)
        self.assertEqual(dev, [])
        self.assertEqual(user, [])
        self.assertIsNone(irc)
        self.assertEqual(requirements, [])


if __name__ == "__main__":
    unittest.main()
