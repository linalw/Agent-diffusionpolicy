#!/usr/bin/env bash
# W8-R3.4 belt-speed screen: the W6-B patch battery at 0.12/0.15/0.18 m/s.
#
#   nohup bash scripts/194_r3_belt.sh > logs/w8/R3_belt_driver.log 2>&1 &
#
# The 0.12 m/s reference already exists (`logs/w8/R3_l2_control.log`, the W7-A
# branch replay); this script runs the two higher speeds. Scenario otherwise
# identical to the battery (patch sheet, 20 attempts, seed 5, HEADLESS=1,
# two-line opt-in, balanced mix, Tier A solo). Each config is one branch - the
# screen names where arrivals stop limiting (per-leg catch metrics + the
# interval/rate + the failure classes), not a rate delta across branches.
#
# Outputs: logs/w8/R3_belt_015.log, R3_belt_018.log, R3_belt_report.txt,
# R3_belt_compare.txt.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/w8

BASE=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 ATTEMPTS=20 SEED=5)
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1)
PATCH=(FRUIT_SUPPLY_PATCH=1)

status=0
run() {
    local log=$1 limit=$2 code
    shift 2
    echo "[r3-belt] START $(date +%H:%M:%S) $log $*"
    RUN_LIMIT="$limit" scripts/154_claim_run.sh "$log" "${BASE[@]}" "$@" \
        scripts/run.sh scripts/20_pick_place.py
    code=$?
    echo "[r3-belt] exit=$code $(date +%H:%M:%S) $log"
    if [ "$code" -ne 0 ] || [ ! -s "$log" ]; then
        echo "[r3-belt] FAIL log=$log exit=$code"; status=1
    fi
}

run logs/w8/R3_belt_015.log 7200 "${TWO[@]}" "${PATCH[@]}" FRUIT_BELT_SPEED=0.15
run logs/w8/R3_belt_018.log 7200 "${TWO[@]}" "${PATCH[@]}" FRUIT_BELT_SPEED=0.18

[ "$status" -ne 0 ] && { echo "[r3-belt] incomplete"; exit 1; }

echo "[r3-belt] report"
python3 scripts/186_w6_report.py --label r3-belt \
    logs/w8/R3_l2_control.log logs/w8/R3_belt_015.log logs/w8/R3_belt_018.log \
    | tee logs/w8/R3_belt_report.txt
[ "${PIPESTATUS[0]}" -ne 0 ] && status=1

{
    echo "# W8-R3.4 belt-speed screen (patch sheet, 20 attempts, seed 5)"
    for f in R3_l2_control:R3_belt_015:R3_belt_018; do :; done
    for spec in "0.12 logs/w8/R3_l2_control.log" "0.15 logs/w8/R3_belt_015.log" \
                "0.18 logs/w8/R3_belt_018.log"; do
        set -- $spec
        echo "== belt $1 m/s ($2)"
        grep -e "\[biarm\] [0-9]* pipelined slots" "$2" | tail -1
        grep -e "\[stats\] attempts" "$2" | tail -1
        grep -e "\[biarm\] result" "$2" | grep -oE "grasped=False|placed=False|notes=\[[^]]*\]" \
            | sort | uniq -c | sort -rn | head -8
        grep -e "gate_open" "$2" | tail -1
    done
} | tee logs/w8/R3_belt_compare.txt

echo "[r3-belt] done $(date +%H:%M:%S) status=$status"
exit "$status"
