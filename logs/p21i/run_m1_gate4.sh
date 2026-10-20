#!/bin/bash
# P22-C: the Oracle Gate-4 minimal read (4.5): R0 + the s11 A/B/BR with FRUIT_SUPPLY_DIAG=1 + trace.
cd "$(dirname "$0")/../.." || exit 1
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
     FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_PHYSICS_REAL_MASS=1 ATTEMPTS=20 HEADLESS=1
     FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1
     FRUIT_PLACE_TRACE=1 FRUIT_SUPPLY_DIAG=1)
TRIM=(FRUIT_RELEASE_DWELL=12 FRUIT_RELEASE_PAD_HOLD=1 FRUIT_RELEASE_FINGER_HOLD=1)
BR=(FRUIT_RELEASE_DWELL=12 FRUIT_RELEASE_PAD_HOLD=1 FRUIT_RELEASE_FINGER_HOLD=1 FRUIT_RELEASE_RESYNC=1)
run() { local log=$1; shift; echo "[p22c] START $(date +%H:%M:%S) $log"
    RUN_LIMIT=5400 scripts/154_claim_run.sh "$log" "${TWO[@]}" SEED=11 "$@" \
        scripts/run.sh scripts/20_pick_place.py > "${log%.log}_driver.log" 2>&1
    echo "[p22c] exit=$? $(date +%H:%M:%S) $log"; return 0; }
run logs/p21i/30_seed11_R0.log
run logs/p21i/31_seed11_A.log
run logs/p21i/32_seed11_B.log "${TRIM[@]}"
run logs/p21i/33_seed11_BR.log "${BR[@]}"
echo "[p22c] DONE $(date +%H:%M:%S)"
