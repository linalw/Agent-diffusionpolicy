#!/usr/bin/env bash
# P40 phase 3 / R-R (a) - the two-line battery with the regrasp cap at 2.
# Control: logs/p39/p3/twoline_C.log (same scenario, FRUIT_REGRASPS unset = 3).
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1

HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 \
    FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 \
    FRUIT_REGRASPS=2 ATTEMPTS=10 SEED=5 \
    scripts/run.sh scripts/20_pick_place.py
