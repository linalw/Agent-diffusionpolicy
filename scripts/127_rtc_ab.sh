#!/usr/bin/env bash
# Fast-loop A/B: direct policy rate at --execute-steps 1/2/4 with three
# deployment modes, plus optional report-on timing runs.
#
#   RUNS=3 EPISODES=15 scripts/127_rtc_ab.sh
#   ARMS="4:legacy 4:rtc" RUNS=1 EPISODES=3 AB_DIR=/tmp/opencode/rtc_smoke scripts/127_rtc_ab.sh
#
# Arms are "execute_steps:mode":
#   legacy  synchronous re-planning every E control steps (the shipped loop)
#   rtc     interleaved async chunker, FRUIT_RTC=1 (freeze + EXP soft inpaint)
#   vlash   interleaved async chunker with FRUIT_RTC_GUIDANCE=0 and
#           FRUIT_VLASH=1 (state rolled forward under the pending actions;
#           needs a checkpoint fine-tuned with scripts/133_vlash_finetune.py)
# The legacy tokens 0/1 are accepted and map to legacy/rtc (P4 log labels).
#
# Each run is one sample: `RUNS` runs per arm, each on a different spawn seed
# from SEEDS, run-major so drift is shared. `TIMING=1` adds one report-on
# 3-episode run per arm *first* (those runs are not part of the rate table);
# `PHASE=timing|rates|all` selects the block.
#
# AB_EXTRA_ENV is appended to every run's environment (e.g.
# `AB_EXTRA_ENV="FRUIT_POLICY_TRIGGER=arrival"`); the run manifest records the
# resulting trigger/rtc/vlash configuration, and `129_rtc_report.py` prints it.
#
# One simulator at a time: polls for foreign Isaac processes before every run
# (`pgrep -f '[p]ython.sh'`), never kills another lane's run.
set -uo pipefail

cd "$(dirname "$0")/.."

episodes=${EPISODES:-15}
runs=${RUNS:-3}
seeds=${SEEDS:-77,101,202}
ckpt=${FRUIT_CKPT:-checkpoints/moe_v10/policy_best.pt}
policy_seed=${POLICY_SEED:-11}
out=${AB_DIR:-logs/rtc/ab}
arms=${ARMS:-"1:legacy 1:rtc 2:legacy 2:rtc 4:legacy 4:rtc"}
timing=${TIMING:-0}
timing_episodes=${TIMING_EPISODES:-3}
extra=${AB_EXTRA_ENV:-}

mkdir -p "$out"
echo "fast-loop A/B: ${episodes} episodes x ${runs} runs per arm, ckpt=${ckpt}"
echo "  arms (execute_steps:mode): ${arms}"
echo "  seeds: ${seeds}  policy_seed=${policy_seed}  out=${out}"
if [ -n "$extra" ]; then
    echo "  extra env: ${extra}"
fi

# The frozen tree for this batch: any source the run manifest pins changing
# mid-sweep makes the pooled comparison a mixed-tree comparison, so the sweep
# stops instead. `tasks.py` is also asserted by the env itself (hard fail).
tree_files="src/fruit_sorting/tasks.py src/fruit_sorting/assets.py \
src/fruit_sorting/conveyor.py src/fruit_sorting/scene.py src/fruit_sorting/fruits.py \
src/fruit_sorting/control.py src/fruit_sorting/rl_env.py src/fruit_sorting/policy/runtime.py \
src/fruit_sorting/policy/diffusion.py src/fruit_sorting/policy/trigger.py \
configs/waypoints.json configs/motion_reference.json"
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

