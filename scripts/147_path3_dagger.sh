#!/usr/bin/env bash
# Path-3 A2C2 training-data collection: DAgger rollouts of the base arm.
#
#   scripts/147_path3_dagger.sh
#
# This is *data collection*, not a rate measurement: the base policy runs in
# the direct interface with the encoder trigger, the scripted pick-phase
# controller acts as the HG-DAgger expert (labels every frame's `action`,
# takes over briefly on deviation), and `--record` writes the frames with both
# `policy_action` (the base proposal) and `action` (the expert label). The
# A2C2 head is trained from these by `scripts/146_train_correction.py`.
#
# The base loop is known to wedge in the scripted primitive's contact state
# (the repo's contact-grind mode), so runs are **short**: 6 episodes with a
# 600 s wall cap, one attempt per seed, partial results kept (the recorder
# writes each finished episode immediately). Seeds are walked until the target
# number of recorded episodes is reached. One simulator at a time.
#
# Env: SEEDS EPISODES DAGGER_TIMEOUT TARGET_EPISODES OUT FRUIT_CKPT_PATH
set -uo pipefail

cd "$(dirname "$0")/.."

out=${OUT:-datasets/path3_a2c2_dagger}
seeds=(${SEEDS:-77 101 202 303 404 505})
episodes=${EPISODES:-6}
timeout_s=${DAGGER_TIMEOUT:-600}
target=${TARGET_EPISODES:-18}
ckpt=${FRUIT_CKPT_PATH:-checkpoints/moe_v11/policy_best.pt}
mkdir -p "$out" logs/path3

count_rows() {
    python3 -c "import json,sys;print(len(json.load(open(sys.argv[1]))))" \
        "$1/index.json" 2>/dev/null || echo 0
}

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [147b] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

total=0
for seed in "${seeds[@]}"; do
    run_dir="$out/direct_none_seed${seed}"
    log="logs/path3/dagger_seed${seed}.log"
    have=0
    [ -d "$run_dir" ] && have=$(count_rows "$run_dir")
    total=$((total + have))
    if [ "$have" -ge "$episodes" ]; then
        echo "  [147b] seed $seed already complete ($have episodes) - skip"
    elif [ "$total" -ge "$target" ]; then
        echo "  [147b] target reached ($total episodes) - stop"
        break
    else
        wait_for_sim
        echo "  [147b] dagger seed $seed ($episodes episodes, cap ${timeout_s}s) $(date +%H:%M:%S)"
        timeout --signal=INT --kill-after=60 "$timeout_s" \
            env HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_POLICY_SEED=11 \
            FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1 FRUIT_POLICY_TRIGGER=arrival \
            scripts/run.sh scripts/110_rl_rollout.py \
            --ckpt "$ckpt" --presentation direct --episodes "$episodes" \
            --seeds "$seed" --dagger --record --out "$out" \
            > "$log" 2>&1
        rc=$?
        have=$(count_rows "$run_dir")
        total=$((total + have))
        echo "  [147b] seed $seed wrote $have episodes (rc=$rc, total $total)"
        if [ "$rc" -ne 0 ]; then
            echo "[147b] seed $seed timed out/incomplete at $(date +%F\ %H:%M:%S)" >> "$log"
        fi
    fi
done
echo "path-3 dagger collection DONE: $total episodes $(date +%F\ %H:%M:%S)"
