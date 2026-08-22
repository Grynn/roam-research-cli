"""Client for Roam Desktop's local HTTP API and live search."""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

EXPECTED_API_VERSION = "1.1.5"
TOKENS_FILE = Path.home() / ".roam-tools.json"
PORT_FILE = Path.home() / ".roam-local-api.json"
DEFAULT_TIMEOUT = 3.0


class LiveUnavailable(Exception):
    """The local API cannot serve a request."""


@dataclass
class Hit:
    uid: str
    text: str
    is_page: bool
    page_title: str
    breadcrumb: str
    recency: int


def _port() -> int:
    try:
        return int(json.loads(PORT_FILE.read_text())["port"])
    except (OSError, ValueError, KeyError, TypeError):
        return 3333


def load_token(graph: str) -> str | None:
    if token := os.environ.get("RR_TOKEN"):
        return token
    try:
        config = json.loads(TOKENS_FILE.read_text())
    except (OSError, ValueError):
        return None
    for entry in config.get("graphs", []):
        if entry.get("name") == graph and entry.get("token"):
            return entry["token"]
    return None


def call(graph: str, action: str, args: list, timeout: float = DEFAULT_TIMEOUT):
    token = load_token(graph)
    if token is None:
        raise LiveUnavailable(
            "no local API token; create a read-only token in Roam Settings → "
            f"Graph → Local API Tokens and configure it in {TOKENS_FILE}"
        )

    request = urllib.request.Request(
        f"http://127.0.0.1:{_port()}/api/{quote(graph, safe='')}",
        data=json.dumps(
            {
                "action": action,
                "args": args,
                "expectedApiVersion": EXPECTED_API_VERSION,
            }
        ).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read()).get("error")
        except Exception:
            detail = None
        raise LiveUnavailable(
            f"local API HTTP {error.code}: {detail or error.reason}"
        ) from error
    except (
        urllib.error.URLError,
        TimeoutError,
        ConnectionError,
        json.JSONDecodeError,
    ) as error:
        subprocess.Popen(
            ["open", "-g", "roam://"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        raise LiveUnavailable(
            "Roam Desktop is not running (launching it now; retry shortly)"
        ) from error

    if not data.get("success", False):
        raise LiveUnavailable(f"local API error: {data.get('error')}")
    return data.get("result")


_ROAM_TAG = re.compile(r"\s*<roam[^>]*/>")


def _clean(markdown: str) -> str:
    line = _ROAM_TAG.sub("", markdown).strip().split("\n", 1)[0]
    return re.sub(r"^(#+|-)\s+", "", line).strip()


def _to_hit(result: dict) -> Hit:
    uid = result.get("uid") or ""
    is_page = result.get("type") == "page"
    text = _clean(result.get("markdown") or "")
    segments = [_clean(part) for part in result.get("path") or []]
    return Hit(
        uid=uid,
        text=text,
        is_page=is_page,
        page_title=text if is_page else (segments[0] if segments else ""),
        breadcrumb="" if is_page
        else " › ".join(segment for segment in segments[1:] if segment),
        recency=0,
    )


RECENCY_Q = (
    "[:find ?uid ?t ?lu :in $ [?uid ...] :where [?e :block/uid ?uid]"
    " [(get-else $ ?e :edit/time 0) ?t]"
    " [(get-else $ ?e :last-used/time 0) ?lu]]"
)


def _add_recency(graph: str, hits: list[Hit]) -> None:
    if not hits:
        return
    try:
        rows = call(graph, "q", [RECENCY_Q, [hit.uid for hit in hits]]) or []
    except LiveUnavailable:
        return
    times = {
        uid: max(int(edited or 0), int(last_used or 0))
        for uid, edited, last_used in rows
    }
    for hit in hits:
        hit.recency = times.get(hit.uid, 0)


def live_search(
    graph: str,
    query: str,
    limit: int = 20,
    scope: str = "all",
) -> list[Hit]:
    result = call(
        graph,
        "data.ai.search",
        [
            {
                "query": query,
                "scope": scope,
                "offset": 0,
                "limit": limit,
                "includePath": True,
            }
        ],
    )
    raw_results = (result or {}).get("results", [])
    hits = [
        hit
        for hit in (_to_hit(raw) for raw in raw_results)
        if hit.uid and hit.text
    ]
    _add_recency(graph, hits)
    hits.sort(key=lambda hit: (not hit.is_page, -hit.recency))
    return hits
