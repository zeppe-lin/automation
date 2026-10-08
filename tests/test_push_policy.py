#!/usr/bin/env python3

import unittest

from automation.policy import PolicyError, classify_commit, classify_subject, route


class PushPolicyTest(unittest.TestCase):
    def commit(self, title, trailers=None):
        return {
            "sha": "a" * 40,
            "title": title,
            "trailers": trailers or {},
        }

    def test_ordinary_commit_routes_to_development_and_irc(self):
        result = classify_commit(self.commit("pkg: ordinary cleanup"))
        self.assertEqual(result["classification"]["tags"], [])
        self.assertEqual(
            result["classification"]["destinations"], ["mail-dev", "irc"]
        )

    def test_tagged_commit_routes_to_user_audience(self):
        result = classify_commit(
            self.commit(
                "[news][security] linux: security update",
                {
                    "Affected": ["2.x systems"],
                    "Action": ["update and reboot"],
                    "News": [".news/linux-update"],
                    "Reference": ["CVE-2026-1", "CVE-2026-2"],
                },
            )
        )
        classification = result["classification"]
        self.assertEqual(classification["tags"], ["news", "security"])
        self.assertEqual(
            classification["destinations"], ["mail-dev", "mail-user", "irc"]
        )
        self.assertEqual(classification["requirements"], ["system-news"])
        self.assertEqual(
            classification["trailers"]["Reference"], ["CVE-2026-1", "CVE-2026-2"]
        )

    def test_breaking_requires_news(self):
        with self.assertRaisesRegex(PolicyError, "must be combined with \\[news\\]"):
            classify_subject("[breaking] interface: remove compatibility")

    def test_tag_order_and_spelling_are_enforced(self):
        with self.assertRaisesRegex(PolicyError, "canonical"):
            classify_subject("[security][news] linux: update")
        with self.assertRaisesRegex(PolicyError, "lowercase"):
            classify_subject("[News] linux: update")

    def test_obsolete_notify_is_rejected(self):
        with self.assertRaisesRegex(PolicyError, "obsolete"):
            classify_subject("[notify] package: removed")

    def test_unknown_bracket_prefix_is_not_invented_as_project_policy(self):
        tags, summary = classify_subject("[RFC] proposal: discuss")
        self.assertEqual(tags, [])
        self.assertEqual(summary, "[RFC] proposal: discuss")

    def test_breaking_route_requires_release_note_review(self):
        destinations, requirements = route(["news", "breaking"])
        self.assertIn("mail-user", destinations)
        self.assertEqual(requirements, ["system-news", "release-note-review"])


if __name__ == "__main__":
    unittest.main()
