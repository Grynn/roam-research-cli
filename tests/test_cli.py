import argparse
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from roam_research_cli import cli
from roam_research_cli.live import Hit


class CLITests(unittest.TestCase):
    def test_deep_link_escapes_components(self):
        self.assertEqual(
            cli.deep_link("team graph", "uid/value"),
            "roam://#/app/team%20graph/page/uid%2Fvalue",
        )

    def test_graph_nickname_resolves_to_name(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "graphs": [
                            {
                                "name": "actual-graph",
                                "nickname": "notes",
                                "token": "test-token",
                            }
                        ]
                    }
                )
            )
            with patch.object(cli, "TOKENS_FILE", config):
                self.assertEqual(cli.resolve_graph_name("notes"), "actual-graph")

    def test_environment_selects_graph(self):
        with patch.dict(os.environ, {"RR_GRAPH": "example"}, clear=False):
            self.assertEqual(cli.default_graph_name(), "example")

    def test_json_search_output(self):
        hit = Hit(
            uid="abc123",
            text="Project Ideas",
            is_page=True,
            page_title="Project Ideas",
            breadcrumb="",
            recency=123456,
        )
        arguments = argparse.Namespace(
            query=["project", "ideas"],
            graph="example",
            limit=10,
            pages_only=False,
            json=True,
        )
        output = io.StringIO()
        with patch.object(cli, "live_search", return_value=[hit]), redirect_stdout(output):
            cli.cmd_search(arguments)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["graph"], "example")
        self.assertEqual(payload["results"][0]["reference"], "[[Project Ideas]]")
        self.assertEqual(
            payload["results"][0]["url"],
            "roam://#/app/example/page/abc123",
        )

    def test_missing_config_points_at_rr_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "absent.json"
            environment = {
                key: value
                for key, value in os.environ.items()
                if key != "RR_GRAPH"
            }
            with (
                patch.object(cli, "TOKENS_FILE", missing),
                patch.dict(os.environ, environment, clear=True),
                self.assertRaises(SystemExit) as raised,
            ):
                cli.default_graph_name()
        message = str(raised.exception)
        self.assertIn("rr setup", message)
        self.assertIn(cli.DOCS_URL, message)

    def test_setup_is_not_treated_as_a_search_query(self):
        with patch.object(cli, "cmd_setup") as command:
            with patch.object(sys, "argv", ["rr", "setup", "--graph", "example"]):
                cli.main()
        self.assertEqual(command.call_args.args[0].graph, "example")

    def test_limit_must_be_positive(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            cli.positive_integer("0")


if __name__ == "__main__":
    unittest.main()
