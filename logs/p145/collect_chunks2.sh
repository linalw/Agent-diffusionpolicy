#!/usr/bin/env bash
# P145 step 1b: the >=150-episode DAgger store, 16 episodes per timeout-guarded
# chunk, horizon 520 (the close ramp ends at ~t=455; the 760-tick episode spent
# 4 s in the post-close phase where the direct loop wedged - measured: 8/8 with
# 520, 2/8 with 760).
set -u
cd "$(dirname "$0")/../.." || exit 1
SEEDS=(303 404 505 606 707 808 909 111 222 333)
NCHUNK=${NCHUNK:-10}
for i in $(seq 1 "$NCHUNK"); do
    s=${SEEDS[$(( (i-1) % 10 ))]}
    out=$(printf "datasets/p145_d%02d" "$i")
    have=$(ls "$out"/*/*.npz 2>/dev/null | wc -l)
    if [ "$have" -ge 16 ]; then
        echo "[p145] chunk $i already has $have episodes, skip"
        continue
    fi
    rm -rf "$out"
    echo "[p145] chunk $i seed $s start $(date +%H:%M:%S)"
    timeout 1500 env FRUIT_GOAL_SOURCE=perception FRUIT_PERCEPTION_DIAG=1 \
        FRUIT_POLICY_HANDOVER=0 FRUIT_CAMERA_RES=240,424 FRUIT_HANDOVER_DIAG=1 \
        FRUIT_DAGGER_NO_TAKEOVER=1 SKIP_SELFCHECK=1 scripts/run.sh \
        scripts/110_rl_rollout.py --ckpt checkpoints/p145_dagger_b/policy_best.pt \
        --presentation direct --episodes 16 --seeds "$s" --horizon 520 \
        --dagger --expert-tolerance 99 --expert-window 0 --record --out "$out" \
        > "logs/p145_chunk2_$(printf %02d "$i").log" 2>&1
    rc=$?
    echo "[p145] chunk $i rc=$rc episodes=$(ls "$out"/*/*.npz 2>/dev/null | wc -l) $(date +%H:%M:%S)"
done
echo "[p145] collection done $(date +%H:%M:%S)"
