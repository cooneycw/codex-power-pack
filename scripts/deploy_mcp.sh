#!/bin/sh
# Canonical repo-owned entrypoint for MCP deployments.

set -eu

usage() {
    cat <<'EOF'
Usage: deploy_mcp.sh [--check] [--profiles "core browser"] [--profile NAME]
                     [--skip-smoke] [--max-attempts N] [--sleep-seconds N]

Modes:
  default          Run the MCP deployment from the current repo checkout
  --check          Validate the deploy entrypoint without changing containers

Environment:
  PROFILE          Space-delimited profile list (default: "core")
  MAX_ATTEMPTS     Retry count for mcp-smoke (default: 10)
  SLEEP_SECONDS    Delay between smoke retries (default: 1)
  MCP_SMOKE_MODE   host|docker|auto (default: "auto")
EOF
}

mode="deploy"
profile_spec="${PROFILE:-core}"
max_attempts="${MAX_ATTEMPTS:-10}"
sleep_seconds="${SLEEP_SECONDS:-1}"
sidecar_grace_seconds="${SIDECAR_GRACE_SECONDS:-3}"
smoke_mode="${MCP_SMOKE_MODE:-auto}"
skip_smoke=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --check)
            mode="check"
            shift
            ;;
        --profiles)
            shift
            [ "$#" -gt 0 ] || {
                echo "ERROR: --profiles requires a value" >&2
                exit 1
            }
            profile_spec="$1"
            shift
            ;;
        --profile)
            shift
            [ "$#" -gt 0 ] || {
                echo "ERROR: --profile requires a value" >&2
                exit 1
            }
            if [ -n "$profile_spec" ]; then
                profile_spec="$profile_spec $1"
            else
                profile_spec="$1"
            fi
            shift
            ;;
        --skip-smoke)
            skip_smoke=1
            shift
            ;;
        --max-attempts)
            shift
            [ "$#" -gt 0 ] || {
                echo "ERROR: --max-attempts requires a value" >&2
                exit 1
            }
            max_attempts="$1"
            shift
            ;;
        --sleep-seconds)
            shift
            [ "$#" -gt 0 ] || {
                echo "ERROR: --sleep-seconds requires a value" >&2
                exit 1
            }
            sleep_seconds="$1"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: Unknown argument: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$repo_root" ]; then
    script_path="$0"
    case "$script_path" in
        */*) script_dir_path="${script_path%/*}" ;;
        *) script_dir_path="." ;;
    esac
    script_dir="$(CDPATH= cd -- "$script_dir_path" && pwd)"
    candidate_root="${script_dir%/*}"
    if [ -f "$candidate_root/docker-compose.yml" ]; then
        repo_root="$candidate_root"
    fi
fi
[ -n "$repo_root" ] || {
    echo "ERROR: deploy_mcp.sh must run from inside a git checkout" >&2
    exit 1
}

cd "$repo_root"
[ -f "docker-compose.yml" ] || {
    echo "ERROR: docker-compose.yml not found in $repo_root" >&2
    exit 1
}

command -v docker >/dev/null 2>&1 || {
    echo "ERROR: docker is required for deploy_mcp.sh" >&2
    exit 1
}

compose_args=""
for profile in $profile_spec; do
    compose_args="$compose_args --profile $profile"
done

[ -n "$(printf '%s' "$compose_args" | tr -d ' ')" ] || {
    echo "ERROR: no docker compose profiles configured" >&2
    exit 1
}

case "$smoke_mode" in
    auto|host|docker) ;;
    *)
        echo "ERROR: MCP_SMOKE_MODE must be one of: auto, host, docker" >&2
        exit 1
        ;;
esac

log() {
    printf '[deploy_mcp] %s\n' "$*"
}

run_compose() {
    # shellcheck disable=SC2086
    docker compose $compose_args "$@"
}

is_ci_runtime() {
    [ -n "${CI:-}" ] || [ -n "${CI_WORKSPACE:-}" ] || [ -n "${CI_PIPELINE_NUMBER:-}" ] || [ -n "${WOODPECKER_REPO:-}" ]
}

use_docker_smoke() {
    case "$smoke_mode" in
        docker) return 0 ;;
        host) return 1 ;;
        auto)
            is_ci_runtime
            return $?
            ;;
    esac
    return 1
}

run_host_smoke() {
    command -v make >/dev/null 2>&1 || {
        echo "ERROR: make is required for host mcp-smoke checks" >&2
        exit 1
    }
    make mcp-smoke PROFILE="$profile_spec"
}

smoke_probe_container() {
    case " $profile_spec " in
        *" core "*) printf '%s\n' "codex-second-opinion" ;;
        *" browser "*) printf '%s\n' "codex-playwright" ;;
        *" legacy-cicd "*|*" cicd "*) printf '%s\n' "codex-woodpecker" ;;
        *)
            echo "ERROR: no running probe container available for profiles: $profile_spec" >&2
            exit 1
            ;;
    esac
}

run_docker_smoke() {
    probe_container="$(smoke_probe_container)"
    docker exec -i \
        -e MCP_SMOKE_PROFILES="$profile_spec" \
        "$probe_container" \
        python - <<'PY'
import json
import os
import socket
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

DEFAULT_PROTOCOL_VERSION = "2024-11-05"
PROFILE_ALIASES = {"legacy-cicd": "cicd"}


def parse_profiles(raw):
    if not raw:
        return {"core"}
    normalized = raw.replace(",", " ")
    values = set()
    for token in normalized.split():
        token = token.strip()
        if token:
            values.add(PROFILE_ALIASES.get(token, token))
    return values or {"core"}


def selected_servers(profiles):
    servers = [
        ("codex-second-opinion", "core", "http://codex-second-opinion:9100/sse"),
        ("codex-nano-banana", "core", "http://codex-nano-banana:9102/sse"),
        ("codex-playwright", "browser", "http://codex-playwright:9101/sse"),
        ("codex-woodpecker", "cicd", "http://codex-woodpecker:9103/sse"),
    ]
    return [spec for spec in servers if spec[1] in profiles]


def read_sse_event(stream, max_lines=200):
    event_name = None
    data_lines = []
    line_count = 0
    while line_count < max_lines:
        raw = stream.readline()
        if not raw:
            return None
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        line_count += 1
        if line == "":
            if event_name is not None:
                return {"event": event_name, "data": "\n".join(data_lines)}
            event_name = None
            data_lines = []
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
            continue
        if line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].lstrip())
    return None


def probe_server(name, sse_url, timeout_seconds=8.0):
    headers = {"Accept": "text/event-stream"}
    try:
        with urlopen(Request(sse_url, headers=headers, method="GET"), timeout=timeout_seconds) as stream:
            endpoint = None
            for _ in range(30):
                event = read_sse_event(stream)
                if not event:
                    break
                if event.get("event") == "endpoint":
                    payload = (event.get("data") or "").strip()
                    endpoint = payload if payload.startswith("http") else urljoin(sse_url, payload)
                    break

            if not endpoint:
                return {"ok": False, "stage": "handshake", "target": sse_url, "error": "No endpoint event received"}

            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": DEFAULT_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "codex-power-pack", "version": "1.0"},
                },
            }

            with urlopen(
                Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST"),
                timeout=timeout_seconds,
            ):
                pass

            init_result = None
            for _ in range(60):
                event = read_sse_event(stream)
                if not event:
                    break
                data = (event.get("data") or "").strip()
                if not data:
                    continue
                try:
                    maybe_payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if maybe_payload.get("id") == 1:
                    init_result = maybe_payload
                    break

            if not init_result or "result" not in init_result:
                return {"ok": False, "stage": "handshake", "target": sse_url, "error": "Initialize response was not received"}

            server_info = (init_result.get("result", {}) or {}).get("serverInfo", {})
            return {
                "ok": True,
                "target": sse_url,
                "server_name": server_info.get("name") or name,
                "server_version": server_info.get("version") or "-",
            }
    except HTTPError as exc:
        return {"ok": False, "stage": "endpoint", "target": sse_url, "error": f"HTTP {exc.code}"}
    except (URLError, TimeoutError, socket.timeout, ConnectionError) as exc:
        return {"ok": False, "stage": "endpoint", "target": sse_url, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "stage": "handshake", "target": sse_url, "error": str(exc)}


profiles = parse_profiles(os.environ.get("MCP_SMOKE_PROFILES", "core"))
results = [probe_server(name, sse_url) for name, _, sse_url in selected_servers(profiles)]

print("MCP Smoke Results")
for result in results:
    status = "PASS" if result["ok"] else "FAIL"
    if result["ok"]:
        print(
            f"- [{status}] {result['server_name']} ({result['target']}) "
            f"server={result['server_name']} version={result['server_version']}"
        )
    else:
        print(f"- [{status}] {result['target']} stage={result['stage']} error={result['error']}")

if not all(result["ok"] for result in results):
    if any(result["stage"] == "endpoint" for result in results if not result["ok"]):
        raise SystemExit(2)
    raise SystemExit(3)
PY
}

run_smoke() {
    if use_docker_smoke; then
        run_docker_smoke
    else
        run_host_smoke
    fi
}

expected_sidecars() {
    case " $profile_spec " in
        *" core "*) printf '%s\n' "codex-second-opinion-secrets" ;;
    esac
    case " $profile_spec " in
        *" legacy-cicd "*) printf '%s\n' "codex-woodpecker-secrets" ;;
    esac
}

sidecar_status() {
    docker inspect -f '{{.State.Status}}' "$1" 2>/dev/null || printf '%s\n' "missing"
}

assert_sidecars_running() {
    sidecars="$(expected_sidecars)"
    [ -n "$sidecars" ] || return 0

    if [ "${sidecar_grace_seconds}" -gt 0 ] 2>/dev/null; then
        sleep "${sidecar_grace_seconds}"
    fi

    for sidecar in $sidecars; do
        status="$(sidecar_status "$sidecar")"
        if [ "$status" != "running" ]; then
            log "Sidecar '$sidecar' is not running (status: $status)"
            docker logs --tail 20 "$sidecar" || true
            return 3
        fi
    done
}

if [ "$mode" = "check" ]; then
    log "Validating deploy entrypoint from repo checkout: $repo_root"
    docker compose version >/dev/null
    run_compose config >/dev/null
    log "Deploy entrypoint validation passed for profiles: $profile_spec"
    exit 0
fi

log "Deploying MCP services from repo-owned entrypoint"
docker compose version
run_compose up -d --build --wait
run_compose ps
assert_sidecars_running

if [ "$skip_smoke" -ne 1 ]; then
    if use_docker_smoke; then
        log "Running mcp-smoke via docker exec inside the compose network"
    else
        log "Running mcp-smoke from the host workspace"
    fi
    attempt=1
    while :; do
        if run_smoke; then
            break
        fi

        if [ "$attempt" -ge "$max_attempts" ]; then
            echo "mcp-smoke failed after $max_attempts attempts" >&2
            exit 2
        fi

        log "mcp-smoke not ready yet (attempt $attempt/$max_attempts), retrying in ${sleep_seconds}s..."
        attempt=$((attempt + 1))
        sleep "$sleep_seconds"
    done
fi

assert_sidecars_running

docker image prune -f
log "Deploy complete."