mode_env() {
    # Echo the environment additions for a mode (rtc settings / vlash switch).
    local mode=$1 e=$2
    case "$mode" in
    legacy) ;;
    rtc)
        printf 'FRUIT_RTC=1 FRUIT_RTC_INFERENCE_DELAY=%s FRUIT_RTC_EXECUTION_HORIZON=%s FRUIT_RTC_SCHEDULE=%s' \
            "$e" "${RTC_HORIZON:-10}" "${RTC_SCHEDULE:-EXP}"
        ;;
    vlash)
        printf 'FRUIT_RTC=1 FRUIT_RTC_GUIDANCE=0 FRUIT_VLASH=1 FRUIT_RTC_INFERENCE_DELAY=%s FRUIT_RTC_EXECUTION_HORIZON=%s FRUIT_RTC_SCHEDULE=%s' \
            "$e" "${RTC_HORIZON:-10}" "${RTC_SCHEDULE:-EXP}"
        ;;
    *)
        echo "FATAL: unknown arm mode ${mode}" >&2
        exit 2
        ;;
    esac
}

parse_arm() {
    # Sets ARM_E and ARM_MODE from "E:mode"; maps the P4 tokens 0/1.
    local arm=$1
    ARM_E=${arm%%:*}
    ARM_MODE=${arm##*:}
    if [ "$ARM_E" = "$ARM_MODE" ]; then
        echo "FATAL: arm must be execute_steps:mode, got ${arm}" >&2
        exit 2
    fi
    case "$ARM_MODE" in
    0) ARM_MODE=legacy ;;
    1) ARM_MODE=rtc ;;
    esac
}

if [ "$timing" = "1" ] && [ "${PHASE:-all}" != "rates" ]; then
    for arm in $arms; do
        parse_arm "$arm"
        label="E${ARM_E}_${ARM_MODE}"
        log="$out/${label}_timing.log"
        envs="FRUIT_CAMERA_RES=240,424 FRUIT_POLICY_SEED=${policy_seed} FRUIT_CKPT=${ckpt} \
FRUIT_RTC_REPORT=1 ${extra}"
        envs="$envs $(mode_env "$ARM_MODE" "$ARM_E")"
        wait_for_sim
        check_tree
        echo "[ab] timing run arm=${label}"
        env $envs HEADLESS=1 \
            scripts/run.sh scripts/110_rl_rollout.py \
            --presentation direct --episodes "$timing_episodes" --seeds "${TIMING_SEED:-77}" \
            --execute-steps "$ARM_E" --ddim "${DDIM:-16}" --rtc-report \
            > "$log" 2>&1
        # Snapshot the run's manifest next to its log: the live manifest is keyed
        # by (presentation, ablate, seed), so the next arm that runs this seed
        # rewrites it. `129_rtc_report.py` reads the snapshot.
        mf=$(grep -m1 -oE '\[rl\] manifest: \S+' "$log" | awk '{print $3}')
        [ -n "${mf:-}" ] && [ -f "$mf" ] && cp -f "$mf" "$out/${label}_timing.manifest.json"
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
        parse_arm "$arm"
        label="E${ARM_E}_${ARM_MODE}"
        log="$out/${label}_run${run}.log"
        envs="FRUIT_CAMERA_RES=240,424 FRUIT_POLICY_SEED=${policy_seed} FRUIT_CKPT=${ckpt} ${extra}"
        envs="$envs $(mode_env "$ARM_MODE" "$ARM_E")"
        wait_for_sim
        check_tree
        echo "[ab] run ${run}/${runs} seed=${seed} arm=${label}"
        env $envs HEADLESS=1 \
            scripts/run.sh scripts/110_rl_rollout.py \
            --presentation direct --episodes "$episodes" --seeds "$seed" \
            --execute-steps "$ARM_E" --ddim "${DDIM:-16}" \
            > "$log" 2>&1
        # Snapshot the run's manifest next to its log (see the timing block).
        mf=$(grep -m1 -oE '\[rl\] manifest: \S+' "$log" | awk '{print $3}')
        [ -n "${mf:-}" ] && [ -f "$mf" ] && cp -f "$mf" "$out/${label}_run${run}.manifest.json"
        printf '  %s run %d: %s\n' "$label" "$run" \
            "$(grep -oE 'rollout success [0-9]+/[0-9]+' "$log" | tail -1)"
    done
done
fi

python3 scripts/129_rtc_report.py "$out" --runs "$runs"
