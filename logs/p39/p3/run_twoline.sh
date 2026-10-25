#!/usr/bin/env bash
# P39 phase 3, battery 5: the two-line gate. A2.7 permits shortening this
# battery to the arms whose pear/acceptance FILTERED `[fruit]` stream moved vs C;
# the deviation is recorded in RESULT.md. Usage:
#
#   bash logs/p39/p3/run_twoline.sh C S F1     # all three
#   bash logs/p39/p3/run_twoline.sh S F1       # only the arms that moved
#
# The scenario of record is the W7-A dense two-line battery (10 attempts, seed 5,
# trace off) whose fingerprint is configs/motion_reference_twoline.json
# (181c9151); scripts/190 gates the log against it with its own 0.60 floor.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
OUT=logs/p39/p3
BASE=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 ATTEMPTS=10 SEED=5)
status=0

if [ "$#" -eq 0 ]; then
    echo "[p3] twoline: no arms requested; nothing to run (A2.7 deviation)"
    exit 0
fi

run_arm() {  # run_arm <arm> [env...]
    local arm=$1; shift
    local log=$OUT/twoline_${arm}.log t0
    t0=$(date +%s)
    echo "[p3] twoline $arm START $(date +%H:%M:%S) env='$*'"
    env "${BASE[@]}" "$@" scripts/run.sh scripts/20_pick_place.py > "$log" 2>&1
    local code=$?
    echo "[p3] twoline $arm EXIT=$code wall=$(( $(date +%s) - t0 ))s $(date +%H:%M:%S) log=$log"
    [ "$code" -eq 0 ] || status=1
}

for arm in "$@"; do
    case "$arm" in
        C)  run_arm C ;;
        S)  run_arm S  FRUIT_FINGER_TIP_DELTA=0 ;;
        F1) run_arm F1 FRUIT_FINGER_TIP_DELTA=-0.004 ;;
        *)  echo "[p3] twoline: unknown arm $arm" >&2; status=1 ;;
    esac
done

echo "[p3] twoline battery DONE $(date +%H:%M:%S) status=$status"
exit $status
