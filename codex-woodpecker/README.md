# MCP Woodpecker CI

Woodpecker CI pipeline management and monitoring MCP server for Codex.

## Provenance and Strategy

`codex-woodpecker` is a Python reimplementation of the upstream Go binary
[`woodpecker-mcp`](https://github.com/denysvitali/woodpecker-ci-mcp). This
repository keeps the Python variant because it integrates with Codex Power Pack
runtime conventions (dotenv loading, AWS Secrets Manager fallback, repo-local
packaging, and test/lint workflows).

If you prefer to run the upstream Go binary directly, Codex supports that:

```toml
[mcp_servers.codex-woodpecker]
command = "/home/$USER/go/bin/woodpecker-mcp"
args = ["serve"]
```

`scripts/setup-go-binary.sh` bootstraps the Go binary and writes the upstream
`~/.config/woodpecker-mcp/config.yaml` format.

## Tools

| Tool | Description |
|------|-------------|
| `health_check` | Verify connectivity to Woodpecker CI |
| `list_repos` | List all repos the API token can access |
| `lookup_repo` | Find a repo by owner/name |
| `list_pipelines` | List recent pipelines for a repo |
| `get_pipeline` | Get pipeline details with workflow steps |
| `create_pipeline` | Trigger a new pipeline on a branch |
| `cancel_pipeline` | Cancel a running pipeline |
| `approve_pipeline` | Approve a blocked pipeline |
| `get_pipeline_logs` | Get decoded logs for a pipeline step |

Go-compatibility aliases are also exposed for migration parity:

- `get_pipeline_status` (supports `latest`)
- `start_pipeline`
- `stop_pipeline`
- `get_repository`
- `list_repositories`
- `get_logs` (supports `format`, `lines`, `tail`)
- `lint_config`

## Configuration

The server resolves credentials in this order:

1. **Environment variables** (direct):
   - `WOODPECKER_URL` - Woodpecker server URL (e.g. `https://woodpecker.example.com`)
   - `WOODPECKER_API_TOKEN` - API token from Woodpecker UI

2. **AWS Secrets Manager** (auto-fetch, Codex Power Pack default):
   - `AWS_SECRET_NAME` - Secret name (default: `codex-power-pack`)
   - `AWS_REGION` - Region (default: `us-east-1`)
   - Reads `WOODPECKER_HOST` and `WOODPECKER_API_TOKEN` keys from the secret

Upstream Go defaults differ:

- Go binary default credentials: `~/.config/woodpecker-mcp/config.yaml`
- Python server default credentials: env vars or AWS Secrets Manager

Recommended setup:

- Use AWS Secrets Manager with `AWS_SECRET_NAME=codex-power-pack`
- Avoid mounting or injecting raw `WOODPECKER_*` credentials into the container environment unless you intentionally want a local override

## Running

### Docker (recommended)

```bash
# From codex-power-pack root:
make docker-up PROFILE=legacy-cicd
```

Note: the Woodpecker Docker container is intentionally in a legacy profile
because Codex/Claude primary usage is stdio transport.

### Native

```bash
./start-server.sh
# Or with stdio transport:
./start-server.sh --stdio
```

## Port

- Default: `9103`
- Override: `MCP_SERVER_PORT=9103`
- SSE endpoint: `http://127.0.0.1:9103/sse`
- Health check: `http://127.0.0.1:9103/`
