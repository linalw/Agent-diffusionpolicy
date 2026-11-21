#!/usr/bin/env bash
# P227m: one scripted attempt on the single-arm (Panda + side bins) cell.
#
#   scripts/run.sh logs/p227/franka_waypoints.py      # writes configs/waypoints_franka.json
#   bash logs/p227/run_attempt.sh [attempts] [seed]
#
# `FRUIT_BIARM=0` because the two-line `CoopSession` refuses a non-OpenArm hand
# (`tasks.py`); the bin cell is one arm, so the shipped scheduler is not the
# path. `FRUIT_OUTPUT_BINS=1` builds the bins and makes `_place_xy_for` aim
# there; the dynamic catch (`FRUIT_DYNAMIC_PICK` defaults True since P143) is
# what the Panda's per-fruit standoff needs - a *fixed* grasp height holds 1/4
# on the static gate and the moving catch is the pipeline.
set -euo pipefail
cd "$(dirname "$0")/../.."

attempts="${1:-1}"
seed="${2:-5}"
gate=""
if [ "${SKIP_SELFCHECK:-0}" != "1" ]; then
    scripts/selfcheck.sh > /dev/null
    gate=""
fi
FRUIT_ARM_KIND=franka \
FRUIT_OUTPUT_BINS=1 \
FRUIT_BIARM=0 \
ATTEMPTS="$attempts" \
SEED="$seed" \
FRUIT_MOTION_REPORT=1 \
FRUIT_CYCLE_REPORT=1 \
scripts/run.sh scripts/20_pick_place.py
