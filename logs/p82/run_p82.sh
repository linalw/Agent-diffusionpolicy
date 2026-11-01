#!/usr/bin/env bash
# P82 stage 1: the four profile cells (one simulator, claimed one at a time).
#
#   bash logs/p82/run_p82.sh
#
# R1 two-line + I2 arbiter timers   R2 single arm + I2 (inert)
# R3 two-line + I1 py-spy           R4 single arm + I1
#
# Every cell is 20 attempts at seed 5 - P80's S20/T20 cell verbatim - so the wall
# column is the same measurement P80 published, and each run's `[fruit]` stream is
# checked against the canonical record (logs/p80/{S20,T20}.log).
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
export HEADLESS=1 ATTEMPTS=${ATTEMPTS:-20} SEED=${SEED:-5}
export FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
MINE="FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1"

echo "[p82] === R1 two-line + I2 timers $(date +%H:%M:%S) ==="
scripts/154_claim_run.sh logs/p82/R1.driver $MINE \
    P82_TIMERS=logs/p82/R1.timers.json \
    bash logs/p82/one_run.sh logs/p82/R1.log logs/p82/R1.stamps logs/p82/profile_20.py
echo "[p82] R1 exit=$? $(date +%H:%M:%S)"

echo "[p82] === R2 single arm + I2 timers (inert) $(date +%H:%M:%S) ==="
scripts/154_claim_run.sh logs/p82/R2.driver \
    P82_TIMERS=logs/p82/R2.timers.json \
    bash logs/p82/one_run.sh logs/p82/R2.log logs/p82/R2.stamps logs/p82/profile_20.py
echo "[p82] R2 exit=$? $(date +%H:%M:%S)"

echo "[p82] === R3 two-line + I1 py-spy $(date +%H:%M:%S) ==="
scripts/154_claim_run.sh logs/p82/R3.driver $MINE \
    P82_PSPY=logs/p82/R3.speedscope.json \
    P82_LAUNCH='bash logs/p82/run_pyspy.sh' \
    bash logs/p82/one_run.sh logs/p82/R3.log logs/p82/R3.stamps
echo "[p82] R3 exit=$? $(date +%H:%M:%S)"

echo "[p82] === R4 single arm + I1 py-spy $(date +%H:%M:%S) ==="
scripts/154_claim_run.sh logs/p82/R4.driver \
    P82_PSPY=logs/p82/R4.speedscope.json \
    P82_LAUNCH='bash logs/p82/run_pyspy.sh' \
    bash logs/p82/one_run.sh logs/p82/R4.log logs/p82/R4.stamps
echo "[p82] R4 exit=$? $(date +%H:%M:%S)"

echo "[p82] stage 1 done $(date +%H:%M:%S)"
