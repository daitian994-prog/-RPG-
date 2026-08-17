import unittest

from backend.services.project_status_service import get_project_status, parse_changelog


class ProjectStatusTests(unittest.TestCase):
    def test_changelog_parser_returns_release_changes(self):
        releases = parse_changelog("# 日志\n\n## 1.2.3 — 2026-01-02\n\n- 第一项\n- 第二项\n")
        self.assertEqual(releases, [{"version": "1.2.3", "date": "2026-01-02", "changes": ["第一项", "第二项"]}])

    def test_project_status_uses_repository_version_and_exports_handoff(self):
        status = get_project_status()
        self.assertEqual(status["changelog"][0]["version"], status["version"])
        self.assertIn("常规事件不再从固定 20 个事件中抽取", status["integration_markdown"])
        self.assertIn("GET /api/admin/project-status", status["integration_markdown"])


if __name__ == "__main__":
    unittest.main()
