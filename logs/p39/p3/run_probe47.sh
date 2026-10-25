#!/usr/bin/env bash
# P39 phase 3, battery 3 (N4/N4b): scripts/47_robot_collision.py per arm,
# interleaved C -> S -> F1 inside ONE claim. The probe drives the left jaw
# straight down into the belt with the conveyor present and prints the stop
# floor (jaw z at the end + the two finger links' world AABBs), plus the jaw
# separation. N4: the floor shifts by delta*cos(theta) against S (= -4 mm on a
# near-vertical probe); N4b: S vs C within 1.5 mm.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
OUT=logs/p39/p3
status=0

run_arm() {  # run_arm <arm> [env...]
    local arm=$1; shift
    local log=$OUT/probe47_${arm}.log t0
    t0=$(date +%s)
    echo "[p3] probe47 $arm START $(date +%H:%M:%S) env='$*'"
    env HEADLESS=1 "$@" scripts/run.sh scripts/47_robot_collision.py > "$log" 2>&1
    local code=$?
    echo "[p3] probe47 $arm EXIT=$code wall=$(( $(date +%s) - t0 ))s $(date +%H:%M:%S) log=$log"
    [ "$code" -eq 0 ] || status=1
}

run_arm C
run_arm S  FRUIT_FINGER_TIP_DELTA=0
run_arm F1 FRUIT_FINGER_TIP_DELTA=-0.004

echo "[p3] probe47 battery DONE $(date +%H:%M:%S) status=$status"
exit $status
