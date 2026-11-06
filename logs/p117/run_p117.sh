#!/usr/bin/env bash
# P117 - both fixtures, end to end.  Offline (no arm, no attempt loop).
#
#   bash logs/p117/run_p117.sh          # ~4 min: 1 pad session + 5 station sessions
#   bash logs/p117/run_p117.sh pad      # fixture 1 only (~3 min)
#   bash logs/p117/run_p117.sh station  # fixture 2 only (~2 min)
#
# The station cells are run one mode per app session because the pocket, the
# shutter and the belt are authored before `play()`.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$ROOT"
which=${1:-all}

if [ "$which" = "all" ] || [ "$which" = "pad" ]; then
    echo "[p117] fixture 1 - the pad face"
    scripts/run.sh logs/p117/fixture.py > logs/p117/fixture1.log 2>&1
    tail -40 logs/p117/fixture1.log
fi

if [ "$which" = "all" ] || [ "$which" = "station" ]; then
    for mode in support closed drop stream; do
        echo "[p117] fixture 2 - $mode"
        P117_S_MODE=$mode scripts/run.sh logs/p117/fixture_station.py \
            > "logs/p117/st_${mode}.log" 2>&1
        grep -E "\[p117s\]" "logs/p117/st_${mode}.log" | tail -4
    done
    echo "[p117] fixture 2 - the fast cadence (closed shutter)"
    P117_S_MODE=closed P117_S_CADENCE=0.833 scripts/run.sh logs/p117/fixture_station.py \
        > logs/p117/st_closed_fast.log 2>&1
    grep -E "\[p117s\] closed" logs/p117/st_closed_fast.log
fi

echo "[p117] the tables"
python3 logs/p117/p117_report.py
