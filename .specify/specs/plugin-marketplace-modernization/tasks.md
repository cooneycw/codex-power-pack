# Task Breakdown: Plugin Marketplace Modernization

> **Spec:** `.specify/specs/plugin-marketplace-modernization/spec.md`
> **Sync:** epics and stories below are mirrored to GitHub issues in
> cooneycw/codex-power-pack (companion issues B1/B2/E3 in
> cooneycw/claude-power-pack). Issue numbers recorded after sync.
> **Delivery:** Codex builds all tasks; Claude reviews at the end (F4).

| ID  | Epic | Title | Depends on | Repo |
|-----|------|-------|------------|------|
| 0.1 | 0 | Threat model: secrets, supply chain, hooks, telemetry egress | - | CxPP |
| 0.2 | 0 | Spike: borrow-vs-build secret-leak guardrails (Secret Guard / Agent Guard) | 0.1 | CxPP |
| A1  | A | Delete bundled MCP servers, compose runtime, deploy scripts | - | CxPP |
| A2  | A | Wire shared external MCP pointers + host-managed-services doc | A1 | CxPP |
| A3  | A | Purge legacy strays + retire lib/spec_bridge | - | CxPP |
| A4  | A | Retire custom skill/MCP installers and make targets | A1 | CxPP |
| B1  | B | SKILL.md generator with harness transforms | - | CPP |
| B2  | B | Cross-repo publish + bidirectional drift gates | B1 | CPP |
| B3  | B | Remove frozen .claude/commands fork; receive generated skills | B2 | CxPP |
| B4  | B | Harness-lint CI gate for Claude-only constructs | B3 | CxPP |
| C1  | C | Marketplace scaffold + first plugin (project) proven E2E | 0.1, A1 | CxPP |
| C2  | C | Per-family plugins for all families + openai.yaml policy | C1, B3 | CxPP |
| C3  | C | Version pinning + tagged release process | C1 | CxPP |
| C4  | C | cxpp:init/update/status thin infra fallback | A2, A4 | CxPP |
| C5  | C | README/AGENTS.md rewrite, docs cutover | C2, C4 | CxPP |
| D1  | D | project family: $project-init zero-to-repo (+#55) | C1 | CxPP |
| D2  | D | spec family: spec-kit adopt + gh issue sync | C1 | CxPP |
| D3  | D | flow family: issue lifecycle adapted to Codex | C2 | CxPP |
| D4  | D | github family: issue management | C2 | CxPP |
| D5  | D | cicd family: Makefile + pipeline gen (+#53) | C2 | CxPP |
| D6  | D | secrets family: AWS SM + masking guardrails | 0.2, C2 | CxPP |
| D7  | D | woodpecker skills replacing the MCP server (+#57) | D5, D6 | CxPP |
| D8  | D | security family: deterministic half only | C2 | CxPP |
| D9  | D | agents-md family: lint + help | C2 | CxPP |
| D10 | D | documentation family: c4 + pptx | C2 | CxPP |
| D11 | D | qa family: qa-test | C2 | CxPP |
| D12 | D | evaluate + second-opinion client commands | A2, C2 | CxPP |
| E1  | E | Spike: Codex hooks event surface + masking design | 0.1 | CxPP |
| E2  | E | Fail-open friction writer to shared ledger (harness=codex) | E1 | CxPP |
| E3  | E | Ledger feathering: harness tag in schema/consumers | E2 | CPP |
| E4  | E | Codex retro loop consuming the ledger (+#58, +#59) | E2 | CxPP |
| F1  | F | Woodpecker CI refresh (gitleaks-first, image gates) | A1 | CxPP |
| F2  | F | Test suite + drift gates green post-demolition | B4, C2 | CxPP |
| F3  | F | E2E acceptance: fresh-install Codex scaffolds project + spec | D1, D2 | CxPP |
| F4  | F | Claude review-and-tune gap pass over the wave | all | CxPP |

## Definition of Done (every D-story)

1. Family installs as its own plugin via `/plugins` from the repo marketplace.
2. Codex (not Claude) executes the family's core skill end to end (dogfood gate).
3. No Claude-only constructs (harness-lint green); no secrets in output/logs.
4. `make verify` green; docs updated.
