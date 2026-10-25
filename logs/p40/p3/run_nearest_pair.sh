#!/usr/bin/env bash
# P40 phase 3 / R-S (item 2) - the single-arm selection rule, both arms in ONE
# claim and the same stretch (AGENTS section 3b): the knob-off arm first (the
# byte-identity proof for the unset path against logs/p39/p3/accept_C.log),
# then the nearest-above-floor arm.
#
#   C = FRUIT_SELECT_NEAREST_ABOVE_FLOOR unset  -> logs/p40/p3/nearest_off.log
#   N = FRUIT_SELECT_NEAREST_ABOVE_FLOOR=1      -> logs/p40/p3/nearest_accept.log
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1

run_arm() {
    local log=$1; shift
    echo "[pair] $* -> $log $(date +%H:%M:%S)"
    SKIP_SELFCHECK=1 ACCEPT_LOG="$log" "$@" scripts/accept.sh
    echo "[pair] exit=$? $(date +%H:%M:%S) log=$log"
}

run_arm logs/p40/p3/nearest_off.log
run_arm logs/p40/p3/nearest_accept.log FRUIT_SELECT_NEAREST_ABOVE_FLOOR=1
