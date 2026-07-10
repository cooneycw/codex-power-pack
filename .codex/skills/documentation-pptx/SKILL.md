---
name: "documentation-pptx"
description: "Create and quality-check a PowerPoint presentation without nano-banana"
---

# Presentation Creation

Use the installed Codex `$pptx` skill to create or update a `.pptx` presentation.
Codex Power Pack supplies the communication workflow; it does not use or start
the retired nano-banana MCP service.

## Procedure

1. Establish audience, decision, slide count, and any required source material.
   Ask before creating a new presentation when these are not provided.
2. Invoke `$pptx` for the actual deck authoring. Use its prescribed
   template-analysis or from-scratch workflow and keep source data separate from
   the output deck.
3. When a C4 model exists, use the GitHub-renderable Mermaid source as the
   diagram authority. Export a rendered image only when the presentation needs a
   bitmap; do not recreate architecture by hand.
4. Perform the `$pptx` content and visual QA loop before reporting completion:
   extract text, render slides, inspect for overflow/overlap, correct findings,
   and re-render.

## Safety and Scope

- Do not invoke nano-banana or any deleted CxPP runtime service.
- Do not place secrets, credentials, or raw production logs in slides.
- Keep generated `.pptx` files and any source assets in a user-approved project
  location; report their paths and the verification performed.
