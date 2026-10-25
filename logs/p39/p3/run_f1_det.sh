#!/usr/bin/env bash
# P39 phase 3, ADDED determinism check (not a registered battery): the F1 arm's
# acceptance scenario repeated twice, print off, identical env to `accept_F1`,
# because its first pair (`accept_F1` vs `claim_f1_repeat`) did not reproduce.
# PREREG section 3 makes the second run a determinism check; this makes it three.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
OUT=logs/p39/p3
BASE=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_FINGER_TIP_DELTA=-0.004 ATTEMPTS=10 SEED=5)
status=0
for n in 2 3; do
    log=$OUT/f1_repeat$n.log
    t0=$(date +%s)
    echo "[p3] f1 repeat$n START $(date +%H:%M:%S)"
    env "${BASE[@]}" scripts/run.sh scripts/20_pick_place.py > "$log" 2>&1
    code=$?
    echo "[p3] f1 repeat$n EXIT=$code wall=$(( $(date +%s) - t0 ))s $(date +%H:%M:%S) log=$log"
    [ "$code" -eq 0 ] || status=1
done
echo "[p3] f1 determinism DONE $(date +%H:%M:%S) status=$status"
exit $status
