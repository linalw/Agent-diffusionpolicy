#!/bin/bash
# P25-A: the Gate-5 2.6 decisive block (7 runs): endpoint 1 (seed 5: A/B/P + supply diag) +
# endpoint 4 (seeds 11/23: A/B). The decision rule is frozen in logs/p24/ORACLE_GATE5.md 2.6.
cd "$(dirname "$0")/../.." || exit 1
ACC=(HEADLESS=1 ATTEMPTS=10 FRUIT_MOTION_REPORT=1 FRUIT_READY_DIAG=1 FRUIT_SUPPLY_DIAG=1)
B=(FRUIT_READY_SKIP=1 FRUIT_READY_SKIP_DG=0.02 FRUIT_READY_SKIP_RESYNC=1)
P=(FRUIT_READY_SKIP=1 FRUIT_READY_SKIP_DG=0.02 FRUIT_READY_SKIP_RESYNC=1 FRUIT_READY_SKIP_HOLD=230)
run() { local log=$1 seed=$2; shift 2; echo "[p25a] START $(date +%H:%M:%S) $log"
    RUN_LIMIT=3600 scripts/154_claim_run.sh "$log" "${ACC[@]}" SEED="$seed" "$@" \
        scripts/run.sh scripts/20_pick_place.py > "${log%.log}_driver.log" 2>&1
    echo "[p25a] exit=$? $(date +%H:%M:%S) $log"; return 0; }
run logs/p20i/a2_acc_s5_A.log 5
run logs/p20i/a3_acc_s5_B.log 5 "${B[@]}"
run logs/p20i/a4_acc_s5_P.log 5 "${P[@]}"
run logs/p20i/a5_acc_s11_A.log 11
run logs/p20i/a6_acc_s11_B.log 11 "${B[@]}"
run logs/p20i/a7_acc_s23_A.log 23
run logs/p20i/a8_acc_s23_B.log 23 "${B[@]}"
echo "[p25a] DONE $(date +%H:%M:%S)"
