#!/bin/bash
# P30-A-fix: the viable-lift pair (A4/A5) the broken chain never ran.
cd "$(dirname "$0")/../.." || exit 1
run() { local log=$1; shift; echo "[p30a2] START $(date +%H:%M:%S) $log"
    RUN_LIMIT=3600 scripts/154_claim_run.sh "$log" HEADLESS=1 ATTEMPTS=10 FRUIT_MOTION_REPORT=1 \
        scripts/run.sh scripts/20_pick_place.py > "${log%.log}_driver.log" 2>&1
    echo "[p30a2] exit=$? $(date +%H:%M:%S) $log"; }
run logs/p30a/04_accept_lift040.log FRUIT_OPENARM_TRANSFER_LIFT=0.04
run logs/p30a/05_accept_rails_outer_lift040.log FRUIT_OPENARM_TRANSFER_LIFT=0.04 FRUIT_OUTPUT_RAILS=outer
echo "[p30a2] DONE $(date +%H:%M:%S)"
