#!/usr/bin/env bash
# P90 - the place-station map: the main grid, then the robustness pass.
#
#   bash logs/p90/run_p90.sh            # the whole phase (~50 min, one claim at a time)
#
# `scripts/154_claim_run.sh` owns the single-simulator contract; nothing here polls
# for a claim or overlaps a lane.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

RUN=${RUN:-scripts/run.sh}
CLAIM=${CLAIM:-scripts/154_claim_run.sh}

# ---- 1. the main grid: 7 x 7 (x, y) x 2 heights x 2 arms x 3 modes = 588 cells ----
RUN_LIMIT=${RUN_LIMIT:-7200} "$CLAIM" logs/p90/station_map.log \
    env FRUIT_P90_JSON=logs/p90/station_rows.json \
    "$RUN" logs/p90/station_map.py > logs/p90/driver.log 2>&1
echo "[p90] main grid exit=$?"

# ---- 2. the cliff bisection: the best NAT row, 0.01 m in y, both arms ----
# `FRUIT_P90_*` is supplied by the caller once MAP.md names the row (a second
# pass is a different grid, not a rerun of this one).
if [ -n "${P90_REFINE_X:-}" ]; then
    RUN_LIMIT=${REFINE_LIMIT:-2400} "$CLAIM" logs/p90/station_map_refine.log \
        env FRUIT_P90_JSON=logs/p90/station_rows_refine.json \
            FRUIT_P90_X="${P90_REFINE_X}" \
            FRUIT_P90_Y="${P90_REFINE_Y}" \
            FRUIT_P90_Z="${P90_REFINE_Z}" \
            FRUIT_P90_MODES="${P90_REFINE_MODES:-NAT}" \
            FRUIT_P90_ARMS="${P90_REFINE_ARMS:-left,right}" \
        "$RUN" logs/p90/station_map.py > logs/p90/driver_refine.log 2>&1
    echo "[p90] refine exit=$?"
fi

# ---- 3. the robustness re-solve from the calibrated place seed ----
for spec in "left:bin0_above" "right:bin1_above"; do
    side=${spec%%:*}
    seed=${spec##*:}
    RUN_LIMIT=${ROB_LIMIT:-2400} "$CLAIM" "logs/p90/station_map_seed_${side}.log" \
        env FRUIT_P90_JSON="logs/p90/station_rows_seed_${side}.json" \
            FRUIT_P90_ARMS="$side" \
            FRUIT_P90_MODES="${P90_SEED_MODES:-T0}" \
            FRUIT_P90_SEED="$seed" \
            FRUIT_P90_RESTARTS="${P90_SEED_RESTARTS:-3}" \
            FRUIT_P90_X="${P90_SEED_X:-0.43}" \
            FRUIT_P90_Y="${P90_SEED_Y:-0.35,0.45,0.50,0.55,0.65}" \
            FRUIT_P90_Z="${P90_SEED_Z:-1.450,1.530}" \
        "$RUN" logs/p90/station_map.py > "logs/p90/driver_seed_${side}.log" 2>&1
    echo "[p90] seed $side ($seed) exit=$?"
done

# ---- 4. the report ----
grep -a '\[p90\]' logs/p90/station_map.log | sed 's/^\[fruit\] //' \
    > logs/p90/station_map.txt
python3 logs/p90/cost_map.py --check > logs/p90/cost_map.txt 2>&1
echo "[p90] wrote logs/p90/{station_map.txt,cost_map.txt}"
