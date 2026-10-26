#!/usr/bin/env bash
# P42 phase 2 driver: the bounded pre-close centring (`FRUIT_SEAT_CENTRE=0.010`).
# Two claimed runs, sequential, one claim at a time (logs/p42/PREREG.md section 7):
#   1. the species-locked pear battery (the primary)  -> pear_centre010.log
#   2. the acceptance no-harm pair (P5)               -> accept_centre010.log
# Controls (phase 1, same tree, knob unset): logs/p42/p2/seat_pear.log and
# logs/p42/p2/seat_accept.log (both instrumented identically: SEAT_DIAG + CARRY_DIAG).
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1

echo "$(date +%FT%T) [p3] start"

scripts/154_claim_run.sh logs/p42/p3/pear_centre010.log \
    ATTEMPTS=10 SEED=5 FRUIT_SUPPLY_SPECIES=pear \
    FRUIT_SEAT_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_MOTION_REPORT=1 \
    FRUIT_SEAT_CENTRE=0.010 \
    scripts/run.sh scripts/20_pick_place.py
echo "$(date +%FT%T) [p3] pear_centre010 done"

scripts/154_claim_run.sh logs/p42/p3/accept_centre010.log \
    ATTEMPTS=10 SEED=5 \
    FRUIT_SEAT_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_MOTION_REPORT=1 \
    FRUIT_SEAT_CENTRE=0.010 \
    scripts/run.sh scripts/20_pick_place.py
echo "$(date +%FT%T) [p3] accept_centre010 done"

echo "$(date +%FT%T) [p3] all done"
