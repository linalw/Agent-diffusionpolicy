#!/usr/bin/env bash
# P41 phase 1 - the **post-hoc bracket** around the 8-cell sweep's force step.
#
#   RUN_LIMIT=2400 scripts/154_claim_run.sh logs/p41/claim_bracket.log \
#       bash logs/p41/bracket_cells.sh
#
# The 8-cell sweep reads a **step**, not a curve: the shipped gain (k = 1e6 on
# joint1 only) delivers 4.38 N, and every softer cell (3e5 / 1e5 / 5e4, which the
# runtime read-back shows also gives the mimic joint2 a drive) delivers
# 9.7-10.0 N. Nothing brackets the step, and nothing tests the regime where the
# authored law's own `k*err` falls below the 10 N cap (k <= ~2e3 N/m at a ~4 mm
# error). These three cells do that, on the same acceptance scenario and the same
# 120 Hz physics, so they are directly comparable with the sweep's sub1 group:
#
#   k=500000 / 700000 - bracket the step between 3e5 and the asset's 1e6;
#   k=1000           - the sub-cap regime (authored k*err ~ 4 N < the 10 N cap),
#                      i.e. "does the plateau follow the drive law or the cap?".
#
# Post-hoc diagnostic: reported in a separate table, never mixed into the
# pre-registered 8-cell grid.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p41/sweep_bracket
BASE=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_GRIP_EFFORT=1 ATTEMPTS=2 SEED=5)
status=0

cell() {  # cell <name> <timeout> <env...>
    local name=$1 tmo=$2 log code t0
    shift 2
    log="logs/p41/sweep_bracket/${name}.log"
    echo "[p41b] START $(date +%H:%M:%S) cell=${name} tmo=${tmo}s $*"
    t0=$(date +%s)
    timeout -k 30 "$tmo" env "${BASE[@]}" "$@" scripts/run.sh scripts/20_pick_place.py \
        > "$log" 2>&1
    code=$?
    echo "[p41b] CELL ${name} exit=${code} wall=$(( $(date +%s) - t0 ))s log=${log}"
    if [ "$code" -ne 0 ] || ! grep -q '\[stats\]' "$log"; then
        echo "[p41b] FAIL ${name}"
        status=1
        return 1
    fi
    printf '%s\t%s\t%s\n' "$name" "$(( $(date +%s) - t0 ))" "$log" >> logs/p41/sweep_bracket/wall.tsv
}

: > logs/p41/sweep_bracket/wall.tsv
cell k500000 900 FRUIT_SUBSTEPS=1 FRUIT_FINGER_STIFFNESS=500000
cell k700000 900 FRUIT_SUBSTEPS=1 FRUIT_FINGER_STIFFNESS=700000
cell k1000   900 FRUIT_SUBSTEPS=1 FRUIT_FINGER_STIFFNESS=1000

echo "[p41b] bracket done status=${status} $(date +%H:%M:%S)"
exit "$status"
