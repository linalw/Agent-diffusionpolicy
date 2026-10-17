#!/bin/bash
# P10-C.1 multi-seed confirmation: A vs B at SEED=11/23 (the patch battery shape, diag on both).
cd "$(dirname "$0")/../.." || exit 1
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
     FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 HEADLESS=1
     FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1)
B=(FRUIT_CARRY_MONITOR=1 FRUIT_CARRY_MONITOR_TWOLINE=1 FRUIT_CARRY_MONITOR_LOAD_FLOOR=3.5)
status=0
run() {
    local log=$1 seed=$2; shift 2
    echo "[seeds] START $(date +%H:%M:%S) $log"
    RUN_LIMIT=5400 scripts/154_claim_run.sh "$log" "${TWO[@]}" SEED="$seed" "$@" \
        scripts/run.sh scripts/20_pick_place.py > "${log%.log}_driver.log" 2>&1
    local code=$?
    echo "[seeds] exit=$code $(date +%H:%M:%S) $log"
    [ "$code" -ne 0 ] && status=1
    return 0
}
run logs/p10c/50_seed11_A.log 11
run logs/p10c/51_seed11_B.log 11 "${B[@]}"
run logs/p10c/52_seed23_A.log 23
run logs/p10c/53_seed23_B.log 23 "${B[@]}"
[ "$status" -ne 0 ] && { echo "[seeds] incomplete"; exit 1; }
echo "[seeds] DONE $(date +%H:%M:%S)"
