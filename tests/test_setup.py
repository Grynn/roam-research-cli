import argparse
import io
import json
import stat
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from roam_research_cli import setup
from roam_research_cli.live import LiveUnavailable


def arguments(**overrides) -> argparse.Namespace:
    defaults = {"graph": None, "nickname": None, "token": None, "force": False}
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class ConfigWritingTests(unittest.TestCase):
    def test_slugify_makes_a_nickname(self):
        self.assertEqual(setup.slugify("My Team Graph"), "my-team-graph")
        self.assertEqual(setup.slugify("!!!"), "graph")

    def test_save_graph_keeps_other_graphs_and_unknown_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / ".roam-tools.json"
            config.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "somethingElse": {"kept": True},
                        "graphs": [
                            {"name": "other", "nickname": "other", "token": "keep-me"}
                        ],
                    }
                )
            )
            with patch.object(setup, "TOKENS_FILE", config):
                setup.save_graph("new-graph", "new-token", "new")
            written = json.loads(config.read_text())

        self.assertEqual(written["somethingElse"], {"kept": True})
        self.assertEqual(
            [graph["name"] for graph in written["graphs"]], ["other", "new-graph"]
        )
        self.assertEqual(written["graphs"][0]["token"], "keep-me")
        self.assertEqual(
            written["graphs"][1],
            {
                "name": "new-graph",
                "type": "hosted",
                "token": "new-token",
                "nickname": "new",
                "accessLevel": "read-only",
            },
        )

    def test_save_graph_replaces_the_token_of_a_known_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / ".roam-tools.json"
            config.write_text(
                json.dumps(
                    {
                        "graphs": [
                            {"name": "graph", "nickname": "old", "token": "stale"}
                        ]
                    }
                )
            )
            with patch.object(setup, "TOKENS_FILE", config):
                setup.save_graph("graph", "fresh", "new")
            written = json.loads(config.read_text())
            backup = config.with_name(config.name + ".bak")
            self.assertTrue(backup.exists())
            self.assertIn("stale", backup.read_text())

        self.assertEqual(len(written["graphs"]), 1)
        self.assertEqual(written["graphs"][0]["token"], "fresh")
        self.assertEqual(written["graphs"][0]["nickname"], "new")

    def test_saved_config_is_owner_only(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / ".roam-tools.json"
            with patch.object(setup, "TOKENS_FILE", config):
                setup.save_graph("graph", "token", "graph")
            mode = stat.S_IMODE(config.stat().st_mode)
        self.assertEqual(mode, 0o600)


class SetupCommandTests(unittest.TestCase):
    def run_setup(self, config: Path, *, verified: bool, running: bool = True, **args):
        failure = LiveUnavailable("local API HTTP 401: bad token")
        output = io.StringIO()
        with (
            patch.object(setup, "TOKENS_FILE", config),
            patch.object(setup.sys.stdin, "isatty", return_value=False),
            patch.object(setup, "desktop_running", return_value=running),
            patch.object(setup, "_confirm", side_effect=AssertionError("prompted")),
            patch.object(setup, "_ask", side_effect=AssertionError("prompted")),
            patch.object(setup, "_ask_secret", side_effect=AssertionError("prompted")),
            patch.object(
                setup,
                "check_token",
                side_effect=None if verified else failure,
            ) as check,
            redirect_stdout(output),
        ):
            setup.cmd_setup(arguments(**args))
        return check, output.getvalue()

    def test_flags_verify_and_save_without_prompting(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / ".roam-tools.json"
            check, output = self.run_setup(
                config, verified=True, graph="my-graph", token="secret"
            )
            written = json.loads(config.read_text())

        check.assert_called_once_with("my-graph", "secret")
        self.assertEqual(written["graphs"][0]["name"], "my-graph")
        self.assertEqual(written["graphs"][0]["nickname"], "my-graph")
        self.assertNotIn("secret", output)

    def test_failed_check_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / ".roam-tools.json"
            with self.assertRaises(SystemExit):
                self.run_setup(
                    config, verified=False, graph="my-graph", token="secret"
                )
            self.assertFalse(config.exists())

    def test_force_saves_despite_a_failed_check(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / ".roam-tools.json"
            self.run_setup(
                config,
                verified=False,
                graph="my-graph",
                token="secret",
                force=True,
            )
            written = json.loads(config.read_text())
        self.assertEqual(written["graphs"][0]["token"], "secret")

    def test_closed_desktop_does_not_prompt_without_a_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / ".roam-tools.json"
            _, output = self.run_setup(
                config,
                verified=True,
                running=False,
                graph="my-graph",
                token="secret",
            )
            self.assertTrue(config.exists())
        self.assertIn("does not look like it is running", output)

    def test_missing_flags_without_a_terminal_points_at_the_docs(self):
        with (
            patch.object(setup.sys.stdin, "isatty", return_value=False),
            redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit) as raised,
        ):
            setup.cmd_setup(arguments())
        self.assertIn(setup.DOCS_URL, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
