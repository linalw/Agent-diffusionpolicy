#!/bin/bash
# P12-B.2/S3: the approach-height change (FRUIT_DYNAMIC_PAD_LIFT=0.020) on the mass base.
cd "$(dirname "$0")/../.." || exit 1
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
     FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 HEADLESS=1
     FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1)
B=(FRUIT_PHYSICS_REAL_MASS=1 FRUIT_DYNAMIC_PAD_LIFT=0.020)
run() {
    local log=$1 seed=$2; shift 2
    echo "[s3] START $(date +%H:%M:%S) $log"
    RUN_LIMIT=5400 scripts/154_claim_run.sh "$log" "${TWO[@]}" SEED="$seed" "$@" \
        scripts/run.sh scripts/20_pick_place.py > "${log%.log}_driver.log" 2>&1
    echo "[s3] exit=$? $(date +%H:%M:%S) $log"
    return 0
}
run logs/p12b/10_seed11_mass_s3.log 11 "${B[@]}"
run logs/p12b/11_seed5_mass_s3.log 5 "${B[@]}"
run logs/p12b/12_seed23_mass_s3.log 23 "${B[@]}"
echo "[s3] DONE $(date +%H:%M:%S)"
