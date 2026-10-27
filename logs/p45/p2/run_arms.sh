#!/usr/bin/env bash
# P45 phase 2 arms: the mass x speed cells, interleaved C -> M50 -> M25 -> M50S -> M25S.
#
#   bash logs/p45/p2/run_arms.sh A     # the acceptance, seed 5
#   bash logs/p45/p2/run_arms.sh B     # the species-locked pear, seed 5
#
# Normally driven by `run_batch.sh`, which holds ONE claim for the whole battery so
# no other lane can interleave between arms.
#
#   C    = unset                                        the same-tree control
#   M50  = FRUIT_MASS_SCALE=0.5                         half mass, shipped speed
#   M25  = FRUIT_MASS_SCALE=0.25                        quarter mass, shipped speed
#   M50S = FRUIT_MASS_SCALE=0.5  FRUIT_SPEED_ALL=1      does half mass make S safe?
#   M25S = FRUIT_MASS_SCALE=0.25 FRUIT_SPEED_ALL=1      the strongest form
#
# One instrumentation set on EVERY arm (the P44 rule: the instrument sits inside
# the contrast): MOTION_REPORT + CYCLE_REPORT (proven row-neutral), CARRY_DIAG
# (`clean_slip_max` / `force_min`, proven run-neutral on this scenario by
# `logs/p44/p2/amend_F_C.log` = 0 core rows changed), RELEASE_DEBUG (the fling)
# and PLACE_TRACE (the in-hand restriction E2 needs).
#
# Nothing here writes `configs/`, `datasets/` or a checkpoint.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
BATTERY=${1:?usage: run_arms.sh A|B}
OUT=logs/p45/p2
mkdir -p "$OUT"

PICK="scripts/run.sh scripts/20_pick_place.py"
BASE="HEADLESS=1 ATTEMPTS=10 SEED=5 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1"
INSTR="FRUIT_CARRY_DIAG=1 FRUIT_RELEASE_DEBUG=1 FRUIT_PLACE_TRACE=1"

case "$BATTERY" in
    A) SCEN=""; PREFIX=accept_s5 ;;
    B) SCEN="FRUIT_SUPPLY_SPECIES=pear"; PREFIX=pear_s5 ;;
    *) echo "[p45] unknown battery $BATTERY" >&2; exit 2 ;;
esac

ARMS="${P45_ARMS:-C M50 M25 M50S M25S}"

for arm in $ARMS; do
    case "$arm" in
        C)    ARM_ENV="" ;;
        M50)  ARM_ENV="FRUIT_MASS_SCALE=0.5" ;;
        M25)  ARM_ENV="FRUIT_MASS_SCALE=0.25" ;;
        M50S) ARM_ENV="FRUIT_MASS_SCALE=0.5 FRUIT_SPEED_ALL=1" ;;
        M25S) ARM_ENV="FRUIT_MASS_SCALE=0.25 FRUIT_SPEED_ALL=1" ;;
        *)    echo "[p45] unknown arm $arm" >&2; exit 2 ;;
    esac
    log="$OUT/${PREFIX}_${arm}.log"
    t0=$(date +%s)
    # shellcheck disable=SC2086
    env $BASE $INSTR $SCEN $ARM_ENV $PICK > "$log" 2>&1
    code=$?
    echo "[p45] $BATTERY $arm exit=$code wall=$(( $(date +%s) - t0 ))s $(date '+%H:%M:%S') log=$log"
done
echo "[p45] battery $BATTERY all done $(date '+%H:%M:%S')"
