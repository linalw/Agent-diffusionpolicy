#!/bin/bash
# P10-C.2 battery: the A no-harm anchor + the 3 gated B runs + the acceptance no-harm.
cd "$(dirname "$0")/../.." || exit 1
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
     FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 HEADLESS=1
     FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1)
B=(FRUIT_CARRY_MONITOR=1 FRUIT_CARRY_MONITOR_TWOLINE=1 FRUIT_CARRY_MONITOR_LOAD_FLOOR=3.5
   FRUIT_CARRY_MONITOR_CONFIRM_MM=8.0 FRUIT_CARRY_MONITOR_DIAG=1)
status=0
run() {
    local log=$1 seed=$2; shift 2
    echo "[p10c2] START $(date +%H:%M:%S) $log"
    RUN_LIMIT=5400 scripts/154_claim_run.sh "$log" "${TWO[@]}" SEED="$seed" "$@" \
        scripts/run.sh scripts/20_pick_place.py > "${log%.log}_driver.log" 2>&1
    local code=$?
    echo "[p10c2] exit=$code $(date +%H:%M:%S) $log"
    [ "$code" -ne 0 ] && status=1
    return 0
}
run logs/p10c2/60_armA_noharm.log 5
run logs/p10c2/61_seed5_B_gate.log 5 "${B[@]}"
run logs/p10c2/62_seed11_B_gate.log 11 "${B[@]}"
run logs/p10c2/63_seed23_B_gate.log 23 "${B[@]}"
echo "[p10c2] accept START $(date +%H:%M:%S)"
scripts/accept.sh > logs/p10c2/70_accept_noharm.log 2>&1
echo "[p10c2] accept exit=$? $(date +%H:%M:%S)"
[ "$status" -ne 0 ] && { echo "[p10c2] incomplete"; exit 1; }
echo "[p10c2] DONE $(date +%H:%M:%S)"
