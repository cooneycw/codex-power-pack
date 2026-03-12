---
description: Run automated QA testing against a URL or configured shortcut and file bugs as GitHub issues
allowed-tools: Bash(cat:*), Bash(gh:*), Read, AskUserQuestion
---

> Trigger parity entrypoint for `/qa:test`.
> Backing skill: `qa-test` (`.codex/skills/qa-test/SKILL.md`).

# QA Test - Automated Web Testing

Perform automated QA testing on a web application using Playwright MCP.

**Arguments:** `$ARGUMENTS`
- Format: `<url-or-shortcut> [area] [--find N]`
- Examples:
  - `/qa:test https://example.com` - Test full site
  - `/qa:test myapp dashboard` - Test a named area via shortcut
  - `/qa:test myapp login --find 3` - Find up to 3 bugs in login area

---

## Step 1: Load Configuration

Check for `.codex/qa.yml` in the project root:

```bash
cat .codex/qa.yml 2>/dev/null
```

If `.codex/qa.yml` exists, parse:
- `project.url` - default project URL
- `project.repository` - GitHub repo for issue creation
- `shortcuts` - shortcut-to-URL map
- `test_areas` - named areas with paths, descriptions, and checks

If `.codex/qa.yml` does not exist, use interactive fallback.

## Step 1b: Interactive Fallback (No Config)

If no `.codex/qa.yml` exists and no URL was provided:

1. Inform the user:
   ```
   No .codex/qa.yml found. Running in interactive mode.
   Tip: Copy templates/qa.yml.example to .codex/qa.yml for persistent config.
   ```
2. Ask for target URL via AskUserQuestion.
3. Ask for repository (or detect via `gh repo view`).
4. Run generic test areas:
   - Click interactive elements
   - Fill and submit forms
   - Check browser console for errors
   - Test navigation links

## Step 2: Parse Arguments

Extract from `$ARGUMENTS`:
1. Target URL or shortcut (resolve via `shortcuts`)
2. Optional `area` (must exist in `test_areas`)
3. Optional `--find N` bug cap (default: 1)

If shortcut is missing, report available shortcuts.
If area is missing, report available areas.

## Step 3: Create Browser Session

Use regular Playwright MCP to create a headless browser session:

```
create_session(headless=true, viewport_width=1280, viewport_height=720)
```

Store `session_id`.

## Step 4: Navigate to Target

- Resolve shortcut to URL when needed
- Append area `path` when an area is specified

```
browser_navigate(session_id, url, wait_until="networkidle")
```

## Step 5: Test Methodology

### Area-driven checks (when area + tests are configured)

For each checklist item:
1. Locate relevant elements
2. Perform the interaction
3. Verify expected behavior
4. Check console: `browser_console_messages(session_id)`
5. Record failures

### Full-site checks (when no area provided)

Iterate configured `test_areas`, navigate to each path, run each area's checks.

### Generic checks (no config or no explicit test plans)

1. Click response testing
   ```
   browser_query_selector_all(session_id, "button, [onclick], a[href], input[type=submit], [role=button]")
   ```
2. Form testing
3. Navigation testing

Record JS errors, broken navigation, and 4xx/5xx failures.

## Step 6: Bug Classification

| Severity | Description | Example |
|----------|-------------|---------|
| Critical | Blocks core functionality | 403 on main action |
| High | Major feature broken | Form submission fails |
| Medium | Feature partially works | Missing validation |
| Low | UI/UX issues | Misaligned elements |

## Step 7: Log Bugs as GitHub Issues

For each bug:
1. Resolve repository from config or `gh repo view`
2. Title: `[Bug] <Area>: <Brief description>`
3. Include in body:
   - Repro steps
   - Expected vs actual behavior
   - Console errors
   - Technical analysis
   - Environment details
4. Apply labels (`bug`, optional severity label)

```bash
gh issue create --repo <repo> --title "<title>" --body "<body>" --label "bug"
```

## Step 8: Report Summary

```markdown
## QA Test Results

**Target:** <URL>
**Config:** .codex/qa.yml | interactive mode
**Areas Tested:** <list>
**Bugs Found:** N

### Issues Created
| # | Severity | Area | Description |
|---|----------|------|-------------|
| 1 | Critical | login | Form 500 on submit |

### Test Coverage
(Dynamic checklist from config test_areas, or generic areas tested)
```

## Step 9: Cleanup

```
close_session(session_id)
```
