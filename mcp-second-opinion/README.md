# MCP Second Opinion

Multi-model code review MCP server for Codex.

## Features

- **Code Review**: Get AI-powered second opinions on code issues
- **Multi-Model Support**: Consult multiple LLMs (Gemini 3.1, Claude Sonnet/Haiku/Opus, GPT-5.3 Codex, o4-mini)
- **Session-Based**: Interactive multi-turn conversations for deeper analysis
- **Visual Analysis**: Support for screenshot/image analysis (Playwright integration)
- **Streamable HTTP**: Stateless transport - no persistent connection, resilient to disconnects

## Quick Start

```bash
# Start the server (uv handles dependencies automatically)
./start-server.sh

# Or run directly
uv run python src/server.py
```

## Add to Codex

Register the server in your Codex MCP configuration.

**stdio (recommended):**
```json
{
  "mcpServers": {
    "second-opinion": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/codex-power-pack/mcp-second-opinion",
        "python",
        "src/server.py",
        "--stdio"
      ]
    }
  }
}
```

**Streamable HTTP:**
```json
{
  "mcpServers": {
    "second-opinion": {
      "type": "streamable-http",
      "url": "http://127.0.0.1:8080/mcp"
    }
  }
}
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Gemini API key |
| `OPENAI_API_KEY` | No | OpenAI API key (for multi-model) |
| `ANTHROPIC_API_KEY` | No | Anthropic API key (for Claude models) |

## MCP Tools

| Tool | Description |
|------|-------------|
| `get_code_second_opinion` | Single-model code review |
| `get_multi_model_second_opinion` | Multi-model parallel review |
| `list_available_models` | Show available LLM models |
| `create_session` | Start interactive session |
| `consult` | Continue session conversation |
| `get_session_history` | View session transcript |
| `close_session` | End session with summary |
| `list_sessions` | Show active sessions |
| `approve_fetch_domain` | Allow URL fetching for domain |
| `revoke_fetch_domain` | Remove domain approval |
| `list_fetch_domains` | Show approved domains |
| `health_check` | Server status |

## Troubleshooting

### Error: `-32602: Invalid request parameters`

This usually means Codex cannot reach the server or the SSE session expired.

**Fix 1: Upgrade to streamable-http transport (recommended)**

The streamable-http transport is stateless - each request is independent, so there are no
session timeouts or disconnection issues. Update your `.mcp.json`:

```json
{
  "mcpServers": {
    "second-opinion": {
      "type": "streamable-http",
      "url": "http://127.0.0.1:8080/mcp"
    }
  }
}
```

**Fix 2: Switch to stdio transport**

```bash
# Re-register the server in your Codex MCP config using stdio
# and point it at src/server.py --stdio
```

**If using HTTP transport:** Ensure the server is running before starting Codex:

```bash
# Check if server is running
curl -s http://127.0.0.1:8080/ | jq .

# Start if not running
cd /path/to/codex-power-pack/mcp-second-opinion
./start-server.sh
```

### Diagnosing Configuration Issues

```bash
# Run pre-flight diagnostics
./start-server.sh --diagnose

# Or directly
uv run python src/server.py --diagnose
```

This checks API keys, .env file, port availability, and available models.

### No API keys configured

The server starts but all LLM calls will fail. Add at least one key:

```bash
cp .env.example .env
# Edit .env - add GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY
```

## License

MIT
