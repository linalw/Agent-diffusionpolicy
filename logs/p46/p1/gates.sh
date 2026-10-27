#!/usr/bin/env bash
# P46 phase 1 gates: the two-line gate (per-scenario reference + the 0.60 floor)
# and the strict-cone report on every arm.
#
#   bash logs/p46/p1/gates.sh > logs/p46/p1/gates.txt
#
# `190` is the gate of record for a two-line log (105's own 0.75 floor is the
# single-arm calibration). `--strict-cone` is a REPORT here: it fails on this
# scenario's control too (P44 section 9.3), so the arm-vs-control leg count is
# the read, never an absolute pass.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
OUT=logs/p46/p1

echo "# P46 phase 1 gates ($(date '+%F %T')) tree $(git rev-parse HEAD)"
echo
for seed in 5 6; do
    for arm in C U; do
        log="$OUT/twoline_s${seed}_${arm}.log"
        echo "=== 190 seed $seed $arm"
        scripts/190_twoline_gate.sh "$log" 2>&1
        echo
    done
done

echo "=== 105 --strict-cone (relative report only)"
for seed in 5 6; do
    for arm in C U; do
        log="$OUT/twoline_s${seed}_${arm}.log"
        echo "--- seed $seed $arm"
        python3 scripts/105_motion_regression.py "$log" --strict-cone \
            --min-success-rate 0.0 2>&1 | grep -E "worst|hand speed|success|cone|leg\(s\) over"
        echo
    done
done
