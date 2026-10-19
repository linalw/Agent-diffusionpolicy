#!/bin/bash
# P17-B Stage-N: the outcome battery for a promoted capture lever.
# Usage: run_outcome.sh <knob env assignments...>
#   e.g. run_outcome.sh FRUIT_DYNAMIC_SLIDE_GATE=1
# Runs the mass-base scenario (two-line patch battery, FRUIT_PHYSICS_REAL_MASS=1)
# at seeds 11/5/23 (ATTEMPTS=20 each) with the given knob(s); controls are the
# on-disk mass base records logs/p12a2/{10_seed11,11_seed5,12_seed23}_mass.log.
cd "$(dirname "$0")/../.." || exit 1
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
     FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 HEADLESS=1
     FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1)
TAG="$1"; shift
[ -z "$TAG" ] && { echo "usage: run_outcome.sh <knob=1> [more...]"; exit 2; }
SAFE=$(echo "$TAG" | tr '=,.' '_')
run() {
    local log=$1 seed=$2; shift 2
    echo "[p17n] START $(date +%H:%M:%S) $log"
    RUN_LIMIT=5400 scripts/154_claim_run.sh "$log" "${TWO[@]}" SEED="$seed" "$@" \
        scripts/run.sh scripts/20_pick_place.py > "${log%.log}_driver.log" 2>&1
    echo "[p17n] exit=$? $(date +%H:%M:%S) $log"
    return 0
}
run "logs/p17i/30_seed11_${SAFE}.log" 11 FRUIT_PHYSICS_REAL_MASS=1 "$TAG" "$@"
run "logs/p17i/31_seed5_${SAFE}.log" 5 FRUIT_PHYSICS_REAL_MASS=1 "$TAG" "$@"
run "logs/p17i/32_seed23_${SAFE}.log" 23 FRUIT_PHYSICS_REAL_MASS=1 "$TAG" "$@"
echo "[p17n] DONE $(date +%H:%M:%S)"
