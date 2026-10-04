#!/usr/bin/env bash
# Paired N-run A/B of two policy arms in the *direct* presentation (P4).
#
#   ARM_A="--ckpt checkpoints/moe_v7/policy_best.pt" \
#   ARM_B="--ckpt checkpoints/rl_iter1/policy_best.pt" scripts/112_rl_ab.sh
#
# R=5 runs per arm x E=15 episodes, the same seed schedule [77,101,202,303,404],
# interleaved A,B,A,B, with `FRUIT_POLICY_SEED` fixed so the sampler differences
# are the same across arms. Each run is one simulator session (one at a time),
# so this is ~3.5 h of wall clock; the report aggregates the per-episode outcome
# and pairs episodes by (run, episode index).
#
# Why N per arm: the direct loop conditions on rendered frames, and RTX frames
# are not bit-reproducible (WORKLOG "the hybrid loop's variation is the rendered
# frames"), so a single run is one sample of a configuration. Aggregate the
# outcome, not a continuous quantity.
#
# Env: RUNS, EPISODES, AB_SEEDS, AB_POLICY_SEED, AB_SIZE_FILTER, AB_DIR,
#      AB_EXTRA_ENV (both arms), ARM_A_ENV / ARM_B_ENV (per arm),
#      AB_RECORD (set to 1 to write rollout npz as well).
set -uo pipefail

cd "$(dirname "$0")/.."

runs=${RUNS:-5}
episodes=${EPISODES:-15}
seeds=(${AB_SEEDS:-77 101 202 303 404})
policy_seed=${AB_POLICY_SEED:-11}
out=${AB_DIR:-logs/rl_ab}
arm_a=${ARM_A:-"--ckpt checkpoints/moe_v7/policy_best.pt"}
arm_b=${ARM_B:-"--ckpt checkpoints/rl_iter1/policy_best.pt"}
size=${AB_SIZE_FILTER:-}
extra=${AB_EXTRA_ENV:-}
#: Per-arm extra environment (P4b1): e.g. ARM_B_ENV="FRUIT_POLICY_TRIGGER=arrival"
#: to measure an env-side candidate against the same checkpoint. Empty = off.
extra_a=${ARM_A_ENV:-}
extra_b=${ARM_B_ENV:-}
record=${AB_RECORD:+--record}

if [ "${#seeds[@]}" -lt "$runs" ]; then
    echo "FAIL: need at least $runs seeds in AB_SEEDS (have ${#seeds[@]})"
    exit 1
fi

mkdir -p "$out"
echo "direct RL A/B: ${episodes} episodes x ${runs} runs per arm, policy seed=${policy_seed}"
echo "  seeds: ${seeds[*]:0:$runs}"
echo "  arm A (baseline): ${arm_a}"
echo "  arm B (candidate): ${arm_b}"
if [ -n "$extra_a$extra_b$extra" ]; then
    echo "  extra env: both='${extra}' A='${extra_a}' B='${extra_b}'"
fi

# One simulator at a time (AGENTS.md): another lane may hold it, so poll for a
# free one before each session and never kill a foreign process.
wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [ab] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

run_one() {
    local label=$1 args=$2 run=$3 seed=$4 arm_extra=$5 log
    log="$out/${label}_${run}.log"
    wait_for_sim
    # shellcheck disable=SC2086
    env $extra $arm_extra HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER="$size" \
        FRUIT_POLICY_SEED="$policy_seed" FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1 \
        scripts/run.sh scripts/110_rl_rollout.py $args --presentation direct \
        --episodes "$episodes" --seeds "$seed" $record \
        --out "$out/raw/${label}_${run}" > "$log" 2>&1
    printf '  %s run %d (seed %s): %s\n' "$label" "$run" "$seed" \
        "$(grep -oE '\[rl\] rollout success [0-9]+/[0-9]+' "$log" | tail -1)"
}

for i in $(seq 1 "$runs"); do
    seed=${seeds[$((i - 1))]}
    run_one A "$arm_a" "$i" "$seed" "$extra_a"
    run_one B "$arm_b" "$i" "$seed" "$extra_b"
done

python3 scripts/113_rl_report.py "$out" --a A --b B
