#!/bin/bash
# P11-C.3: the from-open arrival + the cut chase range (0.002 m), seeds 11/5/23.
cd "$(dirname "$0")/../.." || exit 1
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
     FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 HEADLESS=1
     FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1)
B=(FRUIT_DYNAMIC_REGRASP_FROM_OPEN=1 FRUIT_DYNAMIC_FORCE_RANGE=0.002)
run() {
    local log=$1 seed=$2; shift 2
    echo "[c3] START $(date +%H:%M:%S) $log"
    RUN_LIMIT=5400 scripts/154_claim_run.sh "$log" "${TWO[@]}" SEED="$seed" "$@" \
        scripts/run.sh scripts/20_pick_place.py > "${log%.log}_driver.log" 2>&1
    echo "[c3] exit=$? $(date +%H:%M:%S) $log"
    return 0
}
run logs/p11c/51_seed11_B3.log 11 "${B[@]}"
run logs/p11c/53_seed5_B3.log 5 "${B[@]}"
run logs/p11c/55_seed23_B3.log 23 "${B[@]}"
echo "[c3] DONE $(date +%H:%M:%S)"
