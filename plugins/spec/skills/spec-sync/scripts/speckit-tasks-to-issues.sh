#!/usr/bin/env bash
#
# Convert official spec-kit tasks.md entries to label-free GitHub issues using
# gh. This is CPP's approved Option-B sync: no GitHub MCP dependency and no
# label adapter.
#
# Usage: speckit-tasks-to-issues.sh [--dry-run] [--tasks PATH] [--repo OWNER/REPO]
set -euo pipefail

DRY_RUN=0
TASKS=""
REPO=""

usage() {
    cat <<'EOF'
Usage: speckit-tasks-to-issues.sh [--dry-run] [--tasks PATH] [--repo OWNER/REPO]

Create one label-free GitHub issue for each `- [ ] TNNN: description` task.

Options:
  --dry-run     Print proposed issues without creating them.
  --tasks PATH  Read this tasks.md instead of auto-detecting one spec.
  --repo REPO   Target this GitHub repository instead of origin.
  -h, --help    Show this help.
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1; shift ;;
        --tasks) TASKS="${2:?--tasks needs a path}"; shift 2 ;;
        --repo) REPO="${2:?--repo needs OWNER/REPO}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

command -v gh >/dev/null 2>&1 || { echo "ERROR: gh CLI not found." >&2; exit 1; }

REMOTE_URL="$(git config --get remote.origin.url 2>/dev/null || true)"
if [ -z "$REMOTE_URL" ]; then
    echo "ERROR: no git remote named origin; refusing to create issues." >&2
    exit 1
fi
case "$REMOTE_URL" in
    *github.com[:/]*) ;;
    *) echo "ERROR: origin is not a GitHub remote; refusing to create issues." >&2; exit 1 ;;
esac

if [ -z "$TASKS" ]; then
    mapfile -t candidates < <(find .specify/specs -maxdepth 2 -name tasks.md -type f 2>/dev/null | sort)
    case "${#candidates[@]}" in
        0) echo "ERROR: no .specify/specs/*/tasks.md found; pass --tasks PATH." >&2; exit 1 ;;
        1) TASKS="${candidates[0]}" ;;
        *)
            echo "ERROR: multiple tasks.md files found; pass --tasks PATH:" >&2
            printf '  %s\n' "${candidates[@]}" >&2
            exit 1
            ;;
    esac
fi
[ -f "$TASKS" ] || { echo "ERROR: tasks file not found: $TASKS" >&2; exit 1; }

GH_REPO_ARGS=()
[ -n "$REPO" ] && GH_REPO_ARGS=(--repo "$REPO")

declare -A existing
while IFS= read -r title; do
    if [[ "$title" =~ (^|[^[:alnum:]])(T[0-9]{3})([^0-9]|$) ]]; then
        existing["${BASH_REMATCH[2]}"]=1
    fi
done < <(gh issue list "${GH_REPO_ARGS[@]}" --state all --limit 1000 --json title --jq '.[].title')

echo "Tasks file: $TASKS"
echo "Mode: $([ "$DRY_RUN" -eq 1 ] && echo 'dry run' || echo 'create issues')"

created=0
skipped=0
while IFS= read -r line; do
    [[ "$line" =~ ^-\ \[[\ xX]\] ]] || continue
    task="${line#*] }"
    task="$(printf '%s' "$task" | sed -E 's/\[P\]//g; s/\[US[0-9]+\]//g; s/^[[:space:]]+//; s/[[:space:]]+$//')"
    [[ "$task" =~ ^(T[0-9]{3})[:[:space:]]+(.*)$ ]] || continue
    task_id="${BASH_REMATCH[1]}"
    title="${task_id}: ${BASH_REMATCH[2]}"

    if [ -n "${existing[$task_id]:-}" ]; then
        echo "skip  $task_id (issue already exists)"
        skipped=$((skipped + 1))
        continue
    fi

    if [ "$DRY_RUN" -eq 1 ]; then
        echo "would create: $title"
    else
        url="$(gh issue create "${GH_REPO_ARGS[@]}" --title "$title" --body "Auto-created from $TASKS ($task_id) by Codex Power Pack spec-sync.")"
        echo "create $task_id -> $url"
    fi
    existing["$task_id"]=1
    created=$((created + 1))
done < "$TASKS"

echo "---"
if [ "$DRY_RUN" -eq 1 ]; then
    echo "Done. $created to create, $skipped skipped (already exist)."
else
    echo "Done. $created created, $skipped skipped (already exist)."
fi
