#!/bin/bash
# P26 verification: (1) the acceptance at the new defaults (the belt 0.15 + the B1c flip);
# (2) the two-line patch battery at 0.15, seeds 11/5/23 (the R3-style confirmation).
cd "$(dirname "$0")/../.." || exit 1
echo "[p26] ACC START $(date +%H:%M:%S)"
RUN_LIMIT=3600 scripts/154_claim_run.sh logs/p26/10_accept_015.log HEADLESS=1 ATTEMPTS=10 \
    FRUIT_MOTION_REPORT=1 scripts/run.sh scripts/20_pick_place.py \
    > logs/p26/10_accept_015_driver.log 2>&1
echo "[p26] ACC exit=$? $(date +%H:%M:%S)"
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
     FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_PHYSICS_REAL_MASS=1 ATTEMPTS=20 HEADLESS=1
     FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1)
for seed in 11 5 23; do
    echo "[p26] START $(date +%H:%M:%S) seed $seed"
    RUN_LIMIT=5400 scripts/154_claim_run.sh logs/p26/2${seed}_patch015_seed${seed}.log "${TWO[@]}" \
        SEED="$seed" scripts/run.sh scripts/20_pick_place.py \
        > logs/p26/2${seed}_patch015_seed${seed}_driver.log 2>&1
    echo "[p26] exit=$? $(date +%H:%M:%S) seed $seed"
done
echo "[p26] DONE $(date +%H:%M:%S)"
