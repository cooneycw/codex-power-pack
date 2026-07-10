---
name: "woodpecker-status"
description: "List recent Woodpecker pipelines without exposing credentials"
---

# Woodpecker Pipeline Status

Use this skill to inspect recent pipeline state for an explicit repository.

1. Require a repository slug (`owner/repo`) and confirm that
   `WOODPECKER_SERVER` is configured. Do not guess either value.
2. Run the request through `$secrets-run` so `WOODPECKER_TOKEN` is injected
   only into the subprocess. The command must not enable shell tracing:

```bash
$secrets-run -- sh -c '
  set +x
  curl --fail-with-body --silent --show-error \
    -H "Authorization: Bearer $WOODPECKER_TOKEN" \
    "$WOODPECKER_SERVER/api/repos/$1/pipelines?per_page=20" \
  | jq -r ".[] | [.number, .status, .event, .branch, .created_at] | @tsv"
' sh "owner/repo"
```

3. Report pipeline number, status, event, branch, and timestamp. Never print
   the Authorization header, token, or unredacted environment.
4. On connection or authorization failure, show only the HTTP status/error and
   advise that the host-managed Woodpecker endpoint or read token needs review.
