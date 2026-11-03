#!/usr/bin/env bash
# P108 - run an explicit list of cells, one per argument (`ARM:seed`).
#
#   bash logs/p108/cells.sh S:6 B:6 C:5      # one stream
#
# Split into two streams (two Isaac instances, one GPU - the sim is not GPU
# bound: 32 % utilisation, 4.4 GB of 32 GB) to halve the wall clock.  Both
# streams write disjoint files, so nothing is interleaved.
set -euo pipefail
cd "$(dirname "$0")/../.."

APERTURE=${APERTURE:-0.100}
GAP_MIN=${GAP_MIN:-0.150}
ATTEMPTS=${ATTEMPTS:-20}
OUT=logs/p108
INST="FRUIT_CAGE_PROBE=1 FRUIT_MOTION_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1"

for spec in "$@"; do
    name=${spec%%:*}
    seed=${spec##*:}
    log="${OUT}/${name}_s${seed}.log"
    if grep -q '^\[fruit\] \[stats\]' "${log}" 2>/dev/null; then
        echo "=== ${name} seed ${seed} (already complete, skipped)"
        continue
    fi
    case "${name}" in
        S) hand="" ;;
        B) hand="FRUIT_GRIPPER_KIND=cage4" ;;
        E) hand="FRUIT_GRIPPER_KIND=cage4 FRUIT_CAGE_OPEN_FACE_R=${APERTURE}" ;;
        C) hand="FRUIT_GRIPPER_KIND=cage4 FRUIT_CAGE_OPEN_FACE_R=${APERTURE} FRUIT_SUPPLY_GAP_MIN=${GAP_MIN}" ;;
        *) echo "unknown arm ${name}" >&2; exit 2 ;;
    esac
    echo "=== ${name} seed ${seed} ${hand}"
    env FRUIT_BIARM=0 SEED="${seed}" ATTEMPTS="${ATTEMPTS}" ${INST} ${hand} \
        scripts/run.sh scripts/20_pick_place.py > "${log}.tmp" 2>&1 || true
    mv "${log}.tmp" "${log}"
    grep -E '^\[fruit\] \[stats\]' "${log}" || echo "  (no stats - see ${log})"
done
