"""Helpers for invoking Codex Power Pack security gates from the runner."""

from __future__ import annotations

CPP_DIR_DISCOVERY = """CPP_DIR=""
for dir in "${CODEX_POWER_PACK_DIR:-}" \
  "$HOME/Projects/codex-power-pack" \
  /opt/codex-power-pack \
  "$HOME/.codex-power-pack"; do
  if [ -n "$dir" ] && [ -f "$dir/AGENTS.md" ]; then
    CPP_DIR="$dir"
    break
  fi
done
"""


def build_security_gate_command(gate: str) -> str:
    """Build a shell command that runs a security gate from the CPP repo root."""
    return (
        CPP_DIR_DISCOVERY
        + 'if [ -z "$CPP_DIR" ]; then echo "codex-power-pack not found" >&2; exit 1; fi; '
        + 'PYTHON_BIN="$CPP_DIR/.venv/bin/python"; '
        + 'if [ ! -x "$PYTHON_BIN" ]; then PYTHON_BIN=python3; fi; '
        + f'PYTHONPATH="$CPP_DIR${{PYTHONPATH:+:$PYTHONPATH}}" "$PYTHON_BIN" -m lib.security gate {gate}'
    )


def build_security_gate_skip_if() -> str:
    """Build a shell expression that skips when lib.security is unavailable."""
    return (
        CPP_DIR_DISCOVERY
        + 'if [ -z "$CPP_DIR" ]; then exit 0; fi; '
        + 'PYTHON_BIN="$CPP_DIR/.venv/bin/python"; '
        + 'if [ ! -x "$PYTHON_BIN" ]; then PYTHON_BIN=python3; fi; '
        + '! PYTHONPATH="$CPP_DIR${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" -c \'import lib.security\' 2>/dev/null'
    )
