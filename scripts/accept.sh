#!/usr/bin/env bash
# One-command acceptance for the shipped sorting pipeline.
#
#   scripts/accept.sh              # ten attempts + the motion gate, with the baseline fingerprint
#   ATTEMPTS=20 scripts/accept.sh  # a longer run (the fingerprint check is skipped)
#
# Runs the scripted line end to end through scripts/run.sh (which raises the
# file-descriptor limit first, see WORKLOG 2026-09-27), then checks the log
# against the shipped motion budgets and the recorded baseline fingerprint.
# Exits non-zero if either fails, so this is safe to put in front of a report or a
# handing-over step.
#
# Why a fingerprint and not just a success count: the run is deterministic per
# configuration but the *outcome* is quantised into a small number of attractors,
# and which one you land in depends on instrumentation as much as on physics. A
# success-rate comparison across attractors measures the attractor, not the change
# under test (WORKLOG: "the outcome is quantized"). `configs/motion_reference.json`
# is the shipped ten-attempt run, so a fingerprint mismatch means "you are in a
# different scenario", not "your code is broken".
#
# It first runs scripts/selfcheck.sh (the simulator-free checks) so a broken
# tree fails in seconds instead of after a ten-minute Isaac Sim run. Set
# SKIP_SELFCHECK=1 to skip that - reasonable when you are iterating on the
# simulator scripts themselves and already know the data/offline checks pass.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ "${SKIP_SELFCHECK:-0}" != "1" ]; then
    echo "=== pre-flight self-check (SKIP_SELFCHECK=1 to skip) ==="
    if ! scripts/selfcheck.sh; then
        echo
        echo "FAIL: fix the self-check before spending a simulator run"
        exit 1
    fi
    echo
fi

attempts=${ATTEMPTS:-10}
log=${ACCEPT_LOG:-logs/accept.log}
fingerprint=configs/motion_reference.json

echo "=== scripted line: ${attempts} attempts, HEADLESS=${HEADLESS:-1} ==="
HEADLESS="${HEADLESS:-1}" FRUIT_MOTION_REPORT=1 ATTEMPTS="${attempts}" \
    scripts/run.sh scripts/20_pick_place.py > "${log}" 2>&1 || true
grep -E "\[stats\]|\[run\] summary" "${log}" | tail -2 || true

echo
echo "=== motion gate ==="
if [ "${attempts}" = "10" ] && [ -f "${fingerprint}" ]; then
    python3 scripts/105_motion_regression.py "${log}" --fingerprint "${fingerprint}"
else
    echo "(baseline fingerprint is for a ten-attempt run; checking the budgets only)"
    python3 scripts/105_motion_regression.py "${log}"
fi
