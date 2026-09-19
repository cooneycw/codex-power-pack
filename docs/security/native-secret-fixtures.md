# Exact native-secret fixture exceptions

The native finish scanner and gitleaks are different checks. The native scanner
examines selected source file types in the working tree; gitleaks has its own
configuration and history behavior. Passing one does not establish the other's
result. This repair is the first, partial delivery of #282.

## Contract

`make native-secret-scan` runs `scripts/native-secret-scan.py --root .` using the
actual `lib.security.modules.secrets` scanner. `make verify` includes this target,
so the CI validate step executes it too. `python3 -m lib.security gate flow_finish`
uses the same matcher and prints the examined-file and exception counts.

Only `<scan root>/.codex/security-fixtures.toml` can declare exceptions. Policies
from parent directories or nested fixtures are not inherited. Version 1 requires
exactly `version` and a `fixtures` array; each entry requires exactly:

- `path`: an exact, normalized root-relative POSIX file path; no globs, traversal,
  absolute paths, backslashes or symlink components.
- `finding_id`: one of the native secret scanner's finding types.
- `sha256`: lowercase SHA-256 of the **entire matched UTF-8 text**, not a file hash,
  line number, prefix or regex. Assignment detectors include assignment syntax.
- `reason`: a nonempty explanation of the reviewed synthetic value.

All three identity fields must match. A second occurrence of the same exact
synthetic text in that file uses the same entry and is counted again. A new token
beside it, a changed token, another finding type or the same token at another path
remains a finding. Moving or editing a fixture cannot widen its old exception.
Missing policies mean no exceptions. Malformed, unreadable, duplicate or symlinked
policies produce a critical `INVALID_FIXTURE_POLICY` finding and apply no
exceptions. Diagnostics never echo policy input or matched values.

Exceptions are a **reviewed security-policy change**, not proof that a value is
synthetic. Never auto-enroll a scan report, use path-only exclusions or change a
fixture merely to evade the scanner. The policy contains hashes, not credentials;
use the repository's masked-read command when reviewing credential-shaped files.
Deleting all exceptions restores the original findings; changing a reason cannot
affect matching. No generic `.codex/security.yml` suppressions are added. Existing
ones remain a separate user policy in the general CLI, with the invalid-policy
blocker protected as described below.

## Reviewed dispositions

The initial baseline has ten identities representing eleven matches:

| Source | Matches | Disposition |
| --- | ---: | --- |
| `tests/test_masked_read.py` | 1 | Scanner matched source-code concatenation in a masking canary, not a stored password. |
| `tests/test_gitleaks_allowlist.py` | 3 | Documentation placeholder and synthetic-token declarations already pinned by existing policy tests. |
| `tests/test_plugin_hooks.py` | 2 | Synthetic hook inputs used to prove masking and minimized capture. |
| `controls/gitleaks-allowlist-scope/control.json` | 1 | Documentation placeholder named by the existing control. |
| The two existing gitleaks historical anchors | 4 | Immutable synthetic allowlist values; original bytes preserved. |

The new control adds three literal occurrences at three exact path/type/value
identities, for **14 reviewed matches / 13 identities** in this revision. It reuses
the existing gitleaks-reviewed synthetic sentinels; no gitleaks policy changes are
needed. Repository-level exceptions name these exact control files. Each isolated
case has its own policy accepting only the first sentinel, so the second token
remains a real red input when the case is the scan root.

## Evidence and limits

The registered `native-secret-fixture-scope` control accepts the known fixture,
rejects an additional token in the same file, and rejects a deliberately mutated
path-only matcher. Its anchor is explicitly **synthetic**, not a historical
revision: it replaces only the matcher and uses the current real scanner. Its
hashed bytes are checked on every register run. This proves one property, not
all native scanner rules or all exception-validation paths. Unit and CLI tests
cover changed values, wrong IDs/paths, malformed policies, duplicates, symlinks,
empty inputs, masked diagnostics and finish-gate blocking separately.

The native command returns 0 for examined source without unexcepted findings,
1 for native findings, and 2 for invalid root/policy or no source examined. Its
output states the actual examined population and visible exception count. The
existing general finish gate's default severity policy is unchanged: critical
findings block; high findings warn. Legacy `.codex/security.yml` suppressions
still affect ordinary findings in the general security CLI, but not the dedicated
native command. They cannot suppress `INVALID_FIXTURE_POLICY`. This preserves
existing user policy without permitting it to hide a malformed exact-exception
policy. Counts report pre-legacy-suppression native observations, not the general
gate's final verdict. A native scan is not an assertion that history,
excluded file types or every other security module was examined.

For the broader register, gitleaks **8.18.4** remains the measured working version
used by `.woodpecker.yml`. On 2026-09-19 the unchanged isolated red input was
detected by 8.18.4; 8.30.1 reported 529 bytes examined and no detection. This
repair does not establish that discrepancy's cause or certify 8.30.1. Put the
verified 8.18.4 binary on PATH before `make verify`; it does not replace the
host's installed version. Reproducible provisioning, unsupported-version early
diagnostics, focused-control routing, binary/fixture checks and per-test timeouts
remain owed under #282's second delivery.

#274 still owns configuration/history blind spots. The existing scanner's
excluded names and extensions are unchanged here. #281 owns subprocess-tree
timeouts, #256 runtime routing, and #278/#286 the dependency audit/upgrades. This
repair neither suppresses dependency advisories nor certifies those workstreams.
