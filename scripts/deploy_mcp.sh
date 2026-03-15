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
EOF
}

mode="deploy"
profile_spec="${PROFILE:-core}"
max_attempts="${MAX_ATTEMPTS:-10}"
sleep_seconds="${SLEEP_SECONDS:-1}"
sidecar_grace_seconds="${SIDECAR_GRACE_SECONDS:-3}"
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

log() {
    printf '[deploy_mcp] %s\n' "$*"
}

run_compose() {
    # shellcheck disable=SC2086
    docker compose $compose_args "$@"
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

if [ "$skip_smoke" -ne 1 ]; then
    command -v make >/dev/null 2>&1 || {
        echo "ERROR: make is required for deploy_mcp.sh when smoke checks are enabled" >&2
        exit 1
    }
fi

log "Deploying MCP services from repo-owned entrypoint"
docker compose version
run_compose up -d --build --wait
run_compose ps
assert_sidecars_running

if [ "$skip_smoke" -ne 1 ]; then
    attempt=1
    while :; do
        if make mcp-smoke PROFILE="$profile_spec"; then
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
