# Installation Issues Log

Issues encountered during installation of the codex-power-pack MCP servers.

## uv Installation

This project uses [uv](https://docs.astral.sh/uv/) for Python dependency management. Install it with:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Issue 1: Playwright Browsers Not Installed

**Problem**: Playwright MCP server fails to start because Chromium browser is not installed.

**Error**:
```
playwright._impl._errors.Error: Executable doesn't exist at /home/user/.cache/ms-playwright/chromium-xxx/chrome-linux/chrome
```

**Solution**: Install Playwright browsers:
```bash
cd mcp-playwright-persistent  # codex-playwright service
uv run playwright install chromium
```

---

## Issue 2: API Keys Not Configured

**Problem**: MCP Second Opinion server fails because API keys are missing.

**Error**:
```
Missing API key: GEMINI_API_KEY or OPENAI_API_KEY
```

**Solution**: Copy the .env.example and add your keys:
```bash
cd mcp-second-opinion  # codex-second-opinion service
cp .env.example .env
# Edit .env with your API keys
```

---

## Issue 3: Skills Not Found Outside Repository Root

**Problem**: Codex cannot resolve slash-style workflows from unrelated directories.

**Symptoms**:
- First-run command invocations fail with "skill not found"
- Running from `~/Projects/<some-other-repo>/` does not see codex-power-pack workflows

**Solution**: Install repository skill packages into `~/.codex/skills` and run doctor checks:
```bash
cd codex-power-pack
make skills-install-codex
make skills-doctor
```

If doctor reports drift/conflicts:
```bash
make skills-install-codex SKILLS_OVERWRITE=1
```

---

*Generated: 2025-12-20*
*Updated: 2026-03-13 - Added Codex skill discovery/install troubleshooting*
