#!/usr/bin/env bash
# P90 - the two challenges to the negative (`MAP.md` §5).
#
#   bash logs/p90/run_p90_robust.sh      # ~15 min, one claim at a time
#
# A. the cliff bisection: the shipped column x = 0.43, 0.01 m in y, both heights,
#    both modes that can move (`NAT` the delivered attitude, `C0` the arm's own).
# B. the re-seed: `T0` and `NAT` solved from the *calibrated place seed*
#    (`bin0_above` / `bin1_above`) with `restarts = 3` - P66's robustness B, the
#    test of "is the negative a seed artefact?".
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
RUN=${RUN:-scripts/run.sh}
CLAIM=${CLAIM:-scripts/154_claim_run.sh}

# ---- A. the cliff, 0.01 m in y -------------------------------------------------
RUN_LIMIT=${REFINE_LIMIT:-2400} "$CLAIM" logs/p90/station_map_refine.log \
    env FRUIT_P90_JSON=logs/p90/station_rows_refine.json \
        FRUIT_P90_X=0.43 \
        FRUIT_P90_Y=0.46,0.47,0.48,0.49,0.50,0.51,0.52,0.53,0.54,0.55,0.56,0.57,0.58 \
        FRUIT_P90_Z=1.450,1.530 \
        FRUIT_P90_MODES=NAT,C0 \
    "$RUN" logs/p90/station_map.py > logs/p90/driver_refine.log 2>&1
echo "[p90] refine exit=$?"

# ---- B. the re-seed from the calibrated place pose -----------------------------
for spec in "left:bin0_above" "right:bin1_above"; do
    side=${spec%%:*}
    seed=${spec##*:}
    RUN_LIMIT=${RESEED_LIMIT:-2400} "$CLAIM" "logs/p90/station_map_seed_${side}.log" \
        env FRUIT_P90_JSON="logs/p90/station_rows_seed_${side}.json" \
            FRUIT_P90_ARMS="$side" \
            FRUIT_P90_MODES=T0,NAT \
            FRUIT_P90_SEED="$seed" \
            FRUIT_P90_RESTARTS=3 \
            FRUIT_P90_X="${RESEED_X:-0.43}" \
            FRUIT_P90_Y=0.35,0.40,0.45,0.50,0.55,0.60,0.65 \
            FRUIT_P90_Z=1.450,1.530 \
        "$RUN" logs/p90/station_map.py > "logs/p90/driver_seed_${side}.log" 2>&1
    echo "[p90] reseed $side ($seed) exit=$?"
done
echo "[p90] robustness DONE"
