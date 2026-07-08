# Host-Managed Services

Codex Power Pack does not run MCP servers. It ships skills, templates,
and documentation that point Codex at services owned outside this repository.
Use `templates/config.toml.example` as the source pointer template for a fresh
Codex install.

## Codex Configuration

Merge these entries into `~/.codex/config.toml`, or run the matching Codex CLI
commands:

```toml
[mcp_servers.second-opinion]
url = "http://127.0.0.1:8080/mcp"

[mcp_servers.playwright]
command = "npx"
args = ["-y", "@playwright/mcp@latest"]
```

```bash
codex mcp add second-opinion --url http://127.0.0.1:8080/mcp
codex mcp add playwright -- npx -y @playwright/mcp@latest
```

Start a fresh Codex session after changing MCP configuration so the tool list is
rebuilt.

## Service Inventory

| Service | Owner | Codex pointer | Health check |
|---------|-------|---------------|--------------|
| `mcp-second-opinion` | Shared external `mcp-second-opinion` service, usually installed as a host service from that repo | `http://127.0.0.1:8080/mcp` | `curl -sf http://127.0.0.1:8080/readyz` |
| `@playwright/mcp` | Native Playwright MCP package resolved by Codex through `npx` | `npx -y @playwright/mcp@latest` | `codex mcp get playwright` |

For `mcp-second-opinion`, `/` is the liveness endpoint and `/readyz` confirms the
server has provider configuration loaded. The MCP tool-level health check is
`health_check` after Codex has loaded the server.

For browser automation, use the native `@playwright/mcp` registration above. This
repo does not ship a Playwright server wrapper or browser lease manager.

## Lifecycle Boundary

No server lifecycle management exists in this repo. Codex Power Pack must not:

- start, stop, restart, update, or deploy `mcp-second-opinion`
- vendor `mcp-second-opinion`, Playwright MCP, or browser binaries
- store API keys for the shared service in repo config
- replace host service health checks with repo-local Docker Compose targets

The host service owner manages credentials, process supervision, upgrades, and
logs. Codex Power Pack only records the client-side connection contract.

## Future `cxpp:init` Scope

Story C4 owns the thin `cxpp:init/update/status` fallback. When implemented, it
should:

1. Copy or print `templates/config.toml.example` for the user's Codex config.
2. Ask before writing any global `~/.codex/config.toml` entry.
3. Run non-secret health checks such as `curl -sf http://127.0.0.1:8080/readyz`
   and `codex mcp get playwright`.
4. Report missing host services without trying to create them.

That fallback may install Codex-facing pointers and hooks/rules. It still must
not own external MCP server lifecycle.
