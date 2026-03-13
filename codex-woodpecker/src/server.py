"""MCP Woodpecker CI server.

Provides Codex-facing pipeline controls and a Go-compatible compatibility layer
for users migrating from the upstream `woodpecker-mcp` binary.
"""

import argparse
import logging
from pathlib import Path
from typing import Any, Optional

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from client import WoodpeckerClient
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

mcp = FastMCP(Config.SERVER_NAME)


def _get_client() -> WoodpeckerClient:
    """Create a Woodpecker API client from current config."""
    if not Config.WOODPECKER_URL or not Config.WOODPECKER_API_TOKEN:
        raise ValueError(
            "Woodpecker not configured. Set WOODPECKER_URL and WOODPECKER_API_TOKEN "
            "environment variables, or set AWS_SECRET_NAME (default: codex-power-pack) to "
            "auto-fetch from AWS Secrets Manager."
        )
    return WoodpeckerClient(Config.WOODPECKER_URL, Config.WOODPECKER_API_TOKEN)


def _extract_pipeline_steps(pipeline: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract flattened workflow step metadata from a pipeline payload."""
    steps: list[dict[str, Any]] = []
    for wf in pipeline.get("workflows", []):
        for child in wf.get("children", []):
            steps.append({
                "id": child.get("id"),
                "name": child.get("name"),
                "state": child.get("state"),
                "exit_code": child.get("exit_code"),
            })
    return steps


def _pipeline_payload(pipeline: dict[str, Any]) -> dict[str, Any]:
    """Normalize Woodpecker pipeline details for MCP responses."""
    return {
        "number": pipeline.get("number"),
        "status": pipeline.get("status"),
        "event": pipeline.get("event"),
        "branch": pipeline.get("branch"),
        "commit": pipeline.get("commit", "")[:12],
        "message": (pipeline.get("message") or "")[:120],
        "author": pipeline.get("author"),
        "started_at": pipeline.get("started_at"),
        "finished_at": pipeline.get("finished_at"),
        "steps": _extract_pipeline_steps(pipeline),
    }


def _default_config_candidates() -> list[Path]:
    """Return likely locations for .woodpecker.yml when lint_config is called."""
    cwd = Path.cwd()
    repo_root = Path(__file__).resolve().parents[2]
    service_root = Path(__file__).resolve().parents[1]
    return [
        cwd / ".woodpecker.yml",
        repo_root / ".woodpecker.yml",
        service_root / ".woodpecker.yml",
    ]


@mcp.custom_route("/", methods=["GET"])
async def root_health_check(request: Request) -> JSONResponse:
    """Health check endpoint."""
    configured = bool(Config.WOODPECKER_URL and Config.WOODPECKER_API_TOKEN)
    status = "healthy" if configured else "no_credentials"
    return JSONResponse({
        "status": status,
        "server": Config.SERVER_NAME,
        "version": Config.SERVER_VERSION,
        "woodpecker_url": Config.WOODPECKER_URL or "(not configured)",
    })


@mcp.tool()
async def health_check() -> dict:
    """Check connectivity to the Woodpecker CI server.

    Verifies that the configured URL and API token can reach the
    Woodpecker instance and list repos.

    Returns:
        dict with status, woodpecker_url, and repo_count.
    """
    try:
        client = _get_client()
        repos = await client.list_repos()
        return {
            "status": "connected",
            "woodpecker_url": Config.WOODPECKER_URL,
            "repo_count": len(repos),
        }
    except ValueError as exc:
        return {"status": "not_configured", "error": str(exc)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool()
async def list_repos() -> dict:
    """List all Woodpecker CI repositories.

    Returns repos the API token has access to, with their IDs, names,
    and active status.

    Returns:
        dict with repos list (id, full_name, active, default_branch).
    """
    try:
        client = _get_client()
        repos = await client.list_repos()
        return {
            "repo_count": len(repos),
            "repos": [
                {
                    "id": r.get("id"),
                    "full_name": r.get("full_name", f"{r.get('owner', '?')}/{r.get('name', '?')}"),
                    "active": r.get("active", False),
                    "default_branch": r.get("default_branch", "main"),
                }
                for r in repos
            ],
        }
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
async def lookup_repo(owner: str, name: str) -> dict:
    """Look up a Woodpecker repo by owner and name.

    Args:
        owner: Repository owner (e.g. 'cooneycw').
        name: Repository name (e.g. 'codex-power-pack').

    Returns:
        dict with repo id, full_name, active, and default_branch.
    """
    try:
        client = _get_client()
        r = await client.lookup_repo(owner, name)
        return {
            "id": r.get("id"),
            "full_name": r.get("full_name", f"{owner}/{name}"),
            "active": r.get("active", False),
            "default_branch": r.get("default_branch", "main"),
        }
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
async def list_pipelines(
    repo_id: int,
    page: int = 1,
    per_page: int = 10,
) -> dict:
    """List recent pipelines for a Woodpecker repo.

    Args:
        repo_id: Numeric repo ID (use list_repos or lookup_repo to find it).
        page: Page number (default: 1).
        per_page: Results per page (default: 10, max: 50).

    Returns:
        dict with pipelines list (number, status, branch, commit, event, started, finished).
    """
    try:
        client = _get_client()
        per_page = min(per_page, 50)
        pipelines = await client.list_pipelines(repo_id, page, per_page)
        return {
            "pipeline_count": len(pipelines),
            "pipelines": [
                {
                    "number": p.get("number"),
                    "status": p.get("status"),
                    "event": p.get("event"),
                    "branch": p.get("branch"),
                    "commit": p.get("commit", "")[:12],
                    "message": (p.get("message") or "")[:80],
                    "author": p.get("author"),
                    "started_at": p.get("started_at"),
                    "finished_at": p.get("finished_at"),
                }
                for p in pipelines
            ],
        }
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
async def get_pipeline(repo_id: int, pipeline_number: int) -> dict:
    """Get details for a specific pipeline.

    Args:
        repo_id: Numeric repo ID.
        pipeline_number: Pipeline number.

    Returns:
        dict with full pipeline details including workflow steps.
    """
    try:
        client = _get_client()
        pipeline = await client.get_pipeline(repo_id, pipeline_number)
        return _pipeline_payload(pipeline)
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
async def create_pipeline(
    repo_id: int,
    branch: str = "main",
    variables: Optional[dict[str, str]] = None,
) -> dict:
    """Trigger a new pipeline on the specified branch.

    Args:
        repo_id: Numeric repo ID.
        branch: Branch to build (default: main).
        variables: Optional key-value pairs passed as pipeline variables.

    Returns:
        dict with the created pipeline number and status.
    """
    try:
        client = _get_client()
        p = await client.create_pipeline(repo_id, branch, variables)
        return {
            "number": p.get("number"),
            "status": p.get("status"),
            "branch": p.get("branch"),
            "message": "Pipeline triggered successfully.",
        }
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
async def cancel_pipeline(repo_id: int, pipeline_number: int) -> dict:
    """Cancel a running pipeline.

    Args:
        repo_id: Numeric repo ID.
        pipeline_number: Pipeline number to cancel.

    Returns:
        dict with cancellation status.
    """
    try:
        client = _get_client()
        await client.cancel_pipeline(repo_id, pipeline_number)
        return {"status": "cancelled", "pipeline_number": pipeline_number}
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
async def approve_pipeline(repo_id: int, pipeline_number: int) -> dict:
    """Approve a blocked/pending pipeline.

    Args:
        repo_id: Numeric repo ID.
        pipeline_number: Pipeline number to approve.

    Returns:
        dict with approval status.
    """
    try:
        client = _get_client()
        await client.approve_pipeline(repo_id, pipeline_number)
        return {"status": "approved", "pipeline_number": pipeline_number}
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
async def get_pipeline_logs(
    repo_id: int,
    pipeline_number: int,
    step_id: int,
) -> dict:
    """Get logs for a specific pipeline step.

    Use get_pipeline first to find step IDs from the workflow children.

    Args:
        repo_id: Numeric repo ID.
        pipeline_number: Pipeline number.
        step_id: Step ID (from get_pipeline workflows[].children[].id).

    Returns:
        dict with decoded log text.
    """
    try:
        client = _get_client()
        log_text = await client.get_step_logs(repo_id, pipeline_number, step_id)
        return {
            "pipeline_number": pipeline_number,
            "step_id": step_id,
            "log": log_text,
            "log_length": len(log_text),
        }
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
async def get_pipeline_status(
    repo_id: int,
    pipeline_number: Optional[int] = None,
    latest: bool = False,
) -> dict:
    """Compatibility alias for the Go `get_pipeline_status` tool.

    Args:
        repo_id: Numeric repo ID.
        pipeline_number: Pipeline number. Required unless `latest` is true.
        latest: If true, fetch the latest pipeline for this repo.
    """
    try:
        client = _get_client()

        selected_number = pipeline_number
        if latest:
            pipelines = await client.list_pipelines(repo_id, page=1, per_page=1)
            if not pipelines:
                return {"error": f"No pipelines found for repo_id={repo_id}"}
            selected_number = pipelines[0].get("number")

        if selected_number is None:
            return {"error": "pipeline_number is required when latest=false"}

        pipeline = await client.get_pipeline(repo_id, int(selected_number))
        payload = _pipeline_payload(pipeline)
        payload["latest"] = latest
        return payload
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
async def start_pipeline(
    repo_id: int,
    branch: str = "main",
    variables: Optional[dict[str, str]] = None,
) -> dict:
    """Compatibility alias for the Go `start_pipeline` tool."""
    return await create_pipeline(repo_id=repo_id, branch=branch, variables=variables)


@mcp.tool()
async def stop_pipeline(repo_id: int, pipeline_number: int) -> dict:
    """Compatibility alias for the Go `stop_pipeline` tool."""
    return await cancel_pipeline(repo_id=repo_id, pipeline_number=pipeline_number)


@mcp.tool()
async def get_repository(
    repo_id: Optional[int] = None,
    owner: Optional[str] = None,
    name: Optional[str] = None,
) -> dict:
    """Compatibility alias for the Go `get_repository` tool.

    Supports lookup by numeric `repo_id` or by `owner` + `name`.
    """
    try:
        client = _get_client()
        if repo_id is not None:
            repo = await client.get_repo(repo_id)
        elif owner and name:
            repo = await client.lookup_repo(owner, name)
        else:
            return {"error": "Provide repo_id or owner+name"}

        return {
            "id": repo.get("id"),
            "full_name": repo.get("full_name", f"{repo.get('owner', '?')}/{repo.get('name', '?')}"),
            "active": repo.get("active", False),
            "default_branch": repo.get("default_branch", "main"),
        }
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
async def list_repositories() -> dict:
    """Compatibility alias for the Go `list_repositories` tool."""
    return await list_repos()


@mcp.tool()
async def get_logs(
    repo_id: int,
    pipeline_number: int,
    step_id: int,
    format: str = "text",
    lines: Optional[int] = None,
    tail: bool = True,
) -> dict:
    """Compatibility alias for the Go `get_logs` tool.

    Args:
        repo_id: Numeric repo ID.
        pipeline_number: Pipeline number.
        step_id: Workflow step ID.
        format: `text` (default) or `list`.
        lines: Optional line cap.
        tail: If line cap is set, return last N lines when true, else first N.
    """
    try:
        base = await get_pipeline_logs(repo_id=repo_id, pipeline_number=pipeline_number, step_id=step_id)
        if "error" in base:
            return base

        log_text = base.get("log", "")
        parts = log_text.splitlines()
        total_lines = len(parts)

        if lines is not None and lines > 0 and total_lines > lines:
            parts = parts[-lines:] if tail else parts[:lines]

        if format.lower() == "list":
            log_value: Any = parts
        else:
            log_value = "\n".join(parts)
            if log_text.endswith("\n") and log_value:
                log_value += "\n"

        return {
            "pipeline_number": pipeline_number,
            "step_id": step_id,
            "format": format,
            "tail": tail,
            "line_count": len(parts),
            "total_lines": total_lines,
            "log": log_value,
        }
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
async def lint_config(config: Optional[str] = None) -> dict:
    """Compatibility shim for Go `lint_config`.

    If `config` is omitted, attempts to locate `.woodpecker.yml` in common
    repository paths.
    """
    raw = ""
    source = "inline"
    if config is not None:
        raw = config
    else:
        for candidate in _default_config_candidates():
            if candidate.exists():
                raw = candidate.read_text(encoding="utf-8")
                source = str(candidate)
                break

    if not raw.strip():
        return {
            "ok": False,
            "source": source,
            "errors": ["No config content provided and no .woodpecker.yml found."],
            "warnings": [],
        }

    errors: list[str] = []
    warnings: list[str] = []

    try:
        import yaml  # type: ignore[import-not-found]

        parsed = yaml.safe_load(raw)
        if not isinstance(parsed, dict):
            errors.append("Config is not a YAML mapping.")
        else:
            if "steps" not in parsed:
                errors.append("Missing top-level 'steps' key.")
            elif not isinstance(parsed["steps"], dict) or not parsed["steps"]:
                errors.append("'steps' must be a non-empty mapping.")
            if "when" not in parsed:
                warnings.append("No top-level 'when' condition set.")
    except Exception:
        # Minimal fallback when YAML parser is unavailable.
        stripped = raw.strip()
        if not stripped:
            errors.append("Config is empty.")
        if "steps:" not in raw:
            errors.append("Missing 'steps:' block.")
        if "when:" not in raw:
            warnings.append("No 'when:' block found.")

    return {
        "ok": not errors,
        "source": source,
        "errors": errors,
        "warnings": warnings,
    }


def main():
    """Main entry point for the MCP server."""
    parser = argparse.ArgumentParser(description="MCP Woodpecker CI Server")
    parser.add_argument("--stdio", action="store_true", help="Run in stdio transport mode")
    args = parser.parse_args()

    logger.info(f"Starting {Config.SERVER_NAME} v{Config.SERVER_VERSION}")

    if args.stdio:
        logger.info("Transport: stdio")
        mcp.run(transport="stdio")
    else:
        logger.info(f"Transport: SSE on {Config.SERVER_HOST}:{Config.SERVER_PORT}")
        mcp.run(
            transport="sse",
            host=Config.SERVER_HOST,
            port=Config.SERVER_PORT,
        )


if __name__ == "__main__":
    main()
