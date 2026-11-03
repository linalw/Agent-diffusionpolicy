#!/usr/bin/env bash
# P110 - the gate fixture's cells: the height sweep, the wake control, the queue.
#
#   bash logs/p110/run_p110.sh            # every cell (~9 min)
#   bash logs/p110/run_p110.sh height 14  # one cell family
#
# One app session per cell (the gate is authored before `play()`, the P104
# driver's pattern).  Each cell runs the **whole pool** (16 fruit) singly, so a
# cell is one line per fruit; the queue cells are the same with N fruit 0.15 m
# apart, front-first.
#
# The registered cells (`logs/p110/PREREG.md` section 2): heights
# {8, 10, 12, 14, 20, 30, 45} mm - 14 is the last that clears the hand's own
# 14.5 mm (`tasks.FINGER_TIP_BELOW_JAW`), the rest bracket it; `WAKE=0` isolates
# the shipped line's own nudge (`fruits.enforce_transport` forces -0.048 m/s on
# any fruit below 0.02 m/s, which a parked fruit is); the queue {2, 4, 8}.
set -euo pipefail
cd "$(dirname "$0")/../.."

OUT=logs/p110
what=${1:-all}
shift || true

run_cell() {  # name env...
    local name=$1; shift
    local log="${OUT}/fix_${name}.log"
    if grep -q '\[p110\] DONE' "${log}" 2>/dev/null; then
        echo "=== ${name} (already complete, skipped)"
        return 0
    fi
    echo "=== ${name}: $*"
    env SKIP_SELFCHECK=1 "$@" scripts/run.sh logs/p110/fixture_gate.py > "${log}" 2>&1 || true
    grep -E '\[p110\] (summary|queue)' "${log}" || echo "  (no summary - see ${log})"
}

if [ "${what}" = "all" ] || [ "${what}" = "height" ]; then
    for h in 8 10 12 14 20 30 45; do
        run_cell "h${h}" P110_H="${h}" P110_N=1
    done
fi

if [ "${what}" = "all" ] || [ "${what}" = "wake" ]; then
    run_cell "h14_nowake" P110_H=14 P110_N=1 P110_WAKE=0
fi

if [ "${what}" = "all" ] || [ "${what}" = "queue" ]; then
    for n in 2 4 8; do
        # 1500 ticks = 12.5 s of belt travel: long enough for the stream to put
        # four fruit on the gate at the shipped 1.875 s cadence.
        run_cell "q${n}" P110_H=14 P110_N="${n}" P110_TICKS=1500
    done
fi

python3 "${OUT}/p110_report.py" > "${OUT}/fixture.txt" 2>&1 || true
tail -40 "${OUT}/fixture.txt"
