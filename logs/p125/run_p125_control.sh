#!/usr/bin/env bash
# P125 amendment A2: the same-batch **two-lane** control (report only).
#
#   FRUIT_OUTPUT_LANES=2 FRUIT_CKPT=checkpoints/moe_v12/policy_best.pt
#
# The pre-P125 pairing (two-lane scene + the canary of record), the evaluator
# defaults of the A/B, two samples. Report only: it cannot move the A/B verdict
# (`logs/p125/PREREG_A2.md`).
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p125

CKPT=${FRUIT_CKPT:-checkpoints/moe_v12/policy_best.pt}
N=${N:-2}
for i in $(seq 1 "$N"); do
    log="logs/p125/canary_C_${i}.log"
    if [ -f "$log" ] && grep -q "policy success" "$log"; then
        echo "[p125-c] C/$i exists - keeping $log"
        continue
    fi
    echo "[p125-c] C/$i start $(date +%H:%M:%S)"
    FRUIT_OUTPUT_LANES=2 FRUIT_CKPT="$CKPT" \
        ACCEPT_POLICY_LOG="$log" HEADLESS=1 SKIP_SELFCHECK=1 \
        scripts/accept_policy.sh > "logs/p125/canary_C_${i}.gate" 2>&1
    echo "[p125-c] C/$i exit=$? $(date +%H:%M:%S)"
    grep -E "policy success|rate:|failures:" "logs/p125/canary_C_${i}.gate" || true
done
echo "[p125-c] done $(date +%H:%M:%S)"
