#!/bin/sh
# NEGATIVE-CONTROL FIXTURE for issue #264. Not a real credential, and not
# reachable from any code path.
#
# The PATH matters as much as the value. Until #264 the allowlist carried
# `scripts/secrets-mask\.sh` as a whole-file entry, so ANY secret in a file at
# this path was suppressed - including one nobody had reviewed. This fixture is
# a secret at that path which is NOT in the allowlist, and the current config
# must report it.
AWS_KEY="AKIA6HD2WQPXKF9TVJ4Z"
