#!/bin/sh
# NEGATIVE-CONTROL FIXTURE for issue #264 - the known-GOOD half.
#
# Same path as the known-bad case, carrying the value the allowlist DOES
# declare. Without this, a scanner wedged at "report everything" would pass the
# known-bad case on its own and score as discriminating.
AWS_KEY="AKIAIOSFODNN7EXAMPLE"
