#!/usr/bin/env bash
# P37 phase 1: collect the *park*-collected direct-rollout store.
#
#   scripts/221_p37_collect.sh            # shards -> merge -> summary
#   P37_SHARD_EPISODES=4 scripts/221_p37_collect.sh   # a short smoke (writes a real store)
#
# The pre-registration is `logs/p37/PREREG.md` section 3: the direct env under
# `FRUIT_ARM_PARK=back`, the W6-A patch sheet, the arrival trigger + ACQ, the
# `moe_v13s` checkpoint, `--record`, one shard per spawn seed (15 episodes),
# target 90 / floor 60, no diagnostics in the store, merged by
# `scripts/197_r9_merge_rollouts.py` into `datasets/rl_rollouts/p37_park`.
#
# Why shards: a recorded direct run can hit the RTX `multitick.render` stall
# after a few minutes (OPS.md (b)); single-seed shards of 15 episodes are the
# R9 shape that completes, and a wedged shard's finished episodes stay valid.
# **A shard dir is never re-run**: `RolloutRecorder` restarts its file numbering
# at 0, so a second run into the same dir would overwrite earlier episodes.
#
# Every simulator session goes through `scripts/154_claim_run.sh` (one claim per
# shard, `RUN_LIMIT` bounded) with the R9 freeze watchdog beside it.
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1

HERE=logs/p37
PARTS=datasets/rl_rollouts/p37_parts
STORE=datasets/rl_rollouts/p37_park
SHARD_EPS=${P37_SHARD_EPISODES:-15}
TARGET=${P37_TARGET:-90}
FLOOR=${P37_FLOOR:-60}
#: pre-registered seeds (disjoint from the A/B's 77/101/202/303/404) and the
#: declared spares, used only if the six shards leave the total below the floor.
SEEDS=(505 606 707 808 909 1010)
SPARE_SEEDS=(1111 1212)

mkdir -p "$HERE" "$PARTS"
STATUS=$HERE/collect_driver.log

PIN_ENV=(
    FRUIT_ARM_PARK=back
    FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
    FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
    FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9
    FRUIT_POLICY_TRIGGER_ACQ=1
    FRUIT_DYNAMIC_PICK=1
    FRUIT_POLICY_SEED=11
    FRUIT_CAMERA_RES=240,424
    FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1
)

log() { echo "[p37 $(date '+%F %T')] $*" | tee -a "$STATUS"; }

count_episodes() {  # count_episodes <index.json>
    python3 -c "import json,sys;print(len(json.load(open(sys.argv[1]))))" "$1" 2>/dev/null || echo 0
}

total_episodes() {
    local total=0 d
    for d in "$PARTS"/direct_none_seed*; do
        [ -d "$d" ] || continue
        [ -f "$d/index.json" ] || continue
        total=$((total + $(count_episodes "$d/index.json")))
    done
    echo "$total"
}

watch_freeze() {  # watch_freeze <log> [freeze_s]
    local log=$1 freeze=${2:-300} waited=0 sim age gpu
    while :; do
        sleep 30
        sim=$(pgrep -f "[p]ython.sh scripts/110_rl_rollout.py" | head -1 || true)
        if [ -z "$sim" ]; then
            waited=$((waited + 30))
            [ "$waited" -ge 240 ] && return 0
            continue
        fi
        waited=0
        [ -f "$log" ] || continue
        age=$(( $(date +%s) - $(stat -c %Y "$log") ))
        gpu=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -1)
        if [ "$age" -ge "$freeze" ] && [ "${gpu:-100}" -lt 20 ]; then
            log "watchdog: $log frozen ${age}s, gpu ${gpu}% -> killing the sim tree"
            cp "$log" "$HERE/frozen_$(basename "$log" .log)_$(date +%H%M%S).log" 2>/dev/null
            kill -TERM -- "-$sim" 2>/dev/null
            sleep 10
            kill -KILL -- "-$sim" 2>/dev/null
            return 0
        fi
    done
}

#: tree pins, written once (the pre-registration's provenance record).
if [ ! -s "$HERE/tree_md5_before.txt" ]; then
    md5sum src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/policy/trigger.py src/fruit_sorting/policy/runtime.py \
        src/fruit_sorting/meshes.py src/fruit_sorting/fruits.py \
        configs/arm_parks.json configs/motion_reference.json \
        checkpoints/moe_v13s/policy_best.pt datasets/demos_v11/index.json \
        > "$HERE/tree_md5_before.txt"
    git rev-parse HEAD >> "$HERE/tree_md5_before.txt"
    log "pins -> $HERE/tree_md5_before.txt"
fi

run_shard() {  # run_shard <seed>
    local seed=$1 shard="$PARTS/direct_none_seed$1" logf n
    if [ -d "$shard" ] && [ -f "$shard/index.json" ]; then
        n=$(count_episodes "$shard/index.json")
        if [ "$n" -ge 1 ]; then
            log "shard seed$seed already has $n episodes - kept, not re-run"
            return 0
        fi
        log "shard seed$seed exists with 0 episodes - clearing the empty dir"
        rm -rf "$shard"
    fi
    logf="$HERE/collect_seed$seed.log"
    log "shard seed$seed (up to $SHARD_EPS recorded episodes) -> $logf"
    watch_freeze "$logf" "${P37_FREEZE_S:-300}" &
    local watch=$!
    RUN_LIMIT=${P37_RUN_LIMIT:-1500} scripts/154_claim_run.sh "$logf" \
        HEADLESS=1 FRUIT_EPISODES="$SHARD_EPS" "${PIN_ENV[@]}" \
        scripts/run.sh scripts/110_rl_rollout.py \
        --ckpt checkpoints/moe_v13s/policy_best.pt --presentation direct \
        --seeds "$seed" --execute-steps 4 --ddim 16 --record --out "$PARTS"
    local code=$?
    kill "$watch" 2>/dev/null
    n=$(count_episodes "$shard/index.json")
    log "shard seed$seed exit=$code episodes=$n $(grep -oE '\[rl\] rollout success [0-9]+/[0-9]+' "$logf" | tail -1)"
}

for seed in "${SEEDS[@]}"; do
    [ "$(total_episodes)" -ge "$TARGET" ] && break
    run_shard "$seed"
done
if [ "$(total_episodes)" -lt "$FLOOR" ]; then
    log "total $(total_episodes) < floor $FLOOR - running the declared spare seeds"
    for seed in "${SPARE_SEEDS[@]}"; do
        [ "$(total_episodes)" -ge "$TARGET" ] && break
        run_shard "$seed"
    done
fi

total=$(total_episodes)
log "collected $total episodes across $(ls -d "$PARTS"/direct_none_seed* 2>/dev/null | wc -l) shard(s)"
if [ "$total" -lt "$FLOOR" ]; then
    log "ABORT: $total < the pre-registered floor $FLOOR"
    exit 2
fi

if [ -e "$STORE/index.json" ]; then
    log "store $STORE already exists - not overwritten (delete it to re-merge)"
else
    python3 scripts/197_r9_merge_rollouts.py --out "$STORE" \
        "$PARTS"/direct_none_seed* > "$HERE/merge.log" 2>&1
    log "merge exit=$? -> $STORE ($(count_episodes "$STORE/index.json") episodes)"
fi
log "done"
