#!/bin/bash
# P30-A lift pair: at a 40 mm-lower transfer the *rail* is the binding constraint.
#
#   logs/p30a/run_lift.sh
#
# Geometry (logs/p30a/RAILS_DESIGN.md section 2b): at
# FRUIT_OPENARM_TRANSFER_LIFT=0.04 the payload's lowest point is ~1.380 m, i.e.
# 5 mm BELOW the output rail's top (1.385) and 30 mm above the slab top (1.350).
# So this pair is the one place where removing the inner rail is the difference
# between a rail contact and a clean crossing - and the only place a rail removal
# can *buy* something without touching tasks.py's default.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

run_accept() {
    local name=$1; shift
    echo "[p30a] START $(date +%H:%M:%S) $name (acceptance)"
    RUN_LIMIT=${RUN_LIMIT:-1800} scripts/154_claim_run.sh "logs/p30a/${name}_driver.log" \
        ACCEPT_LOG="logs/p30a/${name}.log" SKIP_SELFCHECK=1 \
        "$@" scripts/accept.sh > /dev/null 2>&1
    echo "[p30a] exit=$? $(date +%H:%M:%S) $name"
    return 0
}

run_accept 04_accept_lift040 FRUIT_OPENARM_TRANSFER_LIFT=0.04
run_accept 05_accept_rails_outer_lift040 FRUIT_OUTPUT_RAILS=outer FRUIT_OPENARM_TRANSFER_LIFT=0.04
echo "[p30a] DONE $(date +%H:%M:%S)"
