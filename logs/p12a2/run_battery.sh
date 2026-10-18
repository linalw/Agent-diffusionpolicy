#!/bin/bash
# P12-A.2 component batteries: mass-only and compliance-only on the two-line anchor.
cd "$(dirname "$0")/../.." || exit 1
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
     FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 HEADLESS=1
     FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1)
run() {
    local log=$1 seed=$2; shift 2
    echo "[p12a2] START $(date +%H:%M:%S) $log"
    RUN_LIMIT=5400 scripts/154_claim_run.sh "$log" "${TWO[@]}" SEED="$seed" "$@" \
        scripts/run.sh scripts/20_pick_place.py > "${log%.log}_driver.log" 2>&1
    echo "[p12a2] exit=$? $(date +%H:%M:%S) $log"
    return 0
}
run logs/p12a2/10_seed11_mass.log 11 FRUIT_PHYSICS_REAL_MASS=1
run logs/p12a2/11_seed5_mass.log 5 FRUIT_PHYSICS_REAL_MASS=1
run logs/p12a2/12_seed23_mass.log 23 FRUIT_PHYSICS_REAL_MASS=1
run logs/p12a2/20_seed11_comp.log 11 FRUIT_PHYSICS_REAL_COMPLIANCE=1
run logs/p12a2/21_seed5_comp.log 5 FRUIT_PHYSICS_REAL_COMPLIANCE=1
run logs/p12a2/22_seed23_comp.log 23 FRUIT_PHYSICS_REAL_COMPLIANCE=1
echo "[p12a2] DONE $(date +%H:%M:%S)"
