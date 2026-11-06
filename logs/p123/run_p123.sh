#!/usr/bin/env bash
# P123 battery: the third output body's cell (one claim per run).
#
#   bash logs/p123/run_p123.sh              # all four cells, sequential (~25 min)
#   bash logs/p123/run_p123.sh C5 T5        # a subset (the pair first)
#
# PREREG: logs/p123/PREREG.md (md5 in logs/p123/PREREG.md5), pinned before any
# cell. Cells (20 attempts, the shipped scripted two-line), one seed each:
#
#   C5  seed 5, the shipped scene             the control (replays logs/p92/C5.log)
#   T5  seed 5, FRUIT_OUTPUT_LANES=3 + the descriptor + the instruction
#   C6  seed 6, the shipped scene             the second-seed control
#   T6  seed 6, the treatment
#
# The instrumentation is P92's four (`FRUIT_MOTION_REPORT FRUIT_CYCLE_REPORT
# FRUIT_CARRY_DIAG FRUIT_PLACE_TRACE`) on every arm, so the landing guard, the
# clearance guard and the class census come from the same rows in every cell.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p123

RUN=${RUN:-scripts/run.sh}
CLAIM=${CLAIM:-scripts/154_claim_run.sh}
ENV_COMMON=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
            FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1)
TREAT=(FRUIT_OUTPUT_LANES=3
       FRUIT_SCENARIO=logs/p123/three_dest.json
       FRUIT_SORT_INSTRUCTION=logs/p123/three_dest.txt)

cells=("$@")
if [ "${#cells[@]}" -eq 0 ]; then
    cells=(C5 T5 C6 T6)
fi

for cell in "${cells[@]}"; do
    case "$cell" in
        C5) seed=5; extra=() ;;
        T5) seed=5; extra=("${TREAT[@]}") ;;
        C6) seed=6; extra=() ;;
        T6) seed=6; extra=("${TREAT[@]}") ;;
        *) echo "[p123] unknown cell $cell" >&2; exit 2 ;;
    esac
    if [ -s "logs/p123/${cell}.log" ]; then
        echo "[p123] ${cell}: exists, skipped"
        continue
    fi
    echo "[p123] ${cell}: seed ${seed} ${extra[*]}"
    RUN_LIMIT=${RUN_LIMIT:-1500} "$CLAIM" "logs/p123/${cell}.driver" \
        env "${ENV_COMMON[@]}" SEED="$seed" ATTEMPTS=20 "${extra[@]}" \
        bash logs/p123/one_run.sh "logs/p123/${cell}.log" "logs/p123/${cell}.stamps"
    echo "[p123] ${cell}: exit=$? $(grep -ac '^\[fruit\]' "logs/p123/${cell}.log" 2>/dev/null) [fruit] lines"
done

python3 logs/p123/p123_report.py --cells "${cells[@]}" > logs/p123/p123_report.txt 2>&1
echo "[p123] wrote logs/p123/p123_report.txt"
