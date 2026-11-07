#!/usr/bin/env bash
# P125 step 3: the hybrid-canary A/B on the **three-lane** scene.
#
# Both arms run `scripts/accept_policy.sh` with `FRUIT_OUTPUT_LANES=3`, the
# shipped evaluator defaults (`FRUIT_SUPPLY_SCATTER=0`, camera 240,424, SEED 77,
# 10 episodes) and differ **only** in `FRUIT_CKPT`:
#
#   A = checkpoints/moe_v12/policy_best.pt          (the base, the canary of record)
#   B = checkpoints/p125_three_lane/policy_best.pt  (the three-lane recollection)
#
# N = 3 samples per arm, interleaved `A B A B A B` so drift is shared (PREREG
# section 4). Each sample is one `accept_policy.sh` run (~13-16 min). Existing
# logs are kept (resume-safe): rm a log to force its sample.
#
#   nohup bash logs/p125/run_p125_canary.sh > logs/p125/canary_driver.log 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p125

A=${A:-checkpoints/moe_v12/policy_best.pt}
B=${B:-checkpoints/p125_three_lane/policy_best.pt}
N=${N:-3}

for f in "$A" "$B"; do
    [ -f "$f" ] || { echo "[p125-ab] FAIL: no checkpoint $f"; exit 1; }
done

run_one() {  # run_one <arm> <sample>
    local arm=$1 sample=$2 ckpt log
    case "$arm" in
        A) ckpt=$A ;;
        B) ckpt=$B ;;
        *) echo "[p125-ab] bad arm $arm"; exit 1 ;;
    esac
    log="logs/p125/canary_${arm}_${sample}.log"
    if [ -f "$log" ] && grep -q "policy success" "$log"; then
        echo "[p125-ab] $arm/$sample exists - keeping $log"
        return 0
    fi
    echo "[p125-ab] $arm/$sample start $(date +%H:%M:%S) ckpt=$ckpt"
    FRUIT_OUTPUT_LANES=3 FRUIT_CKPT="$ckpt" \
        ACCEPT_POLICY_LOG="$log" HEADLESS=1 SKIP_SELFCHECK=1 \
        scripts/accept_policy.sh > "logs/p125/canary_${arm}_${sample}.gate" 2>&1
    local code=$?
    echo "[p125-ab] $arm/$sample exit=$code $(date +%H:%M:%S)"
    grep -E "policy success|rate:|failures:" "logs/p125/canary_${arm}_${sample}.gate" || true
    return 0
}

for i in $(seq 1 "$N"); do
    run_one A "$i"
    run_one B "$i"
done

echo "[p125-ab] done $(date +%H:%M:%S)"
