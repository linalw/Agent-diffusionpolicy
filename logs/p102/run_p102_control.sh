#!/usr/bin/env bash
# P102 controls: the same cell, same instrumentation, WITHOUT the new knob.
#
#   bash logs/p102/run_p102_control.sh          # C5 then C6
#
# Why a same-batch control rather than a cross-phase record. The obvious
# reference is `logs/p91/C5.log` (P92's control, replayed bit-for-bit by P92).
# It is **not admissible on this tree**: P91 predates P94's `_gripper_offset`
# guard, so it diverges at its own guarded row - attempt 0's left `grasp_lift`
# `[diag] carry-assist ... jaw_target=` reads `[0.4053, 0.0...]` here (the guard's
# `centre`) against `[0.3997, 0.4...]` there (the pre-P94
# `centre - rot @ offset`), exactly the divergence P96's `PREREG_A2` recorded for
# the p92 corpus. P100's own cells add `FRUIT_BIARM_PARK_TRACE` /
# `FRUIT_READY_DIAG` rows, so they are not the same instrumentation either.
# The proof of neutrality is therefore the P87/P88/P95 shape: **the same cell,
# the same batch, the knob the only difference** -
#
#   python3 logs/p102/census.py --same logs/p102/T5.log logs/p102/C5.log
#
# which must print `SAME: n/n lines identical with [tactile] dropped`.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p102

ENV_COMMON=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
            FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1)

fail=0
note() { echo "[p102c] $*"; }

claim_run() {
    local tag=$1; shift
    local log="logs/p102/${tag}.log"
    note "START $(date +%H:%M:%S) $tag  $*"
    RUN_LIMIT=3600 scripts/154_claim_run.sh "logs/p102/${tag}.driver" "$@" \
        bash logs/p80/one_run.sh "$log" "logs/p102/${tag}.stamps"
    local rc=$?
    note "exit=$rc $(date +%H:%M:%S) $tag"
    if [ "$rc" -ne 0 ] || [ ! -s "$log" ]; then
        note "FAIL $tag (rc=$rc)"; fail=$((fail + 1))
    fi
}

sel=("$@")
run() {
    local tag=$1; shift
    if [ "${#sel[@]}" -eq 0 ] || [[ " ${sel[*]} " == *" $tag "* ]]; then
        claim_run "$tag" "$@"
    fi
}

run C5 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5
run C6 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=6

note "controls done $(date +%H:%M:%S) failures=$fail"
exit "$fail"
