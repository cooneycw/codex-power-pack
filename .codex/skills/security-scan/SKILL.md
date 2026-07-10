---
name: "security-scan"
description: "Run deterministic security checks with available external scanners"
---

# Security Scan

Run the full deterministic scan in a CxPP checkout:

```bash
python3 -m lib.security scan --path <project-dir>
```

It combines `$security-quick` checks with gitleaks, pip-audit, and npm audit
when those tools are installed. The scan reports missing optional tools rather
than pretending they ran. Critical findings block the command; use native Codex
review separately for semantic vulnerabilities.
