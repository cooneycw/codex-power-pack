from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_config_template_registers_host_managed_mcp_servers() -> None:
    text = (ROOT / "templates" / "config.toml.example").read_text()

    assert "[mcp_servers.second-opinion]" in text
    assert 'url = "http://127.0.0.1:8080/mcp"' in text
    assert "[mcp_servers.playwright]" in text
    assert 'command = "npx"' in text
    assert 'args = ["-y", "@playwright/mcp@latest"]' in text


def test_host_managed_doc_records_boundary_and_health_checks() -> None:
    text = (ROOT / "docs" / "HOST_MANAGED.md").read_text()

    for needle in [
        "mcp-second-opinion",
        "@playwright/mcp",
        "curl -sf http://127.0.0.1:8080/readyz",
        "codex mcp add second-opinion --url http://127.0.0.1:8080/mcp",
        "No server lifecycle management exists in this repo",
    ]:
        assert needle in text


def test_project_init_records_future_cxpp_init_pointer_scope() -> None:
    text = (ROOT / ".codex" / "prompts" / "project" / "init.md").read_text()

    assert "cxpp:init" in text
    assert "templates/config.toml.example" in text
    assert "does not start, stop, or deploy MCP servers" in text
