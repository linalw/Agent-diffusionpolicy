#!/bin/bash
# P30-A lift pair, re-run with distinct log names (the 04/05 files were
# overwritten by a concurrent lane whose driver dropped its env args, so those
# names are no longer trustworthy for A4/A5). Same env pair, via accept.sh so
# the motion gate runs.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
run_accept() {
    local name=$1; shift
    echo "[p30a2] START $(date +%H:%M:%S) $name"
    RUN_LIMIT=1800 scripts/154_claim_run.sh "logs/p30a/${name}_driver.log" \
        ACCEPT_LOG="logs/p30a/${name}.log" SKIP_SELFCHECK=1 \
        "$@" scripts/accept.sh > /dev/null 2>&1
    echo "[p30a2] exit=$? $(date +%H:%M:%S) $name"
    return 0
}
run_accept 06_lift040_rails_both FRUIT_OPENARM_TRANSFER_LIFT=0.04
run_accept 07_lift040_rails_outer FRUIT_OUTPUT_RAILS=outer FRUIT_OPENARM_TRANSFER_LIFT=0.04
echo "[p30a2] DONE $(date +%H:%M:%S)"
