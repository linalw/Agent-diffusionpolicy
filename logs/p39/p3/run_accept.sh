#!/usr/bin/env bash
# P39 phase 3, battery 2 (REPORT + N1): scripts/accept.sh per arm, interleaved
# C -> S -> F1 inside ONE claim. accept.sh = 10 attempts + the motion gate +
# the fingerprint line against configs/motion_reference.json.
#
# SKIP_SELFCHECK=1 per the phase-3 brief (selfcheck rewrites the tracked
# logs/p36/offline_obs_diff.txt, which would dirty the measurement tree).
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
OUT=logs/p39/p3
status=0

run_arm() {  # run_arm <arm> [env...]
    local arm=$1; shift
    local log=$OUT/accept_${arm}.log t0
    t0=$(date +%s)
    echo "[p3] accept $arm START $(date +%H:%M:%S) env='$*'"
    env SKIP_SELFCHECK=1 ACCEPT_LOG="$log" "$@" scripts/accept.sh
    local code=$?
    echo "[p3] accept $arm EXIT=$code wall=$(( $(date +%s) - t0 ))s $(date +%H:%M:%S) log=$log"
    # accept.sh exits non-zero when the motion gate/rate floor fails; that is a
    # measurement, not a battery failure - record it and carry on.
    echo "[p3] accept $arm gate-exit=$code"
}

run_arm C
run_arm S  FRUIT_FINGER_TIP_DELTA=0
run_arm F1 FRUIT_FINGER_TIP_DELTA=-0.004

echo "[p3] accept battery DONE $(date +%H:%M:%S)"
exit $status
