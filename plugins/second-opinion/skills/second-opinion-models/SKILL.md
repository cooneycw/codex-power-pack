---
name: "second-opinion-models"
description: "Inspect available host-managed second-opinion models and choose review depth"
---

# Choose Second-Opinion Models

1. Check `codex mcp get second-opinion`; on failure, report the standard
   graceful-degradation message and stop before collecting code.
2. Call `list_available_models` through the configured service. Show only
   available model keys, provider, description, and any cost signal returned by
   the service; never expose provider configuration or key state.
3. Ask the user to choose one or more models and `brief`, `detailed`, or
   `in_depth` review. Explain that multi-provider selection gives independent
   perspectives but may cost more and take longer.
4. Hand the selected model keys and depth to `$second-opinion-start` or
   `$evaluate-issue`.
