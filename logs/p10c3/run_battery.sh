#!/bin/bash
# P10-C.3 verification battery: 3 flip runs (no resolution env) + 2 restore runs + the acceptance.
cd "$(dirname "$0")/../.." || exit 1
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
     FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 HEADLESS=1
     FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1)
status=0
run() {
    local log=$1 seed=$2; shift 2
    echo "[p10c3] START $(date +%H:%M:%S) $log"
    RUN_LIMIT=5400 scripts/154_claim_run.sh "$log" "${TWO[@]}" SEED="$seed" "$@" \
        scripts/run.sh scripts/20_pick_place.py > "${log%.log}_driver.log" 2>&1
    local code=$?
    echo "[p10c3] exit=$code $(date +%H:%M:%S) $log"
    [ "$code" -ne 0 ] && status=1
    return 0
}
run logs/p10c3/70_flip_seed5.log 5
run logs/p10c3/71_flip_seed11.log 11
run logs/p10c3/72_flip_seed23.log 23
run logs/p10c3/73_restore_gate0_seed11.log 11 FRUIT_CARRY_MONITOR_CONFIRM_MM=0
run logs/p10c3/74_restore_off_seed5.log 5 FRUIT_CARRY_MONITOR_TWOLINE=0
echo "[p10c3] accept START $(date +%H:%M:%S)"
scripts/accept.sh > logs/p10c3/80_accept.log 2>&1
echo "[p10c3] accept exit=$? $(date +%H:%M:%S)"
[ "$status" -ne 0 ] && { echo "[p10c3] incomplete"; exit 1; }
echo "[p10c3] DONE $(date +%H:%M:%S)"
