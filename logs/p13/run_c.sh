#!/bin/bash
# P13-C: the mass-base reference run (the two-line patch battery, the mass env).
cd "$(dirname "$0")/../.." || exit 1
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
     FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 HEADLESS=1
     FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1)
echo "[p13c] START $(date +%H:%M:%S) the mass reference run"
RUN_LIMIT=5400 scripts/154_claim_run.sh logs/p13/10_mass_ref.log "${TWO[@]}" SEED=5 \
    FRUIT_PHYSICS_REAL_MASS=1 scripts/run.sh scripts/20_pick_place.py > logs/p13/10_mass_ref_driver.log 2>&1
echo "[p13c] exit=$? $(date +%H:%M:%S)"
python3 scripts/105_motion_regression.py logs/p13/10_mass_ref.log --min-success-rate 0.5 \
    --write-fingerprint configs/motion_reference_patch_mass.json > logs/p13/11_write_ref.log 2>&1
echo "[p13c] write-fingerprint exit=$? $(date +%H:%M:%S)"
echo "[p13c] DONE $(date +%H:%M:%S)"
