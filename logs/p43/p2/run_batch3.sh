#!/usr/bin/env bash
# P43 phase 2, batch 3: the post-revert identity (the shipped default restored).
#
#   bash logs/p43/p2/run_batch3.sh > logs/p43/p2/batch3_driver.log 2>&1
#
# The flip was measured and NOT adopted, so the tree's scripted default is back
# to the shipped farthest-upstream pick (`NEAREST_ABOVE_FLOOR_SCRIPTED = "0"`).
# Two runs close the revert:
#   * unset  -> must be byte-identical to the knob-0 control (`d0_accept_A_s5`):
#               the shipped default is exactly the pre-P43 behaviour;
#   * =1     -> must be byte-identical to the measured treatment (`r_accept_B_s5`):
#               the treatment is one env var away, no code change.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
CLAIM=scripts/154_claim_run.sh
PICK="scripts/run.sh scripts/20_pick_place.py"
BASE="HEADLESS=1 ATTEMPTS=10 SEED=5 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1"

run() {
    local log=$1; shift
    local t0 t1 code
    t0=$(date +%s)
    RUN_LIMIT=1500 "$CLAIM" "logs/p43/p2/$log" "$@"
    code=$?
    t1=$(date +%s)
    echo "[batch3] $log done exit=$code wall=$((t1 - t0))s $(date '+%H:%M:%S')"
}

run post_revert_accept_unset.log $BASE $PICK
run post_revert_accept_k1.log $BASE FRUIT_SELECT_NEAREST_ABOVE_FLOOR=1 $PICK
echo "[batch3] all done $(date '+%H:%M:%S')"
