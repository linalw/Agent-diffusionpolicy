#!/bin/bash
# P10-C battery (prereg + amendment frozen): A = knob off (diag on), B = the monitor on the two-line.
cd "$(dirname "$0")/../.." || exit 1
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
     FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 SEED=5 HEADLESS=1
     FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1)
B=(FRUIT_CARRY_MONITOR=1 FRUIT_CARRY_MONITOR_TWOLINE=1 FRUIT_CARRY_MONITOR_LOAD_FLOOR=3.5)
status=0
run() {
    local log=$1 limit=$2 code; shift 2
    echo "[p10c] START $(date +%H:%M:%S) $log"
    RUN_LIMIT="$limit" scripts/154_claim_run.sh "$log" "$@" scripts/run.sh scripts/20_pick_place.py
    code=$?
    echo "[p10c] exit=$code $(date +%H:%M:%S) $log"
    [ "$code" -ne 0 ] && { echo "[p10c] FAIL $log"; status=1; }
    return 0
}
run logs/p10c/10_armA_diag.log 5400 "${TWO[@]}"
run logs/p10c/20_armB_1.log 5400 "${TWO[@]}" "${B[@]}"
run logs/p10c/21_armB_2.log 5400 "${TWO[@]}" "${B[@]}"
run logs/p10c/22_armB_diag.log 5400 "${TWO[@]}" "${B[@]}" FRUIT_CARRY_MONITOR_DIAG=1
[ "$status" -ne 0 ] && { echo "[p10c] incomplete"; exit 1; }
echo "[p10c] DONE $(date +%H:%M:%S)"
