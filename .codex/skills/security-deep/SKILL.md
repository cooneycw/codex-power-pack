---
name: "security-deep"
description: "Run deterministic security checks including Git history"
---

# Security Deep Scan

Run the history-aware deterministic scan:

```bash
python3 -m lib.security deep --path <project-dir>
```

With gitleaks available, this includes Git history so removed-but-committed
credentials are still treated as compromised. Rotate first; do not expose the
finding in an issue or command output. History rewriting is a separate,
explicitly approved remediation.
