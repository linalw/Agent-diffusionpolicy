#!/usr/bin/env bash
# Deployability batch driver for the distillation comparison.
#
#   LABEL=teacher FRUIT_CKPT=checkpoints/moe_v10/policy_best.pt DDIM=16 \
#     scripts/138_distill_runs.sh
#   LABEL=student1 FRUIT_CKPT=checkpoints/distill_v1/policy_best.pt DDIM=1 \
#     scripts/138_distill_runs.sh
#
# One seed per simulator invocation (a wedged primitive costs one seed, not the
# batch) with a 40-minute per-seed wall timeout; the camera resolution, encoder
# intercept trigger and policy sampler seed are the frozen comparison settings.
set -uo pipefail
cd "$(dirname "$0")/.."

label=${LABEL:-teacher}
ckpt=${FRUIT_CKPT:-checkpoints/moe_v10/policy_best.pt}
ddim=${DDIM:-16}
exec_steps=${EXEC:-4}
seeds=${SEEDS:-77,101,202}
episodes=${EPISODES:-15}
trigger=${TRIGGER:-arrival}
out=${OUT_DIR:-datasets/rl_rollouts_distill/${label}_trigger}
logdir=${LOGDIR:-logs/distill}
wall=${WALL:-2400}
mkdir -p "$out" "$logdir"

for seed in $(echo "$seeds" | tr ',' ' '); do
    # Wait for the simulator *and* any queued A/B driver: the other lane's
    # `127_rtc_ab.sh` restarts its runs within a second of the sim exiting, so
    # checking only python.sh can race its startup window.
    while pgrep -f '[p]ython.sh' >/dev/null 2>&1 \
        || pgrep -f '[1]27_rtc_ab.sh' >/dev/null 2>&1 \
        || pgrep -f '[1]40_policy_ab.sh' >/dev/null 2>&1; do
        echo "[wait] another Isaac process/driver is running; sleeping 60 s"
        sleep 60
    done
    log="$logdir/138_${label}_trigger_seed${seed}.log"
    echo "[run] label=$label seed=$seed ckpt=$ckpt ddim=$ddim exec=$exec_steps"
    timeout "$wall" env FRUIT_CAMERA_RES=240,424 FRUIT_POLICY_TRIGGER="$trigger" \
        FRUIT_POLICY_SEED=11 HEADLESS=1 \
        scripts/run.sh scripts/110_rl_rollout.py \
        --ckpt "$ckpt" --presentation direct --episodes "$episodes" --seeds "$seed" \
        --execute-steps "$exec_steps" --ddim "$ddim" --out "$out" \
        > "$log" 2>&1
    code=$?
    echo "[run] label=$label seed=$seed exit=$code $(grep -oE 'rollout success [0-9]+/[0-9]+' "$log" | tail -1)"
    if [ "$code" = "124" ]; then
        echo "[run] seed $seed hit the ${wall}s wall (wedged primitive?)"
    fi
    sleep 5
done
