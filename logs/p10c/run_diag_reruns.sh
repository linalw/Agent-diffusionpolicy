#!/bin/bash
# The MONITOR_DIAG re-runs of the seeds B branches (run-neutral; gives the fire accounting/K2).
cd "$(dirname "$0")/../.." || exit 1
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
     FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 HEADLESS=1
     FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1)
B=(FRUIT_CARRY_MONITOR=1 FRUIT_CARRY_MONITOR_TWOLINE=1 FRUIT_CARRY_MONITOR_LOAD_FLOOR=3.5 FRUIT_CARRY_MONITOR_DIAG=1)
run() {
    local log=$1 seed=$2
    echo "[diagr] START $(date +%H:%M:%S) $log"
    RUN_LIMIT=5400 scripts/154_claim_run.sh "$log" "${TWO[@]}" SEED="$seed" "${B[@]}" \
        scripts/run.sh scripts/20_pick_place.py > "${log%.log}_driver.log" 2>&1
    echo "[diagr] exit=$? $(date +%H:%M:%S) $log"
    return 0
}
run logs/p10c/51r_seed11_B_diag.log 11
run logs/p10c/53r_seed23_B_diag.log 23
echo "[diagr] DONE $(date +%H:%M:%S)"
