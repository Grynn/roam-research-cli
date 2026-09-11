"""`rr setup` — walk through connecting a Roam graph to `rr`."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from getpass import getpass
from pathlib import Path

from .live import (
    TOKENS_FILE,
    LiveUnavailable,
    api_port,
    check_token,
    desktop_running,
    launch_desktop,
)

DOCS_URL = "https://github.com/Grynn/roam-research-cli/blob/main/docs/SETUP.md"
CONNECT_COMMAND = [
    "npx",
    "@roam-research/roam-mcp",
    "connect",
    "--access-level",
    "read-only",
]

TOKEN_STEPS = """\
   In Roam Desktop:
     1. Open the graph you want to search.
     2. Settings → Graph → Local API Tokens → New Token.
     3. Choose read-only access and approve the token dialog.
     4. Copy the token (it looks like roam-graph-local-token-…).

   Your graph name is the one in the Roam URL:
     roamresearch.com/#/app/<graph-name>"""


def _say(text: str = "") -> None:
    print(text)


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"{prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        raise SystemExit("\nrr: setup cancelled") from None
    return answer or default


def _ask_secret(prompt: str) -> str:
    try:
        return getpass(f"{prompt}: ").strip()
    except (EOFError, KeyboardInterrupt):
        raise SystemExit("\nrr: setup cancelled") from None


