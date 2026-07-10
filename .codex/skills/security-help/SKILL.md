---
name: "security-help"
description: "Explain Codex Power Pack deterministic security scanning"
---

# Security Help

This family is the deterministic half of security review:

- `$security-quick` checks source/configuration patterns without external tools.
- `$security-scan` adds gitleaks, pip-audit, and npm audit when available.
- `$security-deep` includes Git history through gitleaks.

Use Codex native code review for semantic reasoning about authorization, data
flow, injection, and business logic. Do not claim that deterministic scanners
replace that review.

In a CxPP checkout, run `python3 -m lib.security <quick|scan|deep> --path <dir>`.
The command exits non-zero for blockers; use that result as a gate rather than
silencing findings. Never paste a secret into a scan command or its report.
