---
name: "woodpecker-help"
description: "Explain the safe Woodpecker CI client workflows available through Codex Power Pack"
---

# Woodpecker Help

Use this family to inspect or restart a Woodpecker pipeline through its HTTP API.
It is a client only: it never installs, starts, deploys, or reconfigures a
Woodpecker server or agent.

- `$woodpecker-status` lists recent pipelines and their states.
- `$woodpecker-logs` fetches and decodes one step's base64 log payload.
- `$woodpecker-restart` restarts one identified pipeline after confirmation.

## Safety

- Require `WOODPECKER_SERVER` and obtain `WOODPECKER_TOKEN` only through
  `$secrets-run`; never ask the user to paste a token or print it.
- Use a read-only token for status and logs. Restart requires a separately
  authorized write-capable token.
- Send secrets only in the HTTP Authorization header, never in a URL, command
  output, issue, commit, or log.
- If the server is unavailable, report the failed non-secret health check and
  the required host prerequisite. Do not start a service.
