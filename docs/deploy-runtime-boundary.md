# Deploy Runtime Boundary

This repository treats deploy execution as a repo-owned workflow, not a host-managed
helper script.

## Canonical Runtime Path

The supported MCP deploy path is:

1. Fresh checkout or pull of this repository
2. `make deploy PROFILE="core browser"` or `./scripts/deploy_mcp.sh`
3. `docker compose ... up -d --build --wait`
4. `make mcp-smoke PROFILE="core browser"`

Both local deploys and the Woodpecker `deploy-mcp` step now route through
`scripts/deploy_mcp.sh`.

## Provisioning-Only Host Artifacts

These artifacts may exist on deployment hosts, but they are provisioning-only and
must not contain runtime deploy logic:

- `woodpecker-bootstrap.service`
- `cloudflared.service`
- `woodpecker/bootstrap-secrets.py`
- `~/.env`
- `woodpecker/docker.env`
- `woodpecker/agent.env`

Allowed responsibilities:

- fetching secrets
- writing env files
- starting tunnels
- bootstrapping the Woodpecker server itself

Disallowed responsibilities:

- running `docker compose up`
- invoking `make deploy`
- embedding MCP deploy steps in `/usr/local/bin` helper scripts

## Drift Detection

Run these commands to validate the deploy contract:

```bash
make deploy-check PROFILE="core browser"
make deploy-doctor
```

`make deploy-check` exercises the same repo-owned entrypoint used in production.
`make deploy-doctor` inventories host-facing unit files and wrapper scripts and fails
when it detects deploy runtime logic outside the repo checkout.

## Migration Guidance

If a host currently uses a helper under `/usr/local/bin`, replace it with a thin
wrapper that delegates into the checked-out repository path:

```sh
#!/bin/sh
exec /srv/codex-power-pack/scripts/deploy_mcp.sh "$@"
```

That wrapper must not contain deploy logic of its own. The repo checkout remains the
single source of truth.
