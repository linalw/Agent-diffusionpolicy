#!/usr/bin/env bash
# P145: collect the >=150-episode DAgger store in **timeout-guarded chunks**.
# The direct rollout has no watchdog; a renderer wedge otherwise costs the whole
# run (measured: one wedge at episode 8 of a 150-episode attempt). Each chunk is
# 8 episodes and is killed after 20 min; completed episodes stay on disk.
set -u
cd "$(dirname "$0")/../.." || exit 1
SEEDS=(77 101 202 303 404)
NCHUNK=${NCHUNK:-19}
for i in $(seq 1 "$NCHUNK"); do
    s=${SEEDS[$(( (i-1) % 5 ))]}
    out=$(printf "datasets/p145_c%02d" "$i")
    have=$(ls "$out"/*.npz 2>/dev/null | wc -l)
    if [ "$have" -ge 8 ]; then
        echo "[p145] chunk $i already has $have episodes, skip"
        continue
    fi
    rm -rf "$out"
    echo "[p145] chunk $i seed $s start $(date +%H:%M:%S)"
    timeout 1200 env FRUIT_GOAL_SOURCE=perception FRUIT_PERCEPTION_DIAG=1 \
        FRUIT_POLICY_HANDOVER=0 FRUIT_CAMERA_RES=240,424 FRUIT_HANDOVER_DIAG=1 \
        FRUIT_DAGGER_NO_TAKEOVER=1 SKIP_SELFCHECK=1 scripts/run.sh \
        scripts/110_rl_rollout.py --ckpt checkpoints/p145_dagger_b/policy_best.pt \
        --presentation direct --episodes 8 --seeds "$s" --horizon 760 \
        --dagger --expert-tolerance 99 --expert-window 0 --record --out "$out" \
        > "logs/p145_chunk_$(printf %02d "$i").log" 2>&1
    rc=$?
    echo "[p145] chunk $i rc=$rc episodes=$(ls "$out"/*.npz 2>/dev/null | wc -l) $(date +%H:%M:%S)"
done
echo "[p145] collection done $(date +%H:%M:%S)"
