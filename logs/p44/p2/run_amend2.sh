#!/usr/bin/env bash
# Resume of the P44 phase-2 amend battery (the first driver died after the C arm;
# `amend_E_C.log` is complete and is reused). Runs the remaining arms only:
#
#   E: S1, S3v      (+ FRUIT_CARRY_DIAG=1, the same instrument as the C arm)
#   F: C, S2        (+ CARRY_DIAG + RELEASE_DEBUG + PLACE_TRACE on both arms)
#
#   setsid nohup bash logs/p44/p2/run_amend2.sh > logs/p44/p2/amend2_driver.log 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
OUT=logs/p44/p2
CLAIM=scripts/154_claim_run.sh
PICK="scripts/run.sh scripts/20_pick_place.py"
BASE="HEADLESS=1 ATTEMPTS=10 SEED=5 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1"
F_EXTRA="FRUIT_RELEASE_DEBUG=1 FRUIT_PLACE_TRACE=1"

run() {  # run <battery> <arm> <env...>
    local battery=$1 arm=$2; shift 2
    local log="$OUT/amend_${battery}_${arm}.log" t0
    t0=$(date +%s)
    echo "[amend2] $battery $arm START $(date '+%H:%M:%S')"
    # shellcheck disable=SC2086
    env RUN_LIMIT=1500 "$CLAIM" "$log" $BASE $@ $PICK
    echo "[amend2] $battery $arm exit=$? wall=$(( $(date +%s) - t0 ))s $(date '+%H:%M:%S')"
}

run E S1  FRUIT_DYNAMIC_PLACE_VMAX=0.52
run E S3v FRUIT_DYNAMIC_LIFT_VMAX=0.37
run F C $F_EXTRA
run F S2  $F_EXTRA FRUIT_RELEASE_DWELL=0 FRUIT_RELEASE_PAD_HOLD=1 FRUIT_RELEASE_FINGER_HOLD=1
echo "[amend2] all done $(date '+%H:%M:%S')"
