#!/usr/bin/env bash
# P111 - run an explicit list of cells, one per argument (`ARM:seed`).
#
#   bash logs/p111/cells.sh C:5 R:5 T1:5
#
# Two streams (two Isaac instances, one GPU - the sim is not GPU bound) are fine:
# both write disjoint files, so nothing is interleaved.
#
# The cell is the **scripted single arm** (`FRUIT_BIARM=0`): the two-line
# scheduler refuses a non-`openarm` hand by construction, so the cage only ever
# runs here.  Every arm carries the *same* instrumentation (P108's `inst()`), so
# the arms are compared inside one instrumented batch - the tree's own rule.
#
# Arms (logs/p111/PREREG.md section 2):
#   C   shipped `openarm` hand                       - the delivered reference
#   R   cage4, 200 mm, k 1e5 c 100 (the rigid ring)   - the compliance control
#   T1  cage4, 200 mm, k 1e3 c 8.9 + hold 1e5/89.4   - the registered point
#   T2  cage4, 200 mm, k 5e3 c 14.1 + hold 1e5/89.4  - the algebra's stiff side
#   S1  cage4, 200 mm, k 1e3 c 8.9, NO hold          - the pure-soft screen (F3)
#   T4  cage4, 200 mm, RIGID approach + a soft CLOSE window (k 1e3) + the stop
#       - the scoped form: soft only between `close_begin` and `close_done`
set -euo pipefail
cd "$(dirname "$0")/../.."

ATTEMPTS=${ATTEMPTS:-20}
OUT=logs/p111
INST="FRUIT_CAGE_PROBE=1 FRUIT_MOTION_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1"
CAGE="FRUIT_GRIPPER_KIND=cage4 FRUIT_CAGE_OPEN_FACE_R=0.100"

for spec in "$@"; do
    name=${spec%%:*}
    seed=${spec##*:}
    log="${OUT}/${name}_s${seed}.log"
    if grep -q '^\[fruit\] \[stats\]' "${log}" 2>/dev/null; then
        echo "=== ${name} seed ${seed} (already complete, skipped)"
        continue
    fi
    case "${name}" in
        C)  hand="" ;;
        R)  hand="${CAGE}" ;;
        T1) hand="${CAGE} FRUIT_CAGE_PAD_STIFFNESS=1000 FRUIT_CAGE_PAD_DAMPING=8.9 FRUIT_CAGE_HOLD_STIFFNESS=100000" ;;
        T2) hand="${CAGE} FRUIT_CAGE_PAD_STIFFNESS=5000 FRUIT_CAGE_PAD_DAMPING=14.1 FRUIT_CAGE_HOLD_STIFFNESS=100000" ;;
        S1) hand="${CAGE} FRUIT_CAGE_PAD_STIFFNESS=1000 FRUIT_CAGE_PAD_DAMPING=8.9" ;;
        T4) hand="${CAGE} FRUIT_CAGE_CLOSE_STIFFNESS=1000 FRUIT_CAGE_CLOSE_DAMPING=8.9 FRUIT_CAGE_HOLD_STIFFNESS=100000" ;;
        *)  echo "unknown arm ${name}" >&2; exit 2 ;;
    esac
    echo "=== ${name} seed ${seed} ${hand}"
    env FRUIT_BIARM=0 SEED="${seed}" ATTEMPTS="${ATTEMPTS}" ${INST} ${hand} \
        scripts/run.sh scripts/20_pick_place.py > "${log}.tmp" 2>&1 || true
    mv "${log}.tmp" "${log}"
    grep -E '^\[fruit\] \[stats\]' "${log}" || echo "  (no stats - see ${log})"
done
