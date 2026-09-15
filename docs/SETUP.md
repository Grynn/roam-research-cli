# Setting up `rr`

`rr` talks to the local HTTP API that Roam Desktop exposes on `127.0.0.1`
while the app is open. To use it you need two things:

- **a graph name** — the graph as Roam names it in the URL
- **a local API token** — a read-only token you create in Roam Desktop

Both live in `~/.roam-tools.json`, the config file `rr` shares with Roam's
[official tools](https://github.com/Roam-Research/roam-tools).

## The short version

```bash
rr setup
```

That walks you through everything below: it checks whether Roam Desktop is
running, tells you where to create the token, asks for the graph name and
token, verifies them against the live API, and writes
`~/.roam-tools.json` with `0600` permissions.

Then check it:

```bash
rr status
```

## Where the graph name comes from

The graph name is the segment in the Roam URL:

```
roamresearch.com/#/app/my-graph-name
                       ^^^^^^^^^^^^^
```

That exact string is what the local API expects — not the display name in the
graph switcher. In `rr` you can also refer to a graph by the *nickname* you
choose during setup (`rr query --graph work`).

## Where the token comes from

In Roam **Desktop** (the local API does not exist in the web app):

1. Open the graph you want to search.
2. Go to **Settings → Graph → Local API Tokens → New Token**.
3. Choose **read-only** access. `rr` never writes to your graph, so read-only
   is all it needs.
4. Approve the token dialog Roam shows.
5. Copy the token. It looks like `roam-graph-local-token-…`.

Paste it into `rr setup` when it asks — the prompt hides the input.

## Other ways to configure

### Roam's official connect flow

`rr setup` can hand off to it, or you can run it yourself:

```bash
npx @roam-research/roam-mcp connect --access-level read-only
```

It writes the same `~/.roam-tools.json` that `rr` reads, so `rr` works
immediately afterwards. (Installing `npm i -g @roam-research/roam-cli` gives
you the same thing as `roam connect`.)

### By hand

```json
{
  "version": 1,
  "graphs": [
    {
      "name": "my-graph-name",
      "type": "hosted",
      "token": "roam-graph-local-token-...",
      "nickname": "my-graph",
      "accessLevel": "read-only"
    }
  ]
}
```

| Field | Required | Description |
| --- | --- | --- |
| `name` | yes | graph name as it appears in the Roam URL |
| `token` | yes | local API token from Roam Settings |
| `nickname` | yes | short slug you can pass to `--graph` |
| `type` | no | `"hosted"` (default) or `"offline"` |
| `accessLevel` | no | what the token was granted; Roam enforces the real permissions |

Save the file as `chmod 600 ~/.roam-tools.json` — it holds a live token.

### Environment variables

`RR_GRAPH` and `RR_TOKEN` override the config file, which is handy for
one-off shells, scripts and CI:

```bash
RR_GRAPH=my-graph-name RR_TOKEN=roam-graph-local-token-... rr status
```

`RR_GRAPH` accepts a configured name *or* nickname.

### Non-interactive setup

```bash
rr setup --graph my-graph-name --nickname work --token roam-graph-local-token-...
```

The token is still verified against the live API before it is saved; add
`--force` to save it regardless. A token passed as an argument lands in your
shell history and in `ps` output — prefer the interactive prompt, which hides
the input, for anything long-lived.

## Several graphs

Run `rr setup` once per graph. With more than one configured, `rr` asks you to
pick:

```bash
rr some query --graph work
export RR_GRAPH=work        # or set a default for the shell
```

## Troubleshooting

| Message | What it means |
| --- | --- |
| `no graphs configured in ~/.roam-tools.json` | nothing is set up yet — run `rr setup` |
| `no local API token for graph 'x'` | the config has no token under that exact graph name; check the name against the Roam URL |
| `Roam Desktop is not running` | the local API is only up while the app is open; `rr` asks macOS to launch it, then retry |
| `local API HTTP 401` / `403` | the token was revoked, or belongs to a different graph — create a new one and re-run `rr setup` |
| `multiple graphs configured` | pass `--graph <name-or-nickname>` or set `RR_GRAPH` |
| `local API HTTP 404` | the graph name is wrong, or that graph is not open in Roam Desktop |

The port is read from `~/.roam-local-api.json` and defaults to `3333`.
Roam writes that file when the desktop app starts.

## What `rr` touches

- Reads `~/.roam-tools.json` and `~/.roam-local-api.json`.
- `rr setup` is the only command that writes: it rewrites
  `~/.roam-tools.json` (keeping a `.bak` copy of the previous file) with
  `0600` permissions, preserving any other graphs already configured.
- Everything else is read-only: search and Datalog queries against
  `127.0.0.1`, and `open roam://…` deep links.
