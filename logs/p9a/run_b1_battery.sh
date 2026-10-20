#!/bin/bash
# P19-B: the P9-A B1 battery (the frozen pre-registration logs/p9/PREREG_GOREADY_B1.md):
# the go_ready skip-when-ready lever, FRUIT_READY_SKIP=1, single-arm scope.
#   (i)  the acceptance A/B (10 attempts, FRUIT_MOTION_REPORT), double-run each arm;
#   (ii) the W6-A patch battery A/B (20 attempts, SEED 5, balanced mix), double-run each arm.
# Queued on the single simulator via the claim (interleaves with the L3/M1c chains).
cd "$(dirname "$0")/../.." || exit 1
PATCH=(FRUIT_BIARM=0 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
       FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 HEADLESS=1
       FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1)
run() {
    local log=$1; shift
    echo "[p19b] START $(date +%H:%M:%S) $log"
    RUN_LIMIT=5400 scripts/154_claim_run.sh "$log" "$@" \
        scripts/run.sh scripts/20_pick_place.py > "${log%.log}_driver.log" 2>&1
    echo "[p19b] exit=$? $(date +%H:%M:%S) $log"
    return 0
}
run logs/p9a/50_acc_A_1.log HEADLESS=1 ATTEMPTS=10 FRUIT_MOTION_REPORT=1
run logs/p9a/51_acc_A_2.log HEADLESS=1 ATTEMPTS=10 FRUIT_MOTION_REPORT=1
run logs/p9a/52_acc_B_1.log HEADLESS=1 ATTEMPTS=10 FRUIT_MOTION_REPORT=1 FRUIT_READY_SKIP=1
run logs/p9a/53_acc_B_2.log HEADLESS=1 ATTEMPTS=10 FRUIT_MOTION_REPORT=1 FRUIT_READY_SKIP=1
run logs/p9a/60_pat_A_1.log "${PATCH[@]}" SEED=5
run logs/p9a/61_pat_A_2.log "${PATCH[@]}" SEED=5
run logs/p9a/62_pat_B_1.log "${PATCH[@]}" SEED=5 FRUIT_READY_SKIP=1
run logs/p9a/63_pat_B_2.log "${PATCH[@]}" SEED=5 FRUIT_READY_SKIP=1
echo "[p19b] DONE $(date +%H:%M:%S)"
