#!/usr/bin/env bash
# P131 - the four-pad ring's aperture-law cells, one per `ARM:seed`.
#
#   bash logs/p131/cells.sh U:5 P:5        # one stream
#   bash logs/p131/run_p131.sh             # the registered battery, two streams
#
# Arms:
#   U  the shipped law (unset)   - the P130 F5 replay
#   P  FRUIT_CAGE_APERTURE=pad_axes
#   M  FRUIT_CAGE_APERTURE=max_extent   (the screen)
#
# Every cell is `cage4` + the close freeze off, the single arm, the shipped
# supply and the P108/P110 instrumentation, so the control is P130's same-seed
# `F5`/`F6` (the unset path is proved byte-identical by `U5`).
set -euo pipefail
cd "$(dirname "$0")/../.."

ATTEMPTS=${ATTEMPTS:-20}
OUT=logs/p131
INST="FRUIT_CAGE_PROBE=1 FRUIT_MOTION_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1"
CAGE="FRUIT_GRIPPER_KIND=cage4 FRUIT_DYNAMIC_CLOSE_FREEZE=0"

for spec in "$@"; do
    name=${spec%%:*}
    seed=${spec##*:}
    log="${OUT}/${name}_s${seed}.log"
    if grep -q '^\[fruit\] \[stats\]' "${log}" 2>/dev/null; then
        echo "=== ${name} seed ${seed} (already complete, skipped)"
        continue
    fi
    case "${name}" in
        U) law="" ;;
        P) law="FRUIT_CAGE_APERTURE=pad_axes" ;;
        M) law="FRUIT_CAGE_APERTURE=max_extent" ;;
        *) echo "unknown arm ${name}" >&2; exit 2 ;;
    esac
    echo "=== ${name} seed ${seed} ${law:-shipped law}"
    # P130's cells leave `FRUIT_BIARM` unset: the default two-line scheduler is
    # refused by the cage hand (`[biarm] ... ignored: hand is 'cage4'`, one row)
    # but the **supply package** it scopes (the dense wave + the balanced mix)
    # is what the control `F5`/`F6` ran on.  `FRUIT_BIARM=0` would silently
    # switch the supply to the single-arm scatter (the P108 `B_*` cells) and the
    # replay would compare two different scenarios.
    env SEED="${seed}" ATTEMPTS="${ATTEMPTS}" ${INST} ${CAGE} ${law} \
        scripts/run.sh scripts/20_pick_place.py > "${log}.tmp" 2>&1 || true
    mv "${log}.tmp" "${log}"
    grep -E '^\[fruit\] \[stats\]' "${log}" || echo "  (no stats - see ${log})"
done
