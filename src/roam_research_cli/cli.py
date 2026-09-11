"""rr — fast, read-only Roam search from the terminal.

Default command is search: `rr some query` is equivalent to
`rr search some query`.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from urllib.parse import quote

from . import __version__
from .live import TOKENS_FILE, Hit, LiveUnavailable, live_search
from .setup import DOCS_URL, cmd_setup

SUBCOMMANDS = {"search", "status", "open", "setup"}


def deep_link(graph: str, uid: str) -> str:
    return f"roam://#/app/{quote(graph, safe='')}/page/{quote(uid, safe='')}"


def _configured_graphs() -> list[dict]:
    try:
        value = json.loads(TOKENS_FILE.read_text())
    except (OSError, ValueError):
        return []
    graphs = value.get("graphs", [])
    return [graph for graph in graphs if isinstance(graph, dict) and graph.get("name")]


def resolve_graph_name(value: str) -> str:
    for graph in _configured_graphs():
        if value in {graph.get("name"), graph.get("nickname")}:
            return graph["name"]
    return value


def default_graph_name() -> str:
    if configured := os.environ.get("RR_GRAPH"):
        return resolve_graph_name(configured)
    graphs = _configured_graphs()
    if len(graphs) == 1:
        return graphs[0]["name"]
    if not graphs:
        raise SystemExit(
            f"rr: no graphs configured in {TOKENS_FILE}\n"
            "    run `rr setup` to connect one, or set RR_GRAPH and RR_TOKEN\n"
            f"    setup guide: {DOCS_URL}"
        )
    labels = [graph.get("nickname") or graph["name"] for graph in graphs]
    raise SystemExit(
        "rr: multiple graphs configured — pass --graph or set RR_GRAPH "
        f"(found: {', '.join(labels)})"
    )


def selected_graph(argument: str | None) -> str:
    return resolve_graph_name(argument) if argument else default_graph_name()


def _date(milliseconds: int) -> str:
    if not milliseconds:
        return ""
    return datetime.fromtimestamp(milliseconds / 1000).strftime("%b %-d, %Y")


def _result(graph: str, hit: Hit) -> dict:
    return {
        "uid": hit.uid,
        "text": hit.text,
        "is_page": hit.is_page,
        "page_title": hit.page_title,
        "breadcrumb": hit.breadcrumb,
        "recency": hit.recency,
        "url": deep_link(graph, hit.uid),
        "reference": f"[[{hit.text}]]" if hit.is_page else f"(({hit.uid}))",
    }


def cmd_search(args: argparse.Namespace) -> None:
    query = " ".join(args.query).strip()
    graph = selected_graph(args.graph)
    if not query:
        if args.json:
            print(json.dumps({"graph": graph, "query": "", "results": []}))
        return

    scope = "pages" if args.pages_only else "all"
    try:
        hits = live_search(graph, query, limit=args.limit, scope=scope)
    except LiveUnavailable as error:
        raise SystemExit(f"rr: {error}") from error

    if args.json:
        payload = {
            "graph": graph,
            "query": query,
            "results": [_result(graph, hit) for hit in hits],
        }
        print(json.dumps(payload, ensure_ascii=False))
        return

    for hit in hits:
        when = _date(hit.recency)
        if hit.is_page:
            print(f"[[{hit.text}]]  {when}  ({hit.uid})")
            continue
        location = hit.page_title or "?"
        if hit.breadcrumb:
            location += f" › {hit.breadcrumb}"
        print(f"{hit.text}\n    — {location}  {when}  (({hit.uid}))")


def cmd_status(args: argparse.Namespace) -> None:
    graph = selected_graph(args.graph)
    print(f"graph:     {graph}")
    try:
        started = time.monotonic()
        live_search(graph, "a", limit=1)
    except LiveUnavailable as error:
        raise SystemExit(f"live API:  unavailable — {error}") from error
    print(f"live API:  ok ({(time.monotonic() - started) * 1000:.0f} ms)")


def cmd_open(args: argparse.Namespace) -> None:
    graph = selected_graph(args.graph)
    subprocess.run(["open", deep_link(graph, args.uid)], check=True)


def positive_integer(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(prog="rr", description=__doc__)
    argument_parser.add_argument("--version", action="version", version=__version__)
    subcommands = argument_parser.add_subparsers(dest="cmd", required=True)

    search = subcommands.add_parser("search", help="search the graph (default command)")
    search.add_argument("query", nargs="*")
    search.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    search.add_argument("--limit", type=positive_integer, default=20)
    search.add_argument("--pages-only", action="store_true")
    search.add_argument("--graph", help="configured graph name or nickname")
    search.set_defaults(fn=cmd_search)

    status = subcommands.add_parser("status", help="check local API health")
    status.add_argument("--graph", help="configured graph name or nickname")
    status.set_defaults(fn=cmd_status)

    open_command = subcommands.add_parser("open", help="open a UID in Roam Desktop")
    open_command.add_argument("uid")
    open_command.add_argument("--graph", help="configured graph name or nickname")
    open_command.set_defaults(fn=cmd_open)

    setup = subcommands.add_parser(
        "setup",
        help="connect a graph (interactive walkthrough)",
        description=(
            "Walk through connecting a Roam graph: check Roam Desktop, create a "
            f"read-only local API token, verify it, and save it to {TOKENS_FILE}. "
            f"See {DOCS_URL}."
        ),
    )
    setup.add_argument("--graph", help="graph name, as it appears in the Roam URL")
    setup.add_argument("--nickname", help="short name to refer to the graph by")
    setup.add_argument("--token", help="local API token (skips the prompts)")
    setup.add_argument(
        "--force",
        action="store_true",
        help="save the token even if the local API check fails",
    )
    setup.set_defaults(fn=cmd_setup)
    return argument_parser


def main() -> None:
    arguments = sys.argv[1:]
    if arguments and arguments[0] not in SUBCOMMANDS and arguments[0] not in {
        "-h",
        "--help",
        "--version",
    }:
        arguments = ["search", *arguments]
    parsed = parser().parse_args(arguments)
    parsed.fn(parsed)


if __name__ == "__main__":
    main()
