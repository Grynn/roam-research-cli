import unittest
from unittest.mock import patch

from roam_research_cli import live


class LiveSearchTests(unittest.TestCase):
    def test_clean_removes_roam_markup(self):
        self.assertEqual(
            live._clean("# Example <roam uid=\"abc\"/>\nignored"),
            "Example",
        )

    def test_to_hit_builds_breadcrumb(self):
        hit = live._to_hit(
            {
                "uid": "block123",
                "markdown": "- Matching block <roam uid=\"block123\"/>",
                "path": [
                    "# Parent Page <roam uid=\"page123\"/>",
                    "- Section <roam uid=\"section1\"/>",
                ],
            }
        )
        self.assertFalse(hit.is_page)
        self.assertEqual(hit.text, "Matching block")
        self.assertEqual(hit.page_title, "Parent Page")
        self.assertEqual(hit.breadcrumb, "Section")

    def test_pages_sort_before_blocks_then_by_recency(self):
        search_result = {
            "results": [
                {"uid": "block", "markdown": "- Block", "path": ["# Page"]},
                {"uid": "old-page", "markdown": "# Old", "type": "page"},
                {"uid": "new-page", "markdown": "# New", "type": "page"},
            ]
        }
        recency = [
            ["block", 500, 0],
            ["old-page", 100, 0],
            ["new-page", 300, 0],
        ]
        with patch.object(live, "call", side_effect=[search_result, recency]):
            hits = live.live_search("example", "query")
        self.assertEqual(
            [hit.uid for hit in hits],
            ["new-page", "old-page", "block"],
        )

    def test_recency_failure_keeps_search_results(self):
        search_result = {
            "results": [{"uid": "page", "markdown": "# Page", "type": "page"}]
        }
        with patch.object(
            live,
            "call",
            side_effect=[search_result, live.LiveUnavailable("no recency")],
        ):
            hits = live.live_search("example", "query")
        self.assertEqual([hit.uid for hit in hits], ["page"])


if __name__ == "__main__":
    unittest.main()
