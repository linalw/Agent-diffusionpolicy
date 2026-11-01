#!/usr/bin/env bash
# One-command acceptance for the shipped sorting pipeline.
#
#   scripts/accept.sh              # ten attempts + the motion gate, with the baseline fingerprint
#   ATTEMPTS=20 scripts/accept.sh  # a longer run (the fingerprint check is skipped)
#   FRUIT_BIARM=0 scripts/accept.sh  # the pre-P85 single-arm scenario, its own reference
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
# **P85 (the flip).** The shipped scripted cell is now the bimanual two-line
# scheduler, which is a *different scenario* with its own reference and its own
# success floor - so the gate is chosen from the log, not assumed:
#
#   * two-line (the log carries `[biarm] two-line scheduler:`) ->
#     `scripts/190_twoline_gate.sh -r configs/motion_reference.json -m 0.60`.
#     That script exists precisely for this: it pins the scenario by its banner,
#     applies the two-line floor (105's own default is the single arm's 0.75) and
#     takes the per-scenario reference. Reusing it instead of teaching 105 a
#     second floor keeps one definition of "a two-line gate" in the tree.
#   * anything else (`FRUIT_BIARM=0`, or a shared-station
#     `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0` run) -> 105 with the pre-P85
#     single-arm record, shipped as `configs/motion_reference_single.json`
#     (byte-identical to the P85 archive
#     `logs/p85/motion_reference_single_pre_p85.json`).
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
single_fingerprint=configs/motion_reference_single.json

echo "=== scripted line: ${attempts} attempts, HEADLESS=${HEADLESS:-1} ==="
HEADLESS="${HEADLESS:-1}" FRUIT_MOTION_REPORT=1 ATTEMPTS="${attempts}" \
    scripts/run.sh scripts/20_pick_place.py > "${log}" 2>&1 || true
grep -E "\[stats\]|\[run\] summary" "${log}" | tail -2 || true
grep -E "\[biarm\] scheduler:|\[biarm\] two-line scheduler:" "${log}" | head -2 || true

two_line=0
if grep -q '\[fruit\] \[biarm\] two-line scheduler:' "${log}"; then
    two_line=1
fi

echo
echo "=== motion gate (session: $([ "$two_line" = "1" ] && echo two-line || echo single-arm)) ==="
if [ "${two_line}" = "1" ]; then
    floor=${TWOLINE_FLOOR:-0.60}
    if [ "${attempts}" = "10" ] && [ -f "${fingerprint}" ]; then
        scripts/190_twoline_gate.sh -r "${fingerprint}" -m "${floor}" "${log}"
    else
        echo "(the two-line fingerprint is a ten-attempt record; checking budgets + the ${floor} floor only)"
        python3 scripts/105_motion_regression.py "${log}" --min-success-rate "${floor}"
    fi
else
    if [ "${attempts}" = "10" ] && [ -f "${single_fingerprint}" ]; then
        python3 scripts/105_motion_regression.py "${log}" --fingerprint "${single_fingerprint}"
    else
        echo "(the baseline fingerprint is for a ten-attempt run; checking the budgets only)"
        python3 scripts/105_motion_regression.py "${log}"
    fi
fi