def _confirm(prompt: str, default: bool = True) -> bool:
    hint = "[Y/n]" if default else "[y/N]"
    try:
        answer = input(f"{prompt} {hint} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        raise SystemExit("\nrr: setup cancelled") from None
    return default if not answer else answer.startswith("y")


def load_config() -> dict:
    try:
        value = json.loads(TOKENS_FILE.read_text())
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def configured_graphs(config: dict | None = None) -> list[dict]:
    graphs = (load_config() if config is None else config).get("graphs", [])
    if not isinstance(graphs, list):
        return []
    return [g for g in graphs if isinstance(g, dict) and g.get("name")]


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "graph"


def _write_config(config: dict) -> None:
    """Replace the tokens file atomically, owner-readable only, keeping a backup."""
    TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if TOKENS_FILE.exists():
        shutil.copy2(TOKENS_FILE, TOKENS_FILE.with_name(TOKENS_FILE.name + ".bak"))
    handle = tempfile.NamedTemporaryFile(
        "w",
        dir=TOKENS_FILE.parent,
        prefix=TOKENS_FILE.name + ".",
        suffix=".tmp",
        delete=False,
    )
    try:
        with handle:
            handle.write(json.dumps(config, indent=2) + "\n")
        os.chmod(handle.name, 0o600)
        os.replace(handle.name, TOKENS_FILE)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise


def save_graph(
    name: str,
    token: str,
    nickname: str,
    access_level: str = "read-only",
) -> Path:
    """Add or update one graph in ~/.roam-tools.json, leaving other entries alone."""
    config = load_config()
    graphs = configured_graphs(config)
    entry = next((g for g in graphs if g.get("name") == name), None)
    if entry is None:
        entry = {"name": name}
        graphs.append(entry)
    entry.setdefault("type", "hosted")
    entry["token"] = token
    entry["nickname"] = nickname
    entry["accessLevel"] = access_level

    updated = {"version": config.get("version", 1)}
    updated.update(
        {
            key: value
            for key, value in config.items()
            if key not in {"version", "graphs"}
        }
    )
    updated["graphs"] = graphs
    _write_config(updated)
    return TOKENS_FILE


def _step_desktop(interactive: bool) -> None:
    _say("1. Roam Desktop")
    if desktop_running():
        _say(f"   ok — the local API is listening on 127.0.0.1:{api_port()}")
        return
    _say("   Roam Desktop does not look like it is running.")
    _say("   The local API only exists while the desktop app is open.")
    if interactive and _confirm("   Launch Roam Desktop now?"):
        if not launch_desktop():
            _say("   could not launch it from here — please open Roam yourself.")
        _ask("   press Enter once Roam is open")
        if desktop_running():
            _say(f"   ok — the local API is listening on 127.0.0.1:{api_port()}")
            return
    _say("   carrying on — rr will check the token against the API in step 4.")


def _run_official_connect() -> bool:
    if shutil.which("npx") is None:
        _say("   npx is not on PATH; install Node.js or paste a token instead.")
        return False
    _say(f"   running: {' '.join(CONNECT_COMMAND)}")
    _say()
    try:
        completed = subprocess.run(CONNECT_COMMAND, check=False)
    except OSError as error:
        _say(f"   could not run npx: {error}")
        return False
    if completed.returncode != 0:
        _say(f"   the connect flow exited with status {completed.returncode}.")
        return False
    return True


def _verify(graph: str, token: str) -> bool:
    _say(f"4. Checking the token against graph '{graph}'…")
    try:
        check_token(graph, token)
    except LiveUnavailable as error:
        _say(f"   failed — {error}")
        return False
    _say("   ok — the local API answered.")
    return True


def _next_steps(nickname: str) -> None:
    _say()
    _say("Next:")
    _say("  rr status                 # confirm the local API is reachable")
    _say("  rr some query             # search (shorthand for `rr search`)")
    if len(configured_graphs()) > 1:
        _say(f"  rr some query --graph {nickname}   # pick a graph")
    _say()
    _say(f"Setup guide: {DOCS_URL}")


def cmd_setup(args: argparse.Namespace) -> None:
    interactive = sys.stdin.isatty()
    if not interactive and not (args.graph and args.token):
        raise SystemExit(
            "rr: setup needs a terminal; pass --graph and --token to configure "
            f"without prompts, or follow {DOCS_URL}"
        )

    _say("rr setup — connect a Roam graph")
    _say()
    existing = configured_graphs()
    if existing:
        labels = ", ".join(g.get("nickname") or g["name"] for g in existing)
        _say(f"   already configured in {TOKENS_FILE}: {labels}")
        _say("   setup adds another graph, or replaces the token of one you repeat.")
        _say()

    _step_desktop(interactive)
    _say()

    graph, token = args.graph, args.token
    nickname = args.nickname
    if not token:
        _say("2. Get a read-only token")
        if _confirm(
            "   Use the official Roam connect flow (npx @roam-research/roam-mcp)?",
            default=False,
        ):
            if _run_official_connect():
                graphs = configured_graphs()
                if graphs:
                    names = ", ".join(g.get("nickname") or g["name"] for g in graphs)
                    _say()
                    _say(f"   ok — {TOKENS_FILE} now lists: {names}")
                    _next_steps(graphs[0].get("nickname") or graphs[0]["name"])
                    return
                _say("   the connect flow did not write a graph; falling back.")
            _say()
        _say(TOKEN_STEPS)
        _say()

    if interactive and not (graph and token and nickname):
        _say("3. Enter your graph and token")
    while not graph:
        graph = _ask("   graph name")
    if nickname:
        nickname = slugify(nickname)
    elif interactive:
        nickname = slugify(_ask("   nickname", default=slugify(graph)))
    else:
        nickname = slugify(graph)
    while not token:
        token = _ask_secret("   token (input hidden)")
    if interactive:
        _say()

    if not _verify(graph, token) and not args.force:
        if not interactive:
            raise SystemExit(
                "rr: token check failed; nothing was written "
                "(pass --force to save it anyway)"
            )
        _say("   this is expected if Roam is closed or the token is for another graph.")
        if not _confirm("   Save it anyway?", default=False):
            raise SystemExit("rr: setup cancelled; nothing was written")

    path = save_graph(graph, token, nickname)
    _say()
    _say(f"5. Saved '{graph}' as '{nickname}' in {path} (permissions 0600).")
    _next_steps(nickname)
