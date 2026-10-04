#!/usr/bin/env bash
# RTC A/B: direct policy rate at --execute-steps 1/2/4, with and without RTC.
#
#   RUNS=3 EPISODES=15 scripts/127_rtc_ab.sh
#   ARMS="1:0 1:1" RUNS=1 EPISODES=3 AB_DIR=/tmp/opencode/rtc_smoke scripts/127_rtc_ab.sh
#
# Arms are "execute_steps:rtc" (rtc=1 sets FRUIT_RTC=1 and the inference delay
# to the same value, i.e. the sampler is spread over execute_steps control
# steps). Each run is one sample: `RUNS` runs per arm, each on a different spawn
# seed from SEEDS, run-major so drift is shared. `TIMING=1` adds one report-on
# 3-episode run per arm *first* (those runs are not part of the rate table);
# `PHASE=timing|rates|all` selects the block.
#
# One simulator at a time: polls for foreign Isaac processes before every run
# (`pgrep -f '[p]ython.sh'`), never kills another lane's run.
set -uo pipefail

cd "$(dirname "$0")/.."

episodes=${EPISODES:-15}
runs=${RUNS:-3}
seeds=${SEEDS:-77,101,202}
ckpt=${FRUIT_CKPT:-checkpoints/moe_v9/policy_best.pt}
policy_seed=${POLICY_SEED:-11}
out=${AB_DIR:-logs/rtc/ab}
arms=${ARMS:-"1:0 1:1 2:0 2:1 4:0 4:1"}
timing=${TIMING:-0}
timing_episodes=${TIMING_EPISODES:-3}

mkdir -p "$out"
echo "RTC A/B: ${episodes} episodes x ${runs} runs per arm, ckpt=${ckpt}"
echo "  arms (execute_steps:rtc): ${arms}"
echo "  seeds: ${seeds}  policy_seed=${policy_seed}  out=${out}"

# The frozen tree for this batch: any source the run manifest pins changing
# mid-sweep makes the pooled comparison a mixed-tree comparison, so the sweep
# stops instead. `tasks.py` is also asserted by the env itself (hard fail).
tree_files="src/fruit_sorting/tasks.py src/fruit_sorting/assets.py \
src/fruit_sorting/conveyor.py src/fruit_sorting/scene.py src/fruit_sorting/fruits.py \
src/fruit_sorting/control.py src/fruit_sorting/rl_env.py src/fruit_sorting/policy/runtime.py \
src/fruit_sorting/policy/diffusion.py configs/waypoints.json configs/motion_reference.json"
tree_before=$(md5sum $tree_files 2>/dev/null)
echo "$tree_before" > "$out/tree_before.sha256"
echo "  tree pinned: $(echo "$tree_before" | awk '{print $1}' | tr '\n' ' ')"

wait_for_sim() {
    while pgrep -f '[p]ython.sh' > /dev/null 2>&1; do
        echo "  [wait] another Isaac process is running; sleeping 60 s"
        sleep 60
    done
}

check_tree() {
    local current
    current=$(md5sum $tree_files 2>/dev/null)
    if [ "$current" != "$tree_before" ]; then
        echo "FATAL: a pinned source changed mid-sweep; aborting before the next run." >&2
        diff <(echo "$tree_before") <(echo "$current") >&2 || true
        exit 3
    fi
}

if [ "$timing" = "1" ] && [ "${PHASE:-all}" != "rates" ]; then
    for arm in $arms; do
        e=${arm%%:*}
        r=${arm##*:}
        label="E${e}_rtc${r}"
        log="$out/${label}_timing.log"
        envs="FRUIT_CAMERA_RES=240,424 FRUIT_POLICY_SEED=${policy_seed} FRUIT_CKPT=${ckpt} \
FRUIT_RTC_REPORT=1"
        if [ "$r" = "1" ]; then
            envs="$envs FRUIT_RTC=1 FRUIT_RTC_INFERENCE_DELAY=${e}"
        fi
        wait_for_sim
        check_tree
        echo "[ab] timing run arm=${label}"
        env $envs HEADLESS=1 \
            scripts/run.sh scripts/110_rl_rollout.py \
            --presentation direct --episodes "$timing_episodes" --seeds "${TIMING_SEED:-77}" \
            --execute-steps "$e" --ddim "${DDIM:-16}" --rtc-report \
            > "$log" 2>&1
        printf '  %s timing: %s\n' "$label" \
            "$(grep -oE 'rollout success [0-9]+/[0-9]+' "$log" | tail -1)"
    done
fi

if [ "${PHASE:-all}" != "timing" ]; then
for run in $(seq 1 "$runs"); do
    seed=$(echo "$seeds" | cut -d, -f"$run")
    if [ -z "$seed" ]; then
        echo "error: only $(echo "$seeds" | tr ',' ' ') seeds for $runs runs" >&2
        exit 2
    fi
    for arm in $arms; do
        e=${arm%%:*}
        r=${arm##*:}
        label="E${e}_rtc${r}"
        log="$out/${label}_run${run}.log"
        envs="FRUIT_CAMERA_RES=240,424 FRUIT_POLICY_SEED=${policy_seed} FRUIT_CKPT=${ckpt}"
        if [ "$r" = "1" ]; then
            envs="$envs FRUIT_RTC=1 FRUIT_RTC_INFERENCE_DELAY=${e} \
FRUIT_RTC_EXECUTION_HORIZON=${RTC_HORIZON:-10} FRUIT_RTC_SCHEDULE=${RTC_SCHEDULE:-EXP}"
        fi
        wait_for_sim
        check_tree
        echo "[ab] run ${run}/${runs} seed=${seed} arm=${label}"
        env $envs HEADLESS=1 \
            scripts/run.sh scripts/110_rl_rollout.py \
            --presentation direct --episodes "$episodes" --seeds "$seed" \
            --execute-steps "$e" --ddim "${DDIM:-16}" \
            > "$log" 2>&1
        printf '  %s run %d: %s\n' "$label" "$run" \
            "$(grep -oE 'rollout success [0-9]+/[0-9]+' "$log" | tail -1)"
    done
done
fi

python3 scripts/129_rtc_report.py "$out" --runs "$runs"
