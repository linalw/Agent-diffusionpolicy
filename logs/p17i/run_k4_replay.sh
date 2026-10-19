#!/bin/bash
# K4: the knob-off control replay (seed 11) vs logs/p12a2/10_seed11_mass.log.
cd "$(dirname "$0")/../.." || exit 1
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
     FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 HEADLESS=1
     FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1)
echo "[k4] START $(date +%H:%M:%S)"
RUN_LIMIT=5400 scripts/154_claim_run.sh logs/p17i/70_k4_control_replay.log "${TWO[@]}" SEED=11 \
    FRUIT_PHYSICS_REAL_MASS=1 scripts/run.sh scripts/20_pick_place.py \
    > logs/p17i/70_k4_control_replay_driver.log 2>&1
echo "[k4] exit=$? $(date +%H:%M:%S)"
diff <(grep -a '\[fruit\]' logs/p12a2/10_seed11_mass.log) \
     <(grep -a '\[fruit\]' logs/p17i/70_k4_control_replay.log) > logs/p17i/71_k4_diff.txt 2>&1
echo "[k4] diff lines: $(wc -l < logs/p17i/71_k4_diff.txt)"
echo "[k4] DONE $(date +%H:%M:%S)"
