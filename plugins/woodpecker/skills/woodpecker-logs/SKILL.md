---
name: "woodpecker-logs"
description: "Fetch and safely decode a Woodpecker pipeline step log"
---

# Woodpecker Step Logs

Use this skill after `$woodpecker-status` identifies a repository, pipeline
number, and step ID. Woodpecker API log payloads are base64 encoded.

1. Confirm the exact `owner/repo`, pipeline number, and step ID. Do not restart
   or alter a pipeline in this read-only workflow.
2. Fetch and decode through `$secrets-run`:

```bash
$secrets-run -- sh -c '
  set +x
  curl --fail-with-body --silent --show-error \
    -H "Authorization: Bearer $WOODPECKER_TOKEN" \
    "$WOODPECKER_SERVER/api/repos/$1/pipelines/$2/steps/$3/logs" \
  | jq -r ".data" | base64 --decode
' sh "owner/repo" "42" "99"
```

3. Before reporting, redact credential-shaped values with the installed
   secrets masking guard. Summarize the failing command and step; include only
   the small relevant excerpt when it contains no secret. Never print the token
   or raw environment values.
4. If the API returns no `data` field, report the HTTP status and stop rather
   than interpreting a potentially different response as a log.
