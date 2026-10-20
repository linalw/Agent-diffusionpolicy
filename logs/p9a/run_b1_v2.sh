#!/bin/bash
# P19-B.1: the B1 v2 battery (the frozen prereg + the DG calibration addendum + the placebo arm).
# Arms: A shipped / B skip DG=0.02 / P skip+HOLD=230; the acceptance (10 attempts) and the
# patch battery (20, SEED 5), each double-run. 12 runs via the claim.
cd "$(dirname "$0")/../.." || exit 1
PATCH=(FRUIT_BIARM=0 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
       FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 HEADLESS=1
       FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1)
B=(FRUIT_READY_SKIP=1 FRUIT_READY_SKIP_DG=0.02)
P=(FRUIT_READY_SKIP=1 FRUIT_READY_SKIP_DG=0.02 FRUIT_READY_SKIP_HOLD=230)
run() {
    local log=$1; shift
    echo "[p19b2] START $(date +%H:%M:%S) $log"
    RUN_LIMIT=5400 scripts/154_claim_run.sh "$log" "$@" \
        scripts/run.sh scripts/20_pick_place.py > "${log%.log}_driver.log" 2>&1
    echo "[p19b2] exit=$? $(date +%H:%M:%S) $log"
    return 0
}
# --- the acceptance scenario ---
run logs/p9a/90_acc_A_1.log HEADLESS=1 ATTEMPTS=10 FRUIT_MOTION_REPORT=1
run logs/p9a/91_acc_B_1.log HEADLESS=1 ATTEMPTS=10 FRUIT_MOTION_REPORT=1 "${B[@]}"
run logs/p9a/92_acc_P_1.log HEADLESS=1 ATTEMPTS=10 FRUIT_MOTION_REPORT=1 "${P[@]}"
run logs/p9a/93_acc_A_2.log HEADLESS=1 ATTEMPTS=10 FRUIT_MOTION_REPORT=1
run logs/p9a/94_acc_B_2.log HEADLESS=1 ATTEMPTS=10 FRUIT_MOTION_REPORT=1 "${B[@]}"
run logs/p9a/95_acc_P_2.log HEADLESS=1 ATTEMPTS=10 FRUIT_MOTION_REPORT=1 "${P[@]}"
# --- the patch battery ---
run logs/p9a/96_pat_A_1.log "${PATCH[@]}" SEED=5
run logs/p9a/97_pat_B_1.log "${PATCH[@]}" SEED=5 "${B[@]}"
run logs/p9a/98_pat_P_1.log "${PATCH[@]}" SEED=5 "${P[@]}"
run logs/p9a/99_pat_A_2.log "${PATCH[@]}" SEED=5
run logs/p9a/9a_pat_B_2.log "${PATCH[@]}" SEED=5 "${B[@]}"
run logs/p9a/9b_pat_P_2.log "${PATCH[@]}" SEED=5 "${P[@]}"
echo "[p19b2] DONE $(date +%H:%M:%S)"
