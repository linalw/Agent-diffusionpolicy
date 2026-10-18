#!/bin/bash
# P12-A battery: FRUIT_PHYSICS_REAL=1 on the two-line anchor (seeds 11 primary + 5/23).
cd "$(dirname "$0")/../.." || exit 1
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
     FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 HEADLESS=1
     FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1)
B=(FRUIT_PHYSICS_REAL=1)
run() {
    local log=$1 seed=$2; shift 2
    echo "[p12a] START $(date +%H:%M:%S) $log"
    RUN_LIMIT=5400 scripts/154_claim_run.sh "$log" "${TWO[@]}" SEED="$seed" "$@" \
        scripts/run.sh scripts/20_pick_place.py > "${log%.log}_driver.log" 2>&1
    echo "[p12a] exit=$? $(date +%H:%M:%S) $log"
    return 0
}
run logs/p12/10_seed11_real.log 11 "${B[@]}"
run logs/p12/11_seed5_real.log 5 "${B[@]}"
run logs/p12/12_seed23_real.log 23 "${B[@]}"
echo "[p12a] DONE $(date +%H:%M:%S)"
