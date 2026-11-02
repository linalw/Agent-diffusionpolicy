#!/usr/bin/env bash
# P106 driver: the mount census, the grasp geometry, the Allegro cell, and the
# P104 control/surrogate re-run in the same batch.
#
#   bash logs/p106/run_p106.sh
#
# Each phase is its own app session (the mount is authored before `play()`), and
# every output lands beside this script. `configs/` is untouched by all of it.
set -uo pipefail
cd "$(dirname "$0")/../.."

OUT=${P106_OUT:-logs/p106}
mkdir -p "$OUT"

common="FRUIT_FINGER_COLLIDERS=0"

run() {
    local tag=$1; shift
    echo "# $tag $(date -u +%FT%TZ)" | tee "$OUT/$tag.txt"
    env $common "$@" scripts/run.sh logs/p106/m1_mount_probe.py 2>&1 \
        | grep -E '^\[fruit\] \[p106\]' | tee -a "$OUT/$tag.txt"
    echo | tee -a "$OUT/$tag.txt"
}

# 1. The mount: DOF count/order, drive readback, unit check, tool offset, and the
#    fingertip geometry per posture (the topology census).
run mount_census \
    P106_PHASE=A P106_CURLS="0.5,0.8,1.1,1.4" P106_THUMB0="0.4,0.9,1.3,1.5"

# 2. The Allegro cell: the one posture that held, one pear draw (measurement).
run m2a_allegro \
    P106_PHASE=C P106_FRUITS="pear,orange,strawberry" P106_REPEATS=1 \
    P106_HAND_K=20 P106_HAND_C=0.4 P106_HAND_CAP=5.0 P106_CLOSE_EXTRA=0.15 \
    P106_SEAT_CURL=1.1 P106_SEAT_THUMB0=1.4 P106_SEAT_CAP=5.0 P106_TARGET_TOTAL=18

# 3. The controls, from P104's fixture **unchanged**: the shipped pinch and the
#    4-pad radial surrogate, three fruits x three repeats.
P104_FORMS="pinch_plate quad" P104_OUT="$OUT/m2a_control.txt" \
    bash logs/p104/run_p104.sh >/dev/null 2>&1
echo "wrote $OUT/m2a_control.txt"
