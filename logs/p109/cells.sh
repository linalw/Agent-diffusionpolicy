#!/usr/bin/env bash
# P109 - run an explicit list of cells, one per argument (`ARM:seed`).
#
#   bash logs/p109/cells.sh M0:5 M05:5 M1:5     # one stream
#
# Split into two streams (two Isaac instances, one GPU - the sim is not GPU
# bound: P108 measured 32 % utilisation, 4.4 GB of 32 GB) to halve the wall
# clock.  Both streams write disjoint files, so nothing is interleaved.
#
# The three arms are `FRUIT_DYNAMIC_DESCEND_MARGIN` unset (M0, the shipped 0.15),
# 0.075 (M05, the dose axis) and 0 (M1).  `logs/p109/PREREG.md` (md5 pinned in
# `PREREG.md5`) fixes the arms, the seeds, the endpoints and the decision rule.
set -euo pipefail
cd "$(dirname "$0")/../.."

ATTEMPTS=${ATTEMPTS:-20}
OUT=logs/p109
INST="FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1"

for spec in "$@"; do
    name=${spec%%:*}
    seed=${spec##*:}
    log="${OUT}/${name}_s${seed}.log"
    if grep -q '^\[fruit\] \[stats\]' "${log}" 2>/dev/null; then
        echo "=== ${name} seed ${seed} (already complete, skipped)"
        continue
    fi
    case "${name}" in
        M0)  margin="" ;;                                     # unset = 0.15
        M05) margin="FRUIT_DYNAMIC_DESCEND_MARGIN=0.075" ;;
        M1)  margin="FRUIT_DYNAMIC_DESCEND_MARGIN=0" ;;
        *) echo "unknown arm ${name}" >&2; exit 2 ;;
    esac
    echo "=== ${name} seed ${seed} ${margin:-margin unset}"
    env FRUIT_BIARM=0 SEED="${seed}" ATTEMPTS="${ATTEMPTS}" ${INST} ${margin} \
        scripts/run.sh scripts/20_pick_place.py > "${log}.tmp" 2>&1 || true
    mv "${log}.tmp" "${log}"
    grep -E '^\[fruit\] \[stats\]' "${log}" || echo "  (no stats - see ${log})"
done
