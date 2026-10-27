#!/usr/bin/env bash
# P53: the policy's own emission defect, two default-off cells (C1 the joint
# clamp, C2 the action hold) against the shipped emission (T0).
#
#   nohup bash logs/p53/run_batch.sh > logs/p53/p3/batch_outer.log 2>&1 &
#
# Design (registered in logs/p53/P53_RESULTS.md section 1 before the run):
#
#   T0 = the shipped emission     (both knobs unset)     ARM_T0_ENV=""
#   C1 = the joint clamp          FRUIT_POLICY_JOINT_CLAMP=1
#   C2 = the action hold          FRUIT_POLICY_ACTION_HOLD=2
#
# All three on `checkpoints/moe_v13s/policy_best.pt` (`61da390a`), the P43
# scenario block verbatim (the W6-A/W8-A patch sheet, balanced A:B:C, trigger
# arrival + lead 0.9 + ACQ=1, dynamic pick, the park default `back`), N = 3 runs
# x 15 episodes per arm, seeds 77/101/202, policy seed 11, interleaved
# T0 -> C1 -> C2 per seed, one `scripts/154_claim_run.sh` claim for the batch,
# one instrumentation set on all three arms (AGENTS 3b: the instrument sits
# inside the contrast).
#
# Instruments:
#   * `FRUIT_EMIT_DIAG=1`  - the new per-episode `[emit]` row: applied ticks, the
#     policy decisions, and the out-of-range joint count **before** and **after**
#     the clamp. Pure array work on the action already in hand - no simulator
#     read, so it cannot perturb the loop through a sensor.
#   * `FRUIT_ACQ_DIAG=1` / `FRUIT_CARRY_DIAG=1` - the failure classes (P35-P43
#     practice), on all arms.
#   * `--record` on every run - the `(action, joint_positions)` pair per 30 Hz
#     frame, i.e. the **same-tick lead residual** (the dither) from the store,
#     with `logs/p52/p2b_feasibility.py`'s own formula (p50 |cmd-achieved| x the
#     0.30 m lever) so the number is comparable to the census's 19.3 mm.
#     Stores go to /tmp (gitignored, several GB); the logs stay in the repo.
#
# Nothing here writes `configs/`, `datasets/` or a checkpoint.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p53/p3 /tmp/opencode/p53/raw

CKPT=checkpoints/moe_v13s/policy_best.pt
PATCH_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25"
SCEN_ENV="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_DYNAMIC_PICK=1"
DIAG_ENV="FRUIT_ACQ_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_EMIT_DIAG=1"

RUNS=3
EPISODES=15
SEEDS=(77 101 202)
POLICY_SEED=11

{
    echo "# P53 batch header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)"
    md5sum "$CKPT" \
        src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
        src/fruit_sorting/control.py src/fruit_sorting/scene.py \
        src/fruit_sorting/policy/runtime.py src/fruit_sorting/policy/trigger.py \
        src/fruit_sorting/meshes.py src/fruit_sorting/fruits.py \
        configs/arm_parks.json configs/motion_reference.json \
        configs/motion_reference_twoline.json \
        scripts/110_rl_rollout.py scripts/113_rl_report.py \
        scripts/229_p53_emit_selftest.py \
        logs/p53/run_batch.sh logs/p53/p53_report.py
    echo "# scenario: $PATCH_ENV $SCEN_ENV $DIAG_ENV"
    echo "# T0 = shipped (knobs unset) ; C1 = FRUIT_POLICY_JOINT_CLAMP=1 ; C2 = FRUIT_POLICY_ACTION_HOLD=2"
    echo "# RUNS=$RUNS EPISODES=$EPISODES SEEDS=${SEEDS[*]:0:$RUNS} policy_seed=$POLICY_SEED, interleaved T0,C1,C2"
    echo "# all three arms --record into /tmp/opencode/p53/raw (the dither store)"
} > logs/p53/p3/P3_header.txt
cat logs/p53/p3/P3_header.txt

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [p53] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

run_one() {
    local label=$1 arm_env=$2 run=$3 seed=$4 log
    log="logs/p53/p3/${label}_${run}.log"
    wait_for_sim
    # shellcheck disable=SC2086
    RUN_LIMIT=2400 scripts/154_claim_run.sh "$log" \
        $PATCH_ENV $SCEN_ENV $DIAG_ENV $arm_env \
        HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= \
        FRUIT_POLICY_SEED="$POLICY_SEED" FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1 \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" --presentation direct \
        --episodes "$EPISODES" --seeds "$seed" --record \
        --out "/tmp/opencode/p53/raw/${label}_${run}"
    printf '  %s run %d (seed %s): exit=%s %s\n' "$label" "$run" "$seed" "$?" \
        "$(grep -oE '\[rl\] rollout success [0-9]+/[0-9]+' "$log" | tail -1)"
}

t0=$(date +%s)
echo "[p53] batch start $(date '+%F %T')"
for i in $(seq 1 "$RUNS"); do
    seed=${SEEDS[$((i - 1))]}
    run_one T0 "" "$i" "$seed"
    run_one C1 "FRUIT_POLICY_JOINT_CLAMP=1" "$i" "$seed"
    run_one C2 "FRUIT_POLICY_ACTION_HOLD=2" "$i" "$seed"
done
t1=$(date +%s)
echo "[p53] batch end $(date '+%F %T') wall=$((t1 - t0))s"

{
    echo "# P53 batch pins after ($(date '+%F %T'))"
    md5sum "$CKPT" src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
        configs/arm_parks.json configs/motion_reference.json \
        configs/motion_reference_twoline.json
    echo "# batch wall $((t1 - t0))s"
} > logs/p53/p3/P3_tree_md5_after.txt

# the manifests of record (the stores themselves stay in /tmp)
mkdir -p logs/p53/p3/manifests
for d in /tmp/opencode/p53/raw/*/; do
    n=$(basename "$d")
    m=$(find "$d" -name manifest.json | head -1)
    [ -n "$m" ] && cp "$m" "logs/p53/p3/manifests/${n}.json"
done

echo "[p53] reports"
python3 logs/p53/p53_report.py --dir logs/p53/p3 --stores /tmp/opencode/p53/raw \
    > logs/p53/p3/P53_report.txt 2>&1
echo "[p53] p53 report exit=$?"
python3 scripts/113_rl_report.py logs/p53/p3 --a T0 --b C1 \
    > logs/p53/p3/P53_113_T0_C1.txt 2>&1
echo "[p53] 113 T0/C1 exit=$?"
python3 scripts/113_rl_report.py logs/p53/p3 --a T0 --b C2 \
    > logs/p53/p3/P53_113_T0_C2.txt 2>&1
echo "[p53] 113 T0/C2 exit=$?"
echo "[p53] done $(date '+%F %T')"
