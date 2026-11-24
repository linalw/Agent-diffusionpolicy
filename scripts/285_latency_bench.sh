#!/usr/bin/env bash
# P228 (Stage 0 of docs/ARCHITECTURE_4T.md): the latency the **world** pays.
#
#   scripts/285_latency_bench.sh
#   D_LIST="0 4 8 16 auto" SEEDS="901 902" EPISODES=6 scripts/285_latency_bench.sh
#
# The shipped direct loop never steps the simulator while the model runs, so its
# 26 ms of inference costs zero belt travel - the metric inflation ReflexBench
# and LIBERO-Dynamic both name. `FRUIT_EVAL_LATENCY=<d>` makes the pause real:
# after a decision's inference returns, the env advances `d` control ticks with
# the arm holding still, then executes the chunk. `auto` divides this machine's
# measured `act()` wall by the control period; an integer is the sweep.
#
# **At the shipped 0.12 m/s one control tick is 1.0 mm of belt**, so `d` reads
# directly as millimetres of displacement: 4 = 4 mm (inside the 6 mm catch
# tolerance), 16 = 16 mm (2.7x it).
#
# The cell, the checkpoint and the six interface settings are whatever
# `scripts/284_single_arm_policy_gate.sh` runs; this only drives it at each `d`
# with the floor disabled (a sweep reports, it does not gate).
set -euo pipefail
cd "$(dirname "$0")/.."

D_LIST="${D_LIST:-0 2 4 8 16 auto}"
SEEDS="${SEEDS:-901 902}"
EPISODES="${EPISODES:-6}"
OUT="${OUT:-logs/p228/latency}"
mkdir -p "$OUT"

if [ "${SKIP_SELFCHECK:-0}" != "1" ]; then
    scripts/selfcheck.sh > /dev/null
fi

for d in $D_LIST; do
    for seed in $SEEDS; do
        log="$OUT/D${d}_s${seed}.log"
        echo "=== FRUIT_EVAL_LATENCY=$d seed=$seed episodes=$EPISODES -> $log"
        SINGLE_ARM_POLICY_LOG="$log" SINGLE_ARM_POLICY_DIR="$OUT" \
        FRUIT_EVAL_LATENCY="$d" \
            scripts/284_single_arm_policy_gate.sh "$EPISODES" "$seed" 0 || true
    done
done

python3 scripts/286_latency_report.py "$OUT"
