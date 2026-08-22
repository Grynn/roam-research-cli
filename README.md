# rr — focused Roam search from the terminal

`rr` is a small, read-only command-line tool for searching a live
[Roam Research](https://roamresearch.com/) graph through the desktop app's
local API.

It is deliberately narrower than Roam's
[official CLI](https://github.com/Roam-Research/roam-tools): `rr` is optimized
for one job—quick search—with shorthand invocation, page-first recency sorting,
Roam deep links, plain terminal output, and stable JSON for scripts.

## Requirements

- macOS and the Roam Research desktop app
- Python 3.11 or newer
- a read-only local API token

The local API is available only while the desktop app is running. If it is
closed, `rr` asks macOS to launch it and exits with a retryable error.

## Install

With [uv](https://docs.astral.sh/uv/):

```bash
uv tool install git+https://github.com/Grynn/roam-research-cli.git
```

Upgrade later with:

```bash
uv tool upgrade roam-research-cli
```

## Configure

`rr` shares `~/.roam-tools.json` with Roam's official tools. The easiest
setup is to use the official connection flow:

```bash
npx @roam-research/roam-cli connect
```

Choose read-only access when prompted. Alternatively, create a token in
Roam Desktop → Settings → Graph → Local API Tokens and use the documented
`~/.roam-tools.json` format.

For ephemeral use, `RR_GRAPH` and `RR_TOKEN` override the config file.
`RR_GRAPH` may be either a configured graph name or nickname.

## Usage

```bash
rr knowledge graph
rr search "knowledge graph" --limit 10
rr search "project ideas" --pages-only
rr search "project ideas" --json
rr status
rr open block-or-page-uid
```

Writing a query without a subcommand is shorthand for `rr search`.

Search results are grouped with pages first, then blocks. Within each group,
recently edited or opened results come first. Block results include their page
and ancestor breadcrumb.

### JSON output

`--json` emits an envelope suitable for launchers and shell automation:

```json
{
  "graph": "example-graph",
  "query": "project ideas",
  "results": [
    {
      "uid": "abc123xyz",
      "text": "Project Ideas",
      "is_page": true,
      "page_title": "Project Ideas",
      "breadcrumb": "",
      "recency": 1770000000000,
      "url": "roam://#/app/example-graph/page/abc123xyz",
      "reference": "[[Project Ideas]]"
    }
  ]
}
```

## Privacy and scope

- Requests go to the Roam desktop API on `127.0.0.1`.
- Tokens and graph contents are never written by `rr`.
- Search and Datalog calls are read-only.
- The local API and this project are alpha software and may need updates when
  Roam changes its internal API contract.

## Development

```bash
uv sync --locked
uv run python -m unittest discover -s tests
uv run rr --help
```
