---
name: "second-opinion-help"
description: "Explain the host-managed multi-model second-opinion workflow"
---

# Second Opinion Help

This family is a client for the host-managed `mcp-second-opinion` service. It
does not run a server, hold provider keys, or copy model credentials into this
repository.

- `$second-opinion-start`: consult available model(s) about a file, diff, or
  pasted design question.
- `$second-opinion-models`: inspect available models and choose a cost/depth
  trade-off.
- `$evaluate-issue`: run a structured multi-model evaluation before writing a
  spec-ready recommendation.

## Availability Contract

First run `codex mcp get second-opinion`. If the pointer or service is absent,
report exactly: `Second-opinion service unavailable; continue with Codex's own
analysis or configure the host-managed MCP pointer with $cxpp-init.` Do not
attempt to start a local server or request API keys.
