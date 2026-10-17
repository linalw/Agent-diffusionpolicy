#!/bin/bash
# P11-C battery: the re-seat arrival geometry (FRUIT_DYNAMIC_REGRASP_FROM_OPEN), seeds 11/5/23.
cd "$(dirname "$0")/../.." || exit 1
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
     FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 HEADLESS=1
     FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1)
B=(FRUIT_DYNAMIC_REGRASP_FROM_OPEN=1)
status=0
run() {
    local log=$1 seed=$2; shift 2
    echo "[p11c] START $(date +%H:%M:%S) $log"
    RUN_LIMIT=5400 scripts/154_claim_run.sh "$log" "${TWO[@]}" SEED="$seed" "$@" \
        scripts/run.sh scripts/20_pick_place.py > "${log%.log}_driver.log" 2>&1
    local code=$?
    echo "[p11c] exit=$code $(date +%H:%M:%S) $log"
    [ "$code" -ne 0 ] && status=1
    return 0
}
run logs/p11c/10_seed11_A.log 11
run logs/p11c/11_seed11_B.log 11 "${B[@]}"
run logs/p11c/20_seed5_A.log 5
run logs/p11c/21_seed5_B.log 5 "${B[@]}"
run logs/p11c/30_seed23_A.log 23
run logs/p11c/31_seed23_B.log 23 "${B[@]}"
[ "$status" -ne 0 ] && { echo "[p11c] incomplete"; exit 1; }
echo "[p11c] DONE $(date +%H:%M:%S)"
