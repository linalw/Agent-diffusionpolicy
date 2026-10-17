#!/bin/bash
# P11-C.2: the acceptance no-harm + the from-open + chase-stop B runs (seeds 11/5/23).
cd "$(dirname "$0")/../.." || exit 1
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
     FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 HEADLESS=1
     FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1)
B=(FRUIT_DYNAMIC_REGRASP_FROM_OPEN=1 FRUIT_FORCE_REENTRY=1)
# wait for the plow-fix chain (bracket-safe pattern)
while pgrep -f "[r]un_plow_fix.sh" >/dev/null 2>&1; do sleep 30; done
echo "[c2] plow-fix gone; acceptance $(date +%H:%M:%S)"
scripts/accept.sh > logs/p11c/70_accept_noharm.log 2>&1
echo "[c2] accept exit=$? $(date +%H:%M:%S)"
run() {
    local log=$1 seed=$2; shift 2
    echo "[c2] START $(date +%H:%M:%S) $log"
    RUN_LIMIT=5400 scripts/154_claim_run.sh "$log" "${TWO[@]}" SEED="$seed" "$@" \
        scripts/run.sh scripts/20_pick_place.py > "${log%.log}_driver.log" 2>&1
    echo "[c2] exit=$? $(date +%H:%M:%S) $log"
    return 0
}
run logs/p11c/41_seed11_B2.log 11 "${B[@]}"
run logs/p11c/43_seed5_B2.log 5 "${B[@]}"
run logs/p11c/45_seed23_B2.log 23 "${B[@]}"
echo "[c2] DONE $(date +%H:%M:%S)"
