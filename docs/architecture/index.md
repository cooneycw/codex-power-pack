# C4 Architecture - Codex Power Pack

## L1 System Context

_L1 - 6 nodes, 5 edges - [`c4-l1-context.mmd`](c4-l1-context.mmd)_

```mermaid
flowchart TB
  subgraph cxpp_boundary["Codex Power Pack"]
    cxpp["Codex Power Pack"]:::system_focus
  end
  developer(("Developer")):::person
  codex["Codex Client"]:::system
  cpp["Claude Power Pack Skill Source"]:::system
  github["GitHub Marketplace Source"]:::system
  host_mcp["Host-managed MCP Services"]:::system
  developer -->|"uses"| codex
  codex -->|"installs plugins"| cxpp
  cxpp -->|"pulls pinned generated skills from"| cpp
  cxpp -->|"distributed from"| github
  cxpp -->|"configures pointers to"| host_mcp
  classDef person fill:#08427b,color:#ffffff,stroke:#0f172a
  classDef system fill:#6b7280,color:#ffffff,stroke:#0f172a
  classDef system_focus fill:#1168bd,color:#ffffff,stroke:#0f172a
```

## L2 Containers

_L2 - 6 nodes, 7 edges - [`c4-l2-container.mmd`](c4-l2-container.mmd)_

```mermaid
flowchart TB
  subgraph repo["codex-power-pack repository"]
    marketplace_catalog["Marketplace Catalog (.agents)"]:::container
    family_plugins["Family Plugins (plugins/)"]:::container
    codex_skills["Codex Skills (.codex/skills)"]:::container
    vendor_snapshot["Pinned CPP Snapshot (vendor/)"]:::container
    runtime_libraries["Deterministic Libraries (lib/)"]:::container
    quality_gates["Quality Gates (Makefile + tests)"]:::container
  end
  marketplace_catalog -->|"indexes"| family_plugins
  family_plugins -->|"packages skills from"| codex_skills
  vendor_snapshot -->|"pins and integrity-checks"| codex_skills
  codex_skills -->|"uses deterministic helpers"| runtime_libraries
  quality_gates -->|"validates"| family_plugins
  quality_gates -->|"drift-checks"| codex_skills
  quality_gates -->|"checks upstream currency"| vendor_snapshot
  classDef container fill:#15803d,color:#ffffff,stroke:#0f172a
```

## L3 Skill Vendoring and Plugin Distribution

_L3 - 8 nodes, 8 edges - [`c4-l3-plugin-distribution.mmd`](c4-l3-plugin-distribution.mmd)_

```mermaid
flowchart TB
  subgraph plugin_package["One family plugin"]
    plugin_manifest["plugin.json Manifest"]:::component
    skill_payload["Skill Payload"]:::component
    openai_metadata["agents/openai.yaml Metadata"]:::component
  end
  marketplace_entry["Marketplace Entry"]:::component
  package_tests["Plugin Package Tests"]:::component
  skill_sync["Skill Sync"]:::component
  runtime_overlay["Codex Runtime Overlay"]:::component
  currency_gate["Upstream Currency Gate"]:::component
  marketplace_entry -->|"locates"| plugin_manifest
  plugin_manifest -->|"declares"| skill_payload
  skill_payload -->|"includes"| openai_metadata
  skill_sync -->|"applies during refresh"| runtime_overlay
  runtime_overlay -->|"writes adapted payload"| skill_payload
  currency_gate -->|"compares current CPP through"| runtime_overlay
  package_tests -->|"validates"| marketplace_entry
  package_tests -->|"checks parity"| skill_payload
  classDef component fill:#7e22ce,color:#ffffff,stroke:#0f172a
```

## L4 Security and Telemetry Code

_L4 - 4 nodes, 3 edges - [`c4-l4-security-runtime.mmd`](c4-l4-security-runtime.mmd)_

```mermaid
classDiagram
  class FrictionWriter {
    +write(event)
    -mask(payload)
  }
  class FrictionEvent {
    +validate()
  }
  class OutputMasker {
    +register_secret(value)
    +mask(text)
  }
  class SecretBundle {
    +secrets: dict
  }
  FrictionWriter --> FrictionEvent : writes
  FrictionWriter --> OutputMasker : uses
  OutputMasker --> SecretBundle : masks values from
```

_Generated 2026-07-19T10:19:13Z_
