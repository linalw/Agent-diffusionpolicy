#!/usr/bin/env bash
# P41 phase 1 - the finger-drive fidelity sweep: 8 cells, one simulator claim.
#
#   RUN_LIMIT=6600 scripts/154_claim_run.sh logs/p41/claim_sweep.log \
#       bash logs/p41/sweep_cells.sh
#
# Contract: this script runs *inside* the claim (154_claim_run.sh has the single
# simulator), so it never re-claims and never releases the slot between cells -
# the whole sweep is one exclusive block. One cell = one `20_pick_place` run on
# the acceptance scenario (ATTEMPTS=2, SEED=5) with the committed default-off
# `FRUIT_GRIP_EFFORT=1` instrument on, logged to `logs/p41/sweep/<cell>.log`.
#
# Grid: FRUIT_SUBSTEPS in {1, 4} x FRUIT_FINGER_STIFFNESS in {0 (the asset's
# authored k), 300000, 100000, 50000}. `FRUIT_FINGER_DAMPING` is left unset so
# control.py's own default (2 % of k = 6000/2000/1000 Ns/m) applies.
#
# A cell that wedges (non-zero exit, or no `[stats]` line) is retried **once**:
# the first attempt stays on disk as `<cell>.log`, the retry is
# `<cell>.retry.log`, and both are named in the claim log.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p41/sweep
BASE=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_GRIP_EFFORT=1 ATTEMPTS=2 SEED=5)
status=0

alive() { pgrep -f '[p]ython.sh' >/dev/null 2>&1; }

wait_idle() {  # wait_idle <seconds>: never start a cell behind a stuck process
    local i=0
    while alive && [ "$i" -lt "$1" ]; do sleep 5; i=$((i + 5)); done
    if alive; then
        echo "[p41] WARN a python.sh is still alive after $1s; continuing"
        return 1
    fi
    return 0
}

one_run() {  # one_run <log> <timeout> <env...> -> sets RUN_CODE / RUN_WALL
    local log=$1 tmo=$2 t0 t1
    shift 2
    t0=$(date +%s)
    timeout -k 30 "$tmo" env "${BASE[@]}" "$@" scripts/run.sh scripts/20_pick_place.py \
        > "$log" 2>&1
    RUN_CODE=$?
    t1=$(date +%s)
    RUN_WALL=$((t1 - t0))
}

cell() {  # cell <name> <timeout> <env...>
    local name=$1 tmo=$2 log ok=0
    shift 2
    log="logs/p41/sweep/${name}.log"
    echo "[p41] START $(date +%H:%M:%S) cell=${name} tmo=${tmo}s $*"
    one_run "$log" "$tmo" "$@"
    if [ "$RUN_CODE" -eq 0 ] && grep -q '\[stats\]' "$log"; then
        ok=1
    fi
    echo "[p41] CELL ${name} attempt=1 exit=${RUN_CODE} wall=${RUN_WALL}s ok=${ok} log=${log}"
    if [ "$ok" -eq 0 ]; then
        echo "[p41] RETRY ${name} (attempt 1 exit=${RUN_CODE}, $(grep -c '\[stats\]' "$log" 2>/dev/null || echo 0) stats rows)"
        wait_idle 180
        one_run "logs/p41/sweep/${name}.retry.log" "$tmo" "$@"
        if [ "$RUN_CODE" -eq 0 ] && grep -q '\[stats\]' "logs/p41/sweep/${name}.retry.log"; then
            ok=1
            log="logs/p41/sweep/${name}.retry.log"
        fi
        echo "[p41] CELL ${name} attempt=2 exit=${RUN_CODE} wall=${RUN_WALL}s ok=${ok} log=${log}"
    fi
    if [ "$ok" -eq 0 ]; then
        echo "[p41] FAIL ${name} (both attempts)"
        status=1
        return 1
    fi
    printf '%s\t%s\t%s\n' "$name" "$RUN_WALL" "$log" >> logs/p41/sweep/wall.tsv
    wait_idle 120
    return 0
}

wait_idle 300
: > logs/p41/sweep/wall.tsv

# ---- the stiffness ladder at the shipped physics rate -------------------- #
cell sub1_k0      900 FRUIT_SUBSTEPS=1
cell sub1_k300000 900 FRUIT_SUBSTEPS=1 FRUIT_FINGER_STIFFNESS=300000
cell sub1_k100000 900 FRUIT_SUBSTEPS=1 FRUIT_FINGER_STIFFNESS=100000
cell sub1_k50000  900 FRUIT_SUBSTEPS=1 FRUIT_FINGER_STIFFNESS=50000

# ---- the same ladder at the 480 Hz rate (P40's force lever) -------------- #
cell sub4_k0      1500 FRUIT_SUBSTEPS=4
cell sub4_k300000 1500 FRUIT_SUBSTEPS=4 FRUIT_FINGER_STIFFNESS=300000
cell sub4_k100000 1500 FRUIT_SUBSTEPS=4 FRUIT_FINGER_STIFFNESS=100000
cell sub4_k50000  1500 FRUIT_SUBSTEPS=4 FRUIT_FINGER_STIFFNESS=50000

echo "[p41] sweep done status=${status} $(date +%H:%M:%S)"
exit "$status"
