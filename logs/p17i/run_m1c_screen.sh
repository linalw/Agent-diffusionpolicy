#!/bin/bash
# P18-D: the M1c screen - the recalibrated slide gate (the P18-C operating point).
# MMPS=90 / TICKS=2 (was 60/3); the window unchanged. One traced run at SEED 11
# (the mechanism seed); the M1 (60/3) screen run is the on-disk control.
cd "$(dirname "$0")/../.." || exit 1
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
     FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 HEADLESS=1
     FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1
     FRUIT_PHYSICS_REAL_MASS=1)
echo "[p18d] START $(date +%H:%M:%S)"
RUN_LIMIT=5400 scripts/154_claim_run.sh logs/p17i/80_m1c_trace.log "${TWO[@]}" SEED=11 \
    FRUIT_DYNAMIC_TRACE=1 FRUIT_DYNAMIC_TRACE_DIR=logs/p17i/traces_m1c \
    FRUIT_DYNAMIC_SLIDE_GATE=1 FRUIT_DYNAMIC_SLIDE_GATE_MMPS=90 \
    FRUIT_DYNAMIC_SLIDE_GATE_TICKS=2 FRUIT_DYNAMIC_SLIDE_GATE_DIAG=1 \
    scripts/run.sh scripts/20_pick_place.py > logs/p17i/80_m1c_trace_driver.log 2>&1
echo "[p18d] exit=$? $(date +%H:%M:%S)"
echo "[p18d] DONE $(date +%H:%M:%S)"
