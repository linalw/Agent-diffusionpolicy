#!/bin/bash
# P21-E: the B1c CORRECTED multi-seed battery - the SINGLE-ARM patch scenario (FRUIT_BIARM=0),
# since the skip is single-arm-scoped. Arms A / B (skip+DG=0.02+RESYNC) / P (placebo HOLD=230).
cd "$(dirname "$0")/../.." || exit 1
PATCH=(FRUIT_BIARM=0 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
       FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 HEADLESS=1
       FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_READY_DIAG=1)
B=(FRUIT_READY_SKIP=1 FRUIT_READY_SKIP_DG=0.02 FRUIT_READY_SKIP_RESYNC=1)
P=(FRUIT_READY_SKIP=1 FRUIT_READY_SKIP_DG=0.02 FRUIT_READY_SKIP_RESYNC=1 FRUIT_READY_SKIP_HOLD=230)
run() { local log=$1 seed=$2; shift 2; echo "[p21e] START $(date +%H:%M:%S) $log"
    RUN_LIMIT=5400 scripts/154_claim_run.sh "$log" "${PATCH[@]}" SEED="$seed" "$@" \
        scripts/run.sh scripts/20_pick_place.py > "${log%.log}_driver.log" 2>&1
    echo "[p21e] exit=$? $(date +%H:%M:%S) $log"; return 0; }
for seed in 11 5 23; do
    run "logs/p20i/6${seed}_sa_A.log" "$seed"
    run "logs/p20i/7${seed}_sa_B.log" "$seed" "${B[@]}"
    run "logs/p20i/8${seed}_sa_P.log" "$seed" "${P[@]}"
done
echo "[p21e] DONE $(date +%H:%M:%S)"
