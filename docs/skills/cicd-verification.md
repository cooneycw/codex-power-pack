# CI/CD & Verification

Build system detection, health checks, smoke tests, pipeline generation, container scaffolding, and the verification loop.

## The Verification Loop

```
code → lint/test → deploy → health check → smoke test → report
```

This is the core pattern: every deployment should be **verified** before it's considered complete. The `/flow` commands orchestrate this automatically when configured.

## Framework Detection

The CI/CD system auto-detects your project's framework and package manager:

| Framework | Package Managers | Detection |
|-----------|-----------------|-----------|
| Python | uv, pip | `pyproject.toml`, `setup.py`, `requirements.txt` |
| Node.js | npm, yarn | `package.json` + lock files |
| Go | go | `go.mod` |
| Rust | cargo | `Cargo.toml` |
| Multi-language | any | Multiple indicators |

Run `/cicd:init` to detect and generate a Makefile from templates.

## Makefile Conventions

### Standard Targets

| Target | Required | Used By | Purpose |
|--------|----------|---------|---------|
| `lint` | Yes | `/flow:finish` | Code linting |
| `test` | Yes | `/flow:finish` | Test suite |
| `format` | No | Manual/IDE | Code formatting |
| `typecheck` | No | `/cicd:check` | Type checking |
| `build` | No | Build step | Build artifacts |
| `deploy` | No | `/flow:deploy` | Production deploy |
| `clean` | No | Manual | Remove artifacts |
| `verify` | No | Pre-deploy | lint + test + typecheck |

### Best Practices

1. **Always use `uv run`** for Python commands (environment isolation)
2. **Declare `.PHONY`** for all non-file targets
3. **Add dependencies** - `deploy` should depend on `test` and `lint`
4. **Use `@` prefix** on informational `echo` commands to reduce noise
5. **Keep targets idempotent** - safe to run multiple times

### Example Makefile

```makefile
.PHONY: lint test format deploy clean verify

lint:
	uv run ruff check .

test:
	uv run pytest

format:
	uv run ruff format .

deploy: verify
	@echo "Deploying..."
	# your deploy commands here

verify: lint test

clean:
	rm -rf .pytest_cache __pycache__ dist/
```

## Health Check Configuration

Configure in `.codex/cicd.yml`:

```yaml
health:
  endpoints:
    - url: http://localhost:8000/health
      name: API Server
      expected_status: 200
      timeout: 5
    - url: http://localhost:3000
      name: Frontend
      expected_status: 200
  processes:
    - name: uvicorn
      port: 8000
    - name: node
      port: 3000
```

### Health Check Types

| Type | What It Checks | How |
|------|---------------|-----|
| **Endpoint** | HTTP response | `curl` with status code + timeout |
| **Process** | Service running | `ss`/`lsof` for port listening |

### Best Practices

- Check **both** endpoints and processes for critical services
- Set reasonable timeouts (5s default, 30s max)
- Use `/health` endpoints that verify dependencies (DB, cache)
- Run health checks **after** deploy, not during

## Smoke Test Configuration

```yaml
smoke_tests:
  - name: API responds
    command: "curl -sf http://localhost:8000/health"
    expected_exit: 0
  - name: CLI version
    command: "python -m myapp --version"
    expected_output: "v\\d+\\.\\d+"
  - name: Database connected
    command: "python -c 'from myapp.db import check; check()'"
    expected_exit: 0
```

### Smoke vs Health

| Aspect | Health Check | Smoke Test |
|--------|-------------|------------|
| Speed | Fast (< 5s each) | Slower (may do I/O) |
| Scope | Is it running? | Does it work? |
| When | Continuous / post-deploy | Post-deploy only |
| Failure | Service down | Feature broken |

## CI/CD Pipeline Patterns

### Woodpecker CI

Generated via `/cicd:pipeline` using templates in `templates/workflows/`:

```yaml
# .woodpecker.yml (generated)
# Deploy secrets are resolved from AWS Secrets Manager.
when:
  branch: [main]
  event: [push, pull_request]

steps:
  - name: lint
    image: python:3.12
    commands:
      - pip install uv
      - uv sync
      - make lint

  - name: test
    image: python:3.12
    commands:
      - pip install uv
      - uv sync
      - make test

  - name: aws-secretsmanager-preflight
    image: amazon/aws-cli:2
    commands:
      - aws sts get-caller-identity >/dev/null
      - aws secretsmanager describe-secret --region "${AWS_REGION:-us-east-1}" --secret-id "codex-power-pack/codex-power-pack" >/dev/null
    when:
      branch: main
      event: push

  - name: deploy
    image: python:3.12
    environment:
      CPP_SECRETS_PROVIDER: aws-secrets-manager
      CPP_AWS_SECRET_ID: codex-power-pack/codex-power-pack
      AWS_REGION: us-east-1
    commands:
      - pip install uv
      - uv sync
      - make deploy
```

Declare the AWS bundle explicitly in `.codex/cicd.yml` when `main` includes
`deploy`:

```yaml
pipeline:
  provider: woodpecker
  branches:
    main: [lint, test, typecheck, build, deploy]
  aws_secrets:
    provider: aws-secrets-manager
    project_id: codex-power-pack
    region: us-east-1
  secrets_needed: [DEPLOY_KEY]
```

`secrets_needed` now documents the keys expected inside the AWS Secrets Manager
bundle. It is no longer the preferred source for raw Woodpecker secret
injection.

For dockerized MCP services in this repo, the runtime path is tighter: the
containerized servers consume secrets through a local AWS Secrets Manager agent
sidecar on `127.0.0.1:2773`, and the sidecar owns the AWS credentials and
session token. The sidecar may authenticate from direct `AWS_*` environment
variables or the host's shared `~/.aws` credentials/config via `AWS_PROFILE`.
The contract tests for that runtime boundary live in
`tests/test_mcp_secret_contract.py`.

### Template Selection

Templates match detected framework:
- `woodpecker-python.yml` - Python
- `woodpecker-node.yml` - Node.js
- `woodpecker-go.yml` - Go
- `woodpecker-rust.yml` - Rust
- `woodpecker-powershell.yml` - PowerShell

## Container Best Practices

Generated via `/cicd:container` using templates in `templates/containers/`:

### Dockerfile Patterns

1. **Multi-stage builds** - separate build and runtime stages
2. **Non-root user** - always run as non-root in production
3. **Layer caching** - copy dependency files first, then source
4. **Health checks** - include `HEALTHCHECK` instruction
5. **Minimal base** - use slim/alpine variants

### docker-compose Patterns

1. **Named volumes** for persistent data
2. **Health checks** with retries and intervals
3. **Dependency ordering** with `depends_on` + `condition: service_healthy`
4. **Deploy secrets** - require AWS Secrets Manager for shared runtime and deploy-time secrets

## Commands Reference

| Command | Purpose |
|---------|---------|
| `/cicd:init` | Detect framework, generate Makefile and cicd.yml |
| `/cicd:check` | Validate Makefile against CPP standards |
| `/cicd:health` | Run health checks (endpoints + processes) |
| `/cicd:smoke` | Run smoke tests from cicd.yml |
| `/cicd:container` | Generate Dockerfile and docker-compose.yml |
| `/cicd:help` | Overview of CI/CD commands |

## Integration with /flow

| Flow Command | CI/CD Integration |
|-------------|-------------------|
| `/flow:finish` | Runs `make lint` + `make test` as quality gates |
| `/flow:deploy` | Runs `make deploy`, then post-deploy health + smoke |
| `/flow:auto` | Full lifecycle including deploy verification |
| `/flow:doctor` | Reports Makefile target availability |

## Related

- `/self-improvement:deployment` - Analyze deploy failures, improve Makefile
- `/flow:doctor` - Forward-looking health check of workflow environment
- `/security:scan` - Security-focused analysis (complementary)
