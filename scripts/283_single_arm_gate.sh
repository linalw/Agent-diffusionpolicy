#!/usr/bin/env bash
# P227s: the single-arm (Franka Panda + two side bins) cell's gate.
#
#   scripts/283_single_arm_gate.sh [attempts=6] [seed=5] [floor=0.80]
#
# Runs the delivered cell (`FRUIT_ARM_KIND=franka FRUIT_OUTPUT_BINS=1
# FRUIT_BIARM=0`) and exits 0 only when the placed count is at or above the
# floor, no attempt crashed, and - with an instruction armed
# (`FRUIT_SORT_INSTRUCTION`) - the ledger's assignment accuracy is complete
# (`in_destination == released`, `mis_sorted == 0`).
#
# Why a gate and not just a log: the cell's numbers (23/24 placed, 14.4-14.9
# s/attempt, the instruction ledger's 6/6) are cited by `docs/SINGLE_ARM_BINS_PLAN.md`
# and AGENTS P227i-P227s, and its code shares `tasks.py` with the shipped cells -
# without this, a change to a shared path could move it silently.
#
# The floor is a **branch floor, not a rate**: the cell's draws are quantized
# (P93's rule), so a 6-attempt arm reads 5/6 or 6/6 on the same tree. 0.80 is
# "one loss allowed", the two-line gate's 0.60 convention applied to a cell whose
# measured count is 96 %.
#
# Everything the caller exports is passed through (seed/FEED/speed knobs, an
# instruction, a scenario), so this is also the recipe runner:
#   FRUIT_SORT_INSTRUCTION=configs/instructions/shipped_grade.txt \
#     scripts/283_single_arm_gate.sh 6 5
set -euo pipefail
cd "$(dirname "$0")/.."

attempts="${1:-6}"
seed="${2:-5}"
floor="${3:-0.80}"
log_dir="${SINGLE_ARM_GATE_DIR:-logs/p227}"
mkdir -p "$log_dir"
log="$log_dir/cell_accept_$(date +%Y%m%d_%H%M%S)_s${seed}.log"

if [ "${SKIP_SELFCHECK:-0}" != "1" ]; then
    scripts/selfcheck.sh > /dev/null
fi

set +e
FRUIT_ARM_KIND=franka \
FRUIT_OUTPUT_BINS=1 \
FRUIT_BIARM=0 \
ATTEMPTS="$attempts" \
SEED="$seed" \
FRUIT_MOTION_REPORT=1 \
FRUIT_CYCLE_REPORT=1 \
FRUIT_PLACE_TRACE="${FRUIT_PLACE_TRACE:-1}" \
    scripts/run.sh scripts/20_pick_place.py > "$log" 2>&1
rc=$?
set -e

stats=$(grep -E '^\[fruit\] \[stats\]' "$log" | tail -1 || true)
if [ -z "$stats" ]; then
    echo "FAIL: no [stats] row - the run did not finish (rc=$rc, log $log)"
    tail -5 "$log" | sed 's/^/  /'
    exit 1
fi

rate=$(printf '%s\n' "$stats" | sed -n 's/.*success_rate=\([0-9]*\)%.*/\1/p')
rate=${rate:-0}
attempts_run=$(printf '%s\n' "$stats" | sed -n 's/.*attempts=\([0-9]*\).*/\1/p')
successes=$(printf '%s\n' "$stats" | sed -n 's/.*successes=\([0-9]*\).*/\1/p')

echo "single-arm cell: ${successes:-?}/${attempts_run:-?} placed (${rate}%), seed $seed"
grep -E '^\[fruit\] \[run\]   ' "$log" | sed 's/^\[fruit\] /  /' || true
grep -E '^\[fruit\] \[cycle\]' "$log" | tail -1 | sed 's/^\[fruit\] /  /' || true
[ -n "${FRUIT_SORT_INSTRUCTION:-}" ] && grep -E '^\[fruit\] \[sort\] ledger' "$log" | sed 's/^\[fruit\] /  /' || true
[ -n "${FRUIT_SORT_INSTRUCTION:-}" ] && grep -E '^\[fruit\] \[sort\] attempt' "$log" | sed 's/^\[fruit\] /  /' || true

fail=0
if [ "${rate:-0}" -lt "$(awk -v f="$floor" 'BEGIN { printf "%d", f * 100 + 0.5 }')" ]; then
    echo "FAIL: placed rate ${rate}% is below the ${floor} floor"
    fail=1
fi
if [ "$rc" -ne 0 ] && ! grep -q "success_rate=" "$log"; then
    echo "FAIL: the run exited $rc"
    fail=1
fi
if [ -n "${FRUIT_SORT_INSTRUCTION:-}" ]; then
    ledger=$(grep -E '^\[fruit\] \[sort\] ledger:' "$log" | tail -1 || true)
    released=$(printf '%s\n' "$ledger" | sed -n 's/.*released=\([0-9]*\).*/\1/p')
    in_dest=$(printf '%s\n' "$ledger" | sed -n 's/.*in_destination=\([0-9]*\).*/\1/p')
    mis=$(printf '%s\n' "$ledger" | sed -n 's/.*mis_sorted=\([0-9]*\).*/\1/p')
    if [ -z "$ledger" ]; then
        echo "FAIL: an instruction was armed but no ledger row was printed"
        fail=1
    elif [ "${in_dest:-0}" -ne "${released:-0}" ] || [ "${mis:-0}" -ne 0 ]; then
        echo "FAIL: the ledger is not clean (released=$released in_destination=$in_dest mis_sorted=$mis)"
        fail=1
    else
        echo "ledger clean: ${in_dest}/${released} in the instructed destination, 0 mis-sorted"
    fi
fi

if [ "$fail" -ne 0 ]; then
    exit 1
fi
echo "PASS ($log)"
