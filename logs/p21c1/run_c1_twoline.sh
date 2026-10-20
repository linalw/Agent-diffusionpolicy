#!/bin/bash
# P17-B Stage-P: the outcome battery for the promoted capture lever (K3 doubles).
# Usage: run_stage_p.sh <tag> <knob env assignments...>
#   e.g. run_stage_p.sh slide FRUIT_DYNAMIC_SLIDE_GATE=1 FRUIT_DYNAMIC_SLIDE_GATE_DIAG=1
# Seeds 11/5/23, ATTEMPTS=20, the mass-base scenario; each seed run twice
# (the K3 bit-identical double). Primaries are traced (the walk read vs the
# P14-B control corpus traces_s11/s5/s23); doubles are untraced.
cd "$(dirname "$0")/../.." || exit 1
TAG="$1"; shift
[ -z "$TAG" ] && { echo "usage: run_stage_p.sh <tag> <knob=1> [more...]"; exit 2; }
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
     FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 HEADLESS=1
     FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1)
run() {
    local log=$1 seed=$2; shift 2
    echo "[p17p] START $(date +%H:%M:%S) $log"
    RUN_LIMIT=5400 scripts/154_claim_run.sh "$log" "${TWO[@]}" SEED="$seed" "$@" \
        scripts/run.sh scripts/20_pick_place.py > "${log%.log}_driver.log" 2>&1
    echo "[p17p] exit=$? $(date +%H:%M:%S) $log"
    return 0
}
run "logs/p21c1/10_seed11_c1_${TAG}.log" 11 FRUIT_PHYSICS_REAL_MASS=1 "$@" FRUIT_DYNAMIC_TRACE=1 FRUIT_DYNAMIC_TRACE_DIR="logs/p21c1/traces_s11"
run "logs/p21c1/11_seed11_c1_${TAG}_double.log" 11 FRUIT_PHYSICS_REAL_MASS=1 "$@"
run "logs/p21c1/12_seed5_c1_${TAG}.log" 5 FRUIT_PHYSICS_REAL_MASS=1 "$@" FRUIT_DYNAMIC_TRACE=1 FRUIT_DYNAMIC_TRACE_DIR="logs/p21c1/traces_s5"
run "logs/p21c1/13_seed5_c1_${TAG}_double.log" 5 FRUIT_PHYSICS_REAL_MASS=1 "$@"
run "logs/p21c1/14_seed23_c1_${TAG}.log" 23 FRUIT_PHYSICS_REAL_MASS=1 "$@" FRUIT_DYNAMIC_TRACE=1 FRUIT_DYNAMIC_TRACE_DIR="logs/p21c1/traces_s23"
run "logs/p21c1/15_seed23_c1_${TAG}_double.log" 23 FRUIT_PHYSICS_REAL_MASS=1 "$@"
echo "[p17p] DONE $(date +%H:%M:%S)"
