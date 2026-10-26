#!/usr/bin/env bash
# P43 phase 2, batch 2: the treatment arm's own `[bed-sel]` census.
#
#   bash logs/p43/p2/run_batch2.sh > logs/p43/p2/batch2_driver.log 2>&1
#
# Why: the L1 mechanism endpoint ("chosen-along drop >= 0.10 m") has to be read
# on the arm that *applies* the rule, not only on the control's counterfactual.
# D0/A's census (batch 1) gives the control's window per attempt; these two runs
# give the treatment's own window and chosen along (seed 5, the seed the D0
# census used). `FRUIT_BED_DIAG` is print-only, and the pair with batch 1's
# plain-B runs is the identity check that says so (`--identity` in
# `p2_report.py`).
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
mkdir -p logs/p43/p2

CLAIM=scripts/154_claim_run.sh
PICK="scripts/run.sh scripts/20_pick_place.py"
BASE_PICK="HEADLESS=1 ATTEMPTS=10 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_BED_DIAG=1"

run() {  # run <log> <env...>
    local log=$1; shift
    local t0 t1 code
    t0=$(date +%s)
    RUN_LIMIT=1500 "$CLAIM" "logs/p43/p2/$log" "$@"
    code=$?
    t1=$(date +%s)
    echo "[batch2] $log done exit=$code wall=$((t1 - t0))s $(date '+%H:%M:%S')"
}

run r_accept_B_s5_diag.log $BASE_PICK SEED=5 $PICK
run r_pear_B_s5_diag.log $BASE_PICK SEED=5 FRUIT_SUPPLY_SPECIES=pear $PICK

echo "[batch2] all done $(date '+%H:%M:%S')"
