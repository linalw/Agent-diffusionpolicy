#!/usr/bin/env bash
# P229 (Stage 1 of docs/ARCHITECTURE_4T.md): the belt-speed ladder.
#
#   scripts/288_speed_ladder.sh
#   SPEEDS="0.06 0.12 0.18" SEEDS="901" EPISODES=6 scripts/288_speed_ladder.sh
#
# The single-arm bins cell has only ever been run at 0.12 m/s (P227i-P227r).
# The lead is a **time** budget converted at the belt speed
# (`_dynamic_pick_lead` = `speed*(overhead + t_desc + descend_margin) + margin`,
# capped 0.80 m), and the direct lane's trigger lead is a **time** too
# (`TriggerSettings.lead` + the acquisition term), so both *should* scale. This
# ladder is the measurement that says whether they do - and where the cell
# breaks if they do not.
#
# Every cell runs at `FRUIT_EVAL_LATENCY=auto` (P228's conclusion: a `d=0` cell
# reports a latency the machine does not have). `auto` converts the measured
# `act()` wall into control ticks per decision, so the arm's lag in **distance**
# scales with the belt: 8 mm at 0.12 m/s, 20 mm at 0.30, against a 6 mm catch
# tolerance.
set -euo pipefail
cd "$(dirname "$0")/.."

SPEEDS="${SPEEDS:-0.06 0.12 0.18 0.24 0.30}"
SEEDS="${SEEDS:-901 902}"
EPISODES="${EPISODES:-6}"
OUT="${OUT:-logs/p229/speed}"
LATENCY="${LATENCY:-auto}"
mkdir -p "$OUT"

if [ "${SKIP_SELFCHECK:-0}" != "1" ]; then
    scripts/selfcheck.sh > /dev/null
fi

for v in $SPEEDS; do
    for seed in $SEEDS; do
        log="$OUT/V${v}_s${seed}.log"
        echo "=== FRUIT_BELT_SPEED=$v latency=$LATENCY seed=$seed -> $log"
        SINGLE_ARM_POLICY_LOG="$log" SINGLE_ARM_POLICY_DIR="$OUT" \
        FRUIT_BELT_SPEED="$v" \
        FRUIT_EVAL_LATENCY="$LATENCY" \
            scripts/284_single_arm_policy_gate.sh "$EPISODES" "$seed" 0 || true
    done
done

python3 scripts/289_speed_report.py "$OUT"
