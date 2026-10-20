#!/bin/bash
# P22-B: the release tail trim + the supply-clock resync (FRUIT_RELEASE_RESYNC=1) on the
# two-line mass base; arms: the trim+resync (new) vs the trim (logs/p21i/1*_relB) vs the control.
cd "$(dirname "$0")/../.." || exit 1
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
     FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_PHYSICS_REAL_MASS=1 ATTEMPTS=20 HEADLESS=1
     FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1
     FRUIT_PLACE_TRACE=1)
BR=(FRUIT_RELEASE_DWELL=12 FRUIT_RELEASE_PAD_HOLD=1 FRUIT_RELEASE_FINGER_HOLD=1 FRUIT_RELEASE_RESYNC=1)
run() { local log=$1 seed=$2; shift 2; echo "[p22b] START $(date +%H:%M:%S) $log"
    RUN_LIMIT=5400 scripts/154_claim_run.sh "$log" "${TWO[@]}" SEED="$seed" "$@" \
        scripts/run.sh scripts/20_pick_place.py > "${log%.log}_driver.log" 2>&1
    echo "[p22b] exit=$? $(date +%H:%M:%S) $log"; return 0; }
for seed in 11 5 23; do
    run "logs/p21i/20_seed${seed}_relBR_1.log" "$seed" "${BR[@]}"
    run "logs/p21i/21_seed${seed}_relBR_2.log" "$seed" "${BR[@]}"
done
echo "[p22b] DONE $(date +%H:%M:%S)"
