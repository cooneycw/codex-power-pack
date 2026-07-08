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


def test_host_managed_doc_records_future_cxpp_init_pointer_scope() -> None:
    # The cxpp:init pointer scope is CxPP-native governance, so it lives in
    # HOST_MANAGED.md, not in a generated (pulled-from-CPP) project skill. The
    # former hand-port `.codex/prompts/project/init.md` carrier was deleted with
    # the fork (codex-power-pack#75).
    text = (ROOT / "docs" / "HOST_MANAGED.md").read_text()

    assert "cxpp:init" in text
    assert "templates/config.toml.example" in text
    assert "not own external MCP server lifecycle" in text
