---
name: "woodpecker-restart"
description: "Restart one confirmed Woodpecker pipeline through the API"
---

# Restart a Woodpecker Pipeline

This is a write operation. Use it only after a failure has been identified via
`$woodpecker-status` and `$woodpecker-logs`.

1. Require the exact repository slug and pipeline number, and state the
   pipeline that will be restarted.
2. Ask for explicit confirmation immediately before the request. Do not treat
   a request to inspect status or logs as confirmation.
3. Run the POST request through `$secrets-run`; it keeps `WOODPECKER_TOKEN` out
   of the parent process and command arguments:

```bash
$secrets-run -- sh -c '
  set +x
  curl --fail-with-body --silent --show-error --request POST \
    -H "Authorization: Bearer $WOODPECKER_TOKEN" \
    "$WOODPECKER_SERVER/api/repos/$1/pipelines/$2/restart" \
  | jq -r "[.number, .status, .created_at] | @tsv"
' sh "owner/repo" "42"
```

4. Report the restarted pipeline number and returned state. Never print the
   token, Authorization header, or full response if it contains secret-like
   content. A failed request is an error report, not a retry loop.
