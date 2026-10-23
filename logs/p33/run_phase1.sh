#!/usr/bin/env bash
# P33 phase 1: the bed's delivered density at the shipped cadence.
# One simulator at a time via scripts/154_claim_run.sh; every run logs to
# logs/p33/<name>.log and its claim_run timestamps to <name>.driver.log
# (claimed HH:MM:SS -> exit HH:MM:SS is the wall row).
#
#   1. the shipped acceptance (10 attempts, no knobs): the byte-identity leg
#   2. the two-line bed control (A0's env, FRUIT_FEED_CADENCE unset)
#   3. the two-line bed + mid-attempt pump (A0's env + FRUIT_FEED_CADENCE=1)
#   4. the single-arm bed control (10 attempts)
#   5. the single-arm bed + cadence (the recorded phase-A M2 pair, re-measured)
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p33

run() {
    local name=$1; shift
    echo "=== ${name} start $(date +%H:%M:%S) ==="
    scripts/154_claim_run.sh "logs/p33/${name}.log" "$@" \
        2>&1 | tee "logs/p33/${name}.driver.log"
    echo "=== ${name} claim_run exit=${PIPESTATUS[0]} $(date +%H:%M:%S) ==="
}

# 1. shipped acceptance (same command scripts/accept.sh uses; gate run after).
run 00_accept_shipped \
    HEADLESS=1 FRUIT_MOTION_REPORT=1 ATTEMPTS=10 \
    scripts/run.sh scripts/20_pick_place.py

# 2. two-line bed control: A0's exact scenario, the P33 hook unset.
run 10_twoline_control \
    FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_BED=1 ATTEMPTS=20 SEED=5 \
    FRUIT_BED_DIAG=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 HEADLESS=1 \
    scripts/run.sh scripts/20_pick_place.py

# 3. two-line bed + the mid-attempt pump: the same scenario + the knob.
run 11_twoline_pump \
    FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_BED=1 ATTEMPTS=20 SEED=5 \
    FRUIT_BED_DIAG=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 HEADLESS=1 \
    FRUIT_FEED_CADENCE=1 \
    scripts/run.sh scripts/20_pick_place.py

# 4. single-arm bed control (the phase-A 87 env: boundary cadence).
run 20_single_control \
    FRUIT_SUPPLY_BED=1 ATTEMPTS=10 SEED=5 FRUIT_BED_DIAG=1 HEADLESS=1 \
    scripts/run.sh scripts/20_pick_place.py

# 5. single-arm bed + cadence (the phase-A M2 arm).
run 21_single_cadence \
    FRUIT_SUPPLY_BED=1 ATTEMPTS=10 SEED=5 FRUIT_BED_DIAG=1 HEADLESS=1 \
    FRUIT_FEED_CADENCE=1 \
    scripts/run.sh scripts/20_pick_place.py

echo "=== phase1 battery done $(date +%H:%M:%S) ==="
