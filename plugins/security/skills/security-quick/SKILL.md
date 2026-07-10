---
name: "security-quick"
description: "Run fast deterministic source and configuration security checks"
---

# Security Quick Scan

Run the zero-dependency deterministic checks before a commit or focused repair:

```bash
python3 -m lib.security quick --path <project-dir>
```

It checks ignored secret files, permissions, high-confidence source patterns,
tracked environment files, and unsafe debug flags. A blocker is a stop signal:
fix or rotate the affected credential and rerun; never suppress the output by
printing the raw value.
