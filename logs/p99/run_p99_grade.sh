#!/usr/bin/env bash
# P99 pricing cells: what the cross-lane mechanism is worth when it is actually
# allowed (`FRUIT_GRADE_ROUTING=0`, the V2 grade-preference-with-fallback).
#
#   bash logs/p99/run_p99_grade.sh          # both seeds
#   bash logs/p99/run_p99_grade.sh G5       # a subset
#
# NOT an adoption candidate: with one output belt per arm (left = lane 0 = grade
# A, right = lane 1 = grade B) a cross-lane pick places the fruit on the arm's
# own lane, i.e. it is a **sort error** (`logs/r2` / AGENTS §2's
# `cross-lane station fruit ... placed on lane M` note). The cells price the
# census's mechanism (i) - they do not propose a default. Nothing in `src/` or
# `configs/` changes; the knob is the shipped V2 fallback.
#
# Instrumentation is the census cells' verbatim, so the same `[bed-sel]` detail
# rows, the same interval decomposition and the same landing guard read on both
# arms of this comparison.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p99

ENV_COMMON=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
            FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1
            FRUIT_BIARM_PARK_TRACE=1 FRUIT_BED_DIAG=2
            FRUIT_GRADE_ROUTING=0)

fail=0
note() { echo "[p99g] $*"; }

claim_run() {  # claim_run <tag> <env...>
    local tag=$1; shift
    local log="logs/p99/${tag}.log"
    note "START $(date +%H:%M:%S) $tag  $*"
    RUN_LIMIT=3600 scripts/154_claim_run.sh "logs/p99/${tag}.driver" "$@" \
        bash logs/p80/one_run.sh "$log" "logs/p99/${tag}.stamps"
    local rc=$?
    note "exit=$rc $(date +%H:%M:%S) $tag"
    if [ "$rc" -ne 0 ] || [ ! -s "$log" ]; then
        note "FAIL $tag (rc=$rc)"; fail=$((fail + 1))
    fi
}

sel=("$@")
run() {  # run <tag> <env...>
    local tag=$1; shift
    if [ "${#sel[@]}" -eq 0 ] || [[ " ${sel[*]} " == *" $tag "* ]]; then
        claim_run "$tag" "$@"
    fi
}

run G5 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5
run G6 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=6

note "pricing cells done $(date +%H:%M:%S) failures=$fail"
exit "$fail"
