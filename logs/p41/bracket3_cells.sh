#!/usr/bin/env bash
# P41 phase 1 - bracket 3: the **damping threshold** at the asset's own stiffness.
#
#   RUN_LIMIT=2400 scripts/154_claim_run.sh logs/p41/claim_bracket3.log \
#       bash logs/p41/bracket3_cells.sh
#
# Bracket 2 identified the active term: `rho_asset` (both finger joints authored
# at the asset's own k = 1e6 / c = 100) is **byte-identical to the shipped cell**
# (0/102 non-instrument lines differ) and delivers the shipped 4.52/4.23 N, while
# `rho_soft` (k = 3e5, c = 100) also stays at the shipped 4.44 N. So the step is
# not the stiffness and not the second joint's drive - it is the drive's
# **damping**, which `control.py`'s default derives as 2 % of k (1000-20000 Ns/m)
# against the asset's authored 100 Ns/m.
#
# This ladder holds the asset's stiffness (k = 1e6, i.e. the least deviation from
# the asset) and moves only `FRUIT_FINGER_DAMPING`: 300 / 500 / 1000 / 2000, to
# bracket the threshold between the shipped 100 (4.4 N) and the 2 %-default 20000
# (10 N). One cell = ~72 s of wall.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p41/sweep_bracket
BASE=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_GRIP_EFFORT=1 ATTEMPTS=2 SEED=5)
status=0

cell() {
    local name=$1 tmo=$2 log code t0
    shift 2
    log="logs/p41/sweep_bracket/${name}.log"
    echo "[p41d] START $(date +%H:%M:%S) cell=${name} tmo=${tmo}s $*"
    t0=$(date +%s)
    timeout -k 30 "$tmo" env "${BASE[@]}" "$@" scripts/run.sh scripts/20_pick_place.py \
        > "$log" 2>&1
    code=$?
    echo "[p41d] CELL ${name} exit=${code} wall=$(( $(date +%s) - t0 ))s log=${log}"
    if [ "$code" -ne 0 ] || ! grep -q '\[stats\]' "$log"; then
        echo "[p41d] FAIL ${name}"
        status=1
        return 1
    fi
    printf '%s\t%s\t%s\n' "$name" "$(( $(date +%s) - t0 ))" "$log" >> logs/p41/sweep_bracket/wall3.tsv
}

: > logs/p41/sweep_bracket/wall3.tsv
cell c300  900 FRUIT_SUBSTEPS=1 FRUIT_FINGER_STIFFNESS=1000000 FRUIT_FINGER_DAMPING=300
cell c500  900 FRUIT_SUBSTEPS=1 FRUIT_FINGER_STIFFNESS=1000000 FRUIT_FINGER_DAMPING=500
cell c1000 900 FRUIT_SUBSTEPS=1 FRUIT_FINGER_STIFFNESS=1000000 FRUIT_FINGER_DAMPING=1000
cell c2000 900 FRUIT_SUBSTEPS=1 FRUIT_FINGER_STIFFNESS=1000000 FRUIT_FINGER_DAMPING=2000

echo "[p41d] bracket3 done status=${status} $(date +%H:%M:%S)"
exit "$status"
