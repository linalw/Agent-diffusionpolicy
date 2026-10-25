#!/usr/bin/env bash
# P39 phase 3, battery 4 (the mechanism readout, A2.7): the acceptance scenario
# again with FRUIT_CARRY_ATTITUDE=1 for ALL THREE arms (C is the lip anchor), 10
# attempts each, interleaved C -> S -> F1 inside ONE claim. The print is
# reporting only (one TCP read per carry leg) and is ON in every arm here, so
# it cannot favour one; the identity/class claims are made on the print-off
# runs (A1.4/A1.5).
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
OUT=logs/p39/p3
BASE=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CARRY_ATTITUDE=1 ATTEMPTS=10 SEED=5)
status=0

run_arm() {  # run_arm <arm> [env...]
    local arm=$1; shift
    local log=$OUT/mech_${arm}.log t0
    t0=$(date +%s)
    echo "[p3] mech $arm START $(date +%H:%M:%S) env='$*'"
    env "${BASE[@]}" "$@" scripts/run.sh scripts/20_pick_place.py > "$log" 2>&1
    local code=$?
    echo "[p3] mech $arm EXIT=$code wall=$(( $(date +%s) - t0 ))s $(date +%H:%M:%S) log=$log"
    [ "$code" -eq 0 ] || status=1
}

run_arm C
run_arm S  FRUIT_FINGER_TIP_DELTA=0
run_arm F1 FRUIT_FINGER_TIP_DELTA=-0.004

echo "[p3] mechanism battery DONE $(date +%H:%M:%S) status=$status"
exit $status
