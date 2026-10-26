#!/usr/bin/env bash
# P41 phase 1 - bracket 2: separate the **damping** term from the **second drive**.
#
#   RUN_LIMIT=2400 scripts/154_claim_run.sh logs/p41/claim_bracket2.log \
#       bash logs/p41/bracket2_cells.sh
#
# Bracket 1 showed the plateau (9.7-10.0 N) is reached at every k from 5e4 to 1e6
# *when the knob is on*, while the shipped path (k = 0 -> the override is skipped)
# delivers 4.38 N. Turning the knob on changes TWO things at once:
#   (a) `control.py:171-173` calls `set_dof_gains` on **both** finger joints, so
#       the drive-less mimic `..._finger_joint2` acquires a drive of its own;
#   (b) the damping default is 2 % of k (1000-20000 Ns/m), i.e. 10-200x the
#       asset's authored c = 100 Ns/m.
# These two cells hold the asset's own gains (k = 1e6, c = 100 - identical to
# what the USD authors) and only let the override author them on **both** joints:
#   rho_asset : k = 1e6, c = 100  (asset gains, both joints driven)
#   rho_soft  : k = 3e5, c = 100  (softer, asset damping)
# If rho_asset reads the plateau, (b) is excluded and the active term is the
# second joint's drive; if it collapses to ~4.4 N, damping is the term.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p41/sweep_bracket
BASE=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_GRIP_EFFORT=1 ATTEMPTS=2 SEED=5)
status=0

cell() {
    local name=$1 tmo=$2 log code t0
    shift 2
    log="logs/p41/sweep_bracket/${name}.log"
    echo "[p41c] START $(date +%H:%M:%S) cell=${name} tmo=${tmo}s $*"
    t0=$(date +%s)
    timeout -k 30 "$tmo" env "${BASE[@]}" "$@" scripts/run.sh scripts/20_pick_place.py \
        > "$log" 2>&1
    code=$?
    echo "[p41c] CELL ${name} exit=${code} wall=$(( $(date +%s) - t0 ))s log=${log}"
    if [ "$code" -ne 0 ] || ! grep -q '\[stats\]' "$log"; then
        echo "[p41c] FAIL ${name}"
        status=1
        return 1
    fi
    printf '%s\t%s\t%s\n' "$name" "$(( $(date +%s) - t0 ))" "$log" >> logs/p41/sweep_bracket/wall2.tsv
}

: > logs/p41/sweep_bracket/wall2.tsv
cell rho_asset 900 FRUIT_SUBSTEPS=1 FRUIT_FINGER_STIFFNESS=1000000 FRUIT_FINGER_DAMPING=100
cell rho_soft  900 FRUIT_SUBSTEPS=1 FRUIT_FINGER_STIFFNESS=300000  FRUIT_FINGER_DAMPING=100

echo "[p41c] bracket2 done status=${status} $(date +%H:%M:%S)"
exit "$status"
