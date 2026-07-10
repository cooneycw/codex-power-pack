# C4 Architecture - Codex Power Pack

## L1 System Context

_L1 - 5 nodes, 4 edges - [`c4-l1-context.mmd`](c4-l1-context.mmd)_

```mermaid
flowchart TB
  subgraph cxpp_boundary["Codex Power Pack"]
    cxpp["Codex Power Pack"]:::system_focus
  end
  developer(("Developer")):::person
  codex["Codex Client"]:::system
  github["GitHub Marketplace Source"]:::system
  host_mcp["Host-managed MCP Services"]:::system
  developer -->|"uses"| codex
  codex -->|"installs plugins"| cxpp
  cxpp -->|"distributed from"| github
  cxpp -->|"configures pointers to"| host_mcp
  classDef person fill:#08427b,color:#ffffff,stroke:#0f172a
  classDef system fill:#6b7280,color:#ffffff,stroke:#0f172a
  classDef system_focus fill:#1168bd,color:#ffffff,stroke:#0f172a
```

## L2 Containers

_L2 - 5 nodes, 5 edges - [`c4-l2-container.mmd`](c4-l2-container.mmd)_

```mermaid
flowchart TB
  subgraph repo["codex-power-pack repository"]
    marketplace_catalog["Marketplace Catalog (.agents)"]:::container
    family_plugins["Family Plugins (plugins/)"]:::container
    codex_skills["Codex Skills (.codex/skills)"]:::container
    runtime_libraries["Deterministic Libraries (lib/)"]:::container
    quality_gates["Quality Gates (Makefile + tests)"]:::container
  end
  marketplace_catalog -->|"indexes"| family_plugins
  family_plugins -->|"packages skills from"| codex_skills
  codex_skills -->|"uses deterministic helpers"| runtime_libraries
  quality_gates -->|"validates"| family_plugins
  quality_gates -->|"drift-checks"| codex_skills
  classDef container fill:#15803d,color:#ffffff,stroke:#0f172a
```

## L3 Plugin Distribution Components

_L3 - 5 nodes, 5 edges - [`c4-l3-plugin-distribution.mmd`](c4-l3-plugin-distribution.mmd)_

```mermaid
flowchart TB
  subgraph plugin_package["One family plugin"]
    plugin_manifest["plugin.json Manifest"]:::component
    skill_payload["Skill Payload"]:::component
    openai_metadata["agents/openai.yaml Metadata"]:::component
  end
  marketplace_entry["Marketplace Entry"]:::component
  package_tests["Plugin Package Tests"]:::component
  marketplace_entry -->|"locates"| plugin_manifest
  plugin_manifest -->|"declares"| skill_payload
  skill_payload -->|"includes"| openai_metadata
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

_Generated 2026-07-10T00:00:00Z_
