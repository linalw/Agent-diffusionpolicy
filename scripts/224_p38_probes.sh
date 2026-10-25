#!/usr/bin/env bash
# P38 phase 2 step 1: the H2 supply verification for the forced/mixed bands.
#
#   bash scripts/224_p38_probes.sh
#
# `logs/p38/PREREG_A1.md` A2: the M1/M2 bands are spawn bands, but the trigger
# sees the **delivered** x = spawn + a fixed per-instance settle offset
# (-35.9..+69.2 mm, `logs/p38/P1_RESULTS.md` section 2), so "forced" and
# "19 % refused" are claims about the delivered distribution and must be
# measured before the batch. Three claimed runs, all SEED=5, free cadence:
#
#   1. `171_supply_probe.py` at the M1 band (0.13-0.17) - the lateral envelope
#      against the belt's 0.11-0.57, the on-belt density and the stacked count;
#   2. `171_supply_probe.py` at the M2 band (0.13-0.36) - the same envelope;
#   3. `logs/p38/probe_drift.py` at the M1 band - its `delivery edge` row is
#      the delivered-x census (`n<0.173`) and, at a forced band, its out-of-band
#      list names every transit with spawn x and class.
#
# The registered rule: M1 counts as *forced* iff the delivered max < 0.170 (the
# right arm's 0.1730 floor with 3 mm slack) and the delivered min > 0.115 (the
# belt edge 0.11 + 5 mm). If the delivered max >= 0.170 the M1 upper bound drops
# to 0.16 and the probe repeats once; a second leak restates M1's population as
# the diag-note episodes.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/p38

probe_supply() {
    local tag=$1 lo=$2 hi=$3
    RUN_LIMIT=1800 scripts/154_claim_run.sh "logs/p38/z1_supply_${tag}.log" \
        SEED=5 FRUIT_SUPPLY_SCATTER=1 \
        FRUIT_SUPPLY_X_MIN="$lo" FRUIT_SUPPLY_X_MAX="$hi" \
        FRUIT_SUPPLY_PROBE_CADENCE=free \
        scripts/run.sh scripts/171_supply_probe.py
    echo "[p38probe] ${tag} exit=$?"
    grep -E "\[supply\] lateral x:|\[supply\] density:" "logs/p38/z1_supply_${tag}.log"
}

probe_supply m1 0.13 0.17
probe_supply m2 0.13 0.36

RUN_LIMIT=1800 scripts/154_claim_run.sh logs/p38/z2_drift_m1.log \
    SEED=5 FRUIT_SUPPLY_X_MIN=0.13 FRUIT_SUPPLY_X_MAX=0.17 \
    FRUIT_DRIFT_ARMS=none scripts/run.sh logs/p38/probe_drift.py
echo "[p38probe] drift m1 exit=$?"
grep -E "\[drift\] delivery edge|out of band at delivery" logs/p38/z2_drift_m1.log
echo "[p38probe] done $(date +%H:%M:%S)"
