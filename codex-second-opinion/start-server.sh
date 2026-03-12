#!/bin/bash
# Start the Second Opinion MCP Server
# This script uses uv to manage dependencies and run the server

set -euo pipefail

# Change to the server directory
cd "$(dirname "$0")"

# Pre-flight: check uv is available
if ! command -v uv &>/dev/null; then
    echo "ERROR: 'uv' not found. Install it: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi

# Pre-flight: check local env, process env, or AWS secret wiring
if [[ ! -f ../.env ]] && [[ ! -f .env ]] && [[ -z "${GEMINI_API_KEY:-}" ]] && [[ -z "${OPENAI_API_KEY:-}" ]] && [[ -z "${ANTHROPIC_API_KEY:-}" ]] && [[ -z "${AWS_API_KEYS_SECRET_NAME:-}" ]] && [[ -z "${AWS_SECRET_NAME:-}" ]]; then
    echo "WARNING: No local env, no API keys in process env, and no AWS secret configured." >&2
    echo "  The server will start but model calls will fail." >&2
    echo "  Preferred: set AWS_API_KEYS_SECRET_NAME=codex_llm_apikeys in ../.env with AWS credentials." >&2
    echo "  Fallback: copy .env.example to .env and add API keys directly." >&2
    echo "" >&2
fi

# Handle --diagnose flag
if [[ "${1:-}" == "--diagnose" ]]; then
    echo "Running diagnostics..."
    uv run python src/server.py --diagnose
    exit $?
fi

# Start the server using uv
echo "Starting Second Opinion MCP Server..."
uv run python src/server.py "$@"
