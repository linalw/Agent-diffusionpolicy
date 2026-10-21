#!/bin/bash
# P30-A A4 retry (the first clean re-run died at warm-up with an RTX
# "Out of resource descriptors!" wedge - the shared GPU; 06's log is truncated).
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
echo "[p30a3] START $(date +%H:%M:%S) 06b_lift040_rails_both"
RUN_LIMIT=1800 scripts/154_claim_run.sh logs/p30a/06b_lift040_rails_both_driver.log \
    ACCEPT_LOG=logs/p30a/06b_lift040_rails_both.log SKIP_SELFCHECK=1 \
    FRUIT_OPENARM_TRANSFER_LIFT=0.04 scripts/accept.sh > /dev/null 2>&1
echo "[p30a3] exit=$? $(date +%H:%M:%S) 06b"
