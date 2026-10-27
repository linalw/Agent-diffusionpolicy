#!/usr/bin/env bash
# P46 phase 1 arms: the P44 speed union on the two-line, C -> U at seeds 5 and 6.
#
#   bash logs/p46/p1/run_arms.sh
#
# Normally driven by `run_batch.sh`, which holds ONE claim for the whole battery
# so no other lane can interleave a simulator between the control and the
# treatment (logs/p45/p2/run_batch.sh's pattern).
#
#   C = unset                       the shipped tree (control)
#   U = FRUIT_SPEED_ALL=1           the P44 union (place 0.52 / lift 0.36+1.9 /
#                                   the release clock at the 3 -> 2 settle)
#
# Scenario = P44 battery D verbatim: the two-line dense sheet, 10 attempts.
# One instrumentation set on EVERY arm (AGENTS 3b: the instrument sits inside the
# contrast) - MOTION_REPORT + CYCLE_REPORT (row-neutral, P43/P44) plus
# CARRY_DIAG (E3's walk) and PLACE_TRACE (E6's landing). Their neutrality on this
# scenario is CHECKED against the recorded no-diag log
# `logs/p44/p2/twoline_s5_C.log` (PREREG section 2), not assumed.
#
# Nothing here writes `configs/`, `datasets/` or a checkpoint.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
OUT=logs/p46/p1
mkdir -p "$OUT"

PICK="scripts/run.sh scripts/20_pick_place.py"
SCEN="FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1"
BASE="HEADLESS=1 ATTEMPTS=10 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1"
INSTR="FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1"

# C -> U per seed (PREREG section 2): the interleave is inside each seed, so the
# pair that is compared shares its supply draw and its session.
for seed in 5 6; do
    for arm in C U; do
        case "$arm" in
            C) ARM_ENV="" ;;
            U) ARM_ENV="FRUIT_SPEED_ALL=1" ;;
            *) echo "[p46] unknown arm $arm" >&2; exit 2 ;;
        esac
        log="$OUT/twoline_s${seed}_${arm}.log"
        t0=$(date +%s)
        # shellcheck disable=SC2086
        env $BASE $INSTR $SCEN SEED="$seed" $ARM_ENV $PICK > "$log" 2>&1
        code=$?
        echo "[p46] seed $seed $arm exit=$code wall=$(( $(date +%s) - t0 ))s $(date '+%H:%M:%S') log=$log"
    done
done
echo "[p46] battery all done $(date '+%H:%M:%S')"
