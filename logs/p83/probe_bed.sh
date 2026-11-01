#!/usr/bin/env bash
# P83 post-hoc mechanism probe (NOT a registered arm): F5's scenario verbatim
# plus `FRUIT_BED_DIAG=1`, which is the tree's own pure-reporting read of
# (a) the first predicate that refuses each candidate at a starved selection
# (`[bed-sel]` rows) and (b) every `fell_off` body's identity and position
# (`[bed-fall]` rows). It answers *why* the treatment's later slots starved.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
scripts/154_claim_run.sh logs/p83/probe_bed.driver \
    HEADLESS=1 ATTEMPTS=20 SEED=5 \
    FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 \
    FRUIT_FAIL_FAST=150 FRUIT_CARRY_DIAG=1 FRUIT_BED_DIAG=1 \
    bash logs/p83/one_run.sh logs/p83/probe_bed.log logs/p83/probe_bed.stamps \
    > logs/p83/probe_bed.driver.log 2>&1
echo "[p83] probe rc=$? $(date +%H:%M:%S)"
