---
name: "documentation-c4"
description: "Generate GitHub-renderable Mermaid C4 architecture diagrams"
---

# C4 Architecture Diagrams

Create a version-controlled C4 model and render it into Mermaid diagrams that
GitHub displays inline. This skill is self-contained: it uses the bundled
`scripts/c4-mermaid.py` renderer and does not use an MCP image service.

## Procedure

1. Read `AGENTS.md`, `README.md`, the top-level directory tree, and the relevant
   configuration files. Model only verified components and integrations.
2. Create or update `docs/architecture/c4-model.json` with L1 context, L2
   containers, L3 components, and L4 classes. Keep identifiers stable and
   globally unique.
3. Locate this installed skill's directory and run its bundled renderer:

```bash
python3 <documentation-c4-skill-dir>/scripts/c4-mermaid.py \
  --model docs/architecture/c4-model.json \
  --out docs/architecture \
  --project "<project name>" \
  --timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

4. Treat an invalid reference as a blocking error. Review density, orphan-node,
   and boundary warnings before committing.
5. Confirm `docs/architecture/index.md` contains Mermaid code fences and inspect
   the rendered diagrams in the GitHub file view. Commit the model, `.mmd`
   files, manifest, and index together.

## Output Contract

- L1-L3 use Mermaid `flowchart`; L4 uses Mermaid `classDiagram`.
- The renderer produces one `.mmd` file per level, `index.md`, and
  `c4-manifest.json`.
- It sanitizes Mermaid identifiers and fails non-zero on invalid node or class
  references. Do not suppress those failures.
