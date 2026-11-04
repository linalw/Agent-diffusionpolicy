#!/usr/bin/env bash
# P112 - the battery: the shipped hand (C) and the three-jaw ring (T), one cell
# per `ARM:seed`, the scripted single arm, identical instrumentation on both.
#
#   bash logs/p112/cells.sh C:5 T:5
set -euo pipefail
cd "$(dirname "$0")/../.."
ATTEMPTS=${ATTEMPTS:-20}
OUT=logs/p112
INST="FRUIT_CAGE_PROBE=1 FRUIT_MOTION_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1"
RING="FRUIT_GRIPPER_KIND=cage3 FRUIT_CAGE_OPEN_FACE_R=0.100 \
FRUIT_CAGE_PAD_STIFFNESS=3300 FRUIT_CAGE_PAD_DAMPING=16.2 \
FRUIT_CAGE_HOLD_STIFFNESS=100000"
for spec in "$@"; do
    name=${spec%%:*}
    seed=${spec##*:}
    log="${OUT}/${name}_s${seed}.log"
    if grep -q '^\[fruit\] \[stats\]' "${log}" 2>/dev/null; then
        echo "=== ${name} seed ${seed} (already complete, skipped)"
        continue
    fi
    case "${name}" in
        C) hand="" ;;
        T) hand="${RING}" ;;
        *) echo "unknown arm ${name}" >&2; exit 2 ;;
    esac
    echo "=== ${name} seed ${seed} ${hand}"
    env FRUIT_BIARM=0 SEED="${seed}" ATTEMPTS="${ATTEMPTS}" ${INST} ${hand} \
        scripts/run.sh scripts/20_pick_place.py > "${log}.tmp" 2>&1 || true
    mv "${log}.tmp" "${log}"
    grep -E '^\[fruit\] \[stats\]' "${log}" || echo "  (no stats - see ${log})"
done
