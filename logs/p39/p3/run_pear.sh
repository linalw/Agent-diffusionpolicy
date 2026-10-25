#!/usr/bin/env bash
# P39 phase 3, battery 1 (PRIMARY): the species-locked pear battery.
# Arms interleaved C -> S -> F1 inside ONE claim (154_claim_run.sh claims this
# script). Recipe = the WORKLOG/P32 one: shipped scatter, species lock, 10
# attempts, SEED=5, motion report. 9 attempts are expected (attempt 7 is
# `no eligible fruit`).
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
OUT=logs/p39/p3
BASE=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_SUPPLY_SPECIES=pear ATTEMPTS=10 SEED=5)
status=0

run_arm() {  # run_arm <arm> [env...]
    local arm=$1; shift
    local log=$OUT/pear_${arm}.log t0
    t0=$(date +%s)
    echo "[p3] pear $arm START $(date +%H:%M:%S) env='$*'"
    env "${BASE[@]}" "$@" scripts/run.sh scripts/20_pick_place.py > "$log" 2>&1
    local code=$?
    echo "[p3] pear $arm EXIT=$code wall=$(( $(date +%s) - t0 ))s $(date +%H:%M:%S) log=$log"
    [ "$code" -eq 0 ] || status=1
}

run_arm C
run_arm S  FRUIT_FINGER_TIP_DELTA=0
run_arm F1 FRUIT_FINGER_TIP_DELTA=-0.004

echo "[p3] pear battery DONE $(date +%H:%M:%S) status=$status"
exit $status
