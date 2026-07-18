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

## `cxpp` Fallback

Install the `cxpp` plugin when plugins need a thin, host-side bootstrap layer:

1. `/cxpp:init` presents independently selectable setup components and asks
   before every write to global Codex configuration, hooks, or rules.
2. `/cxpp:update` rechecks those components and proposes additive refreshes;
   it never overwrites existing configuration or removes user entries.
3. `/cxpp:status` is read-only. It reports installed CxPP plugins, MCP pointer
   presence and health, optional bootstrap state, and pin/drift warnings.

When the marketplace or family plugins are missing, init and update offer
Minimal (`cxpp`), Recommended (the common development families), Full suite
(all published families), and Custom profiles. Status reports each published
family as installed or missing. Before an approved install, init/update show the
selected plugins, exact `.agents` and `plugins/<family>` sparse paths, previous
ref, requested signed tag or immutable commit SHA, and resolved SHA. Re-running
an unchanged profile is `already current`; other outcomes are `updated`,
`skipped by user`, or `needs host prerequisite`.

Plugin-suite consent is deliberately narrow. It authorizes only the previewed
marketplace and plugin actions. It does not authorize MCP pointer changes,
credential or provider setup, hooks, exec-policy rules, or external-service
lifecycle operations. Those remain separate components with individual consent
prompts.

The commands use `templates/config.toml.example` as the MCP-pointer source,
run non-secret checks such as `curl -sf http://127.0.0.1:8080/readyz` and
`codex mcp get playwright`, and report missing services without trying to
create them. They may install reviewed Codex-facing hooks or rules only after
the user approves the exact files and `codex execpolicy check` passes.

The fallback does not own external MCP server lifecycle.
