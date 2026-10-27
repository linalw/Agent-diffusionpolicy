#!/usr/bin/env bash
# P54 phase 1: the **shipped** direct configuration measured against ACQ=1.
#
#   nohup bash logs/p54/run_batch.sh > logs/p54/p1/batch_outer.log 2>&1 &
#
# The question (logs/p54/PREREG.md): the direct interface's post-park baseline
# (right 94.6 % / left 4.8 %) is an **ACQ=1** number, while the shipped default
# is `FRUIT_POLICY_TRIGGER_ACQ` **off** (W7-B; R5 decision 4). Nothing on this
# tree has measured the shipped direct configuration.
#
#   A = the shipped config        FRUIT_POLICY_TRIGGER_ACQ unset
#   B = the measured config       FRUIT_POLICY_TRIGGER_ACQ=1
#
# Everything else is the P43 protocol verbatim: `checkpoints/moe_v13s` (`61da390a`)
# on both arms, the W6-A/W8-A patch sheet, balanced A:B:C, trigger arrival + lead
# 0.9, dynamic pick, the park **default** (`back`), N = 3 runs x 15 episodes per
# arm, seeds 77/101/202, policy seed 11, interleaved A then B per seed, one
# `154_claim_run.sh` claim for the batch, one instrumentation set on both arms
# (AGENTS 3b: the instrument sits inside the contrast).
#
# Endpoints (registered before the run): E1 the right-arm placed delta
# (rate_A - rate_B) >= -0.10; E2 the pre-contact acquisition class (never-held,
# split trigger-path / policy-gate) plus its mechanism (`[acq]` catch-up residual,
# close-start offset); E3 no new failure reason; the left arm reported.
#
# No `--record`: every endpoint of this phase is read from the logs (`[rl] episode`,
# `[acq]`, `[carry]`, `[park]`), and a store would only add wall and I/O noise.
# Nothing here writes `configs/`, `datasets/` or a checkpoint.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p54/p1

CKPT=checkpoints/moe_v13s/policy_best.pt
PATCH_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25"
# NOTE: no `FRUIT_POLICY_TRIGGER_ACQ` here - that is the one variable under test,
# and it lives in the per-arm env below (arm A is the unset case).
SCEN_ENV="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1"
DIAG_ENV="FRUIT_ACQ_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_PARK_DIAG=1"

RUNS=3
EPISODES=15
SEEDS=(77 101 202)
POLICY_SEED=11

{
    echo "# P54 phase 1 batch header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)"
    md5sum "$CKPT" \
        src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
        src/fruit_sorting/control.py src/fruit_sorting/scene.py \
        src/fruit_sorting/policy/runtime.py src/fruit_sorting/policy/trigger.py \
        src/fruit_sorting/meshes.py src/fruit_sorting/fruits.py \
        configs/arm_parks.json configs/motion_reference.json \
        configs/motion_reference_twoline.json \
        scripts/110_rl_rollout.py scripts/113_rl_report.py scripts/154_claim_run.sh \
        logs/w7/B_ab_report.py logs/p53/p53_report.py \
        logs/p54/run_batch.sh logs/p54/p54_report.py logs/p54/PREREG.md
    echo "# scenario (both arms): $PATCH_ENV $SCEN_ENV $DIAG_ENV"
    echo "# A = FRUIT_POLICY_TRIGGER_ACQ unset (the SHIPPED config) ; B = FRUIT_POLICY_TRIGGER_ACQ=1 (the measured config)"
    echo "# ckpt=$CKPT on BOTH arms; park unset = the P43 default (back)"
    echo "# RUNS=$RUNS EPISODES=$EPISODES SEEDS=${SEEDS[*]:0:$RUNS} policy_seed=$POLICY_SEED, interleaved A then B"
} > logs/p54/p1/P1_header.txt
cat logs/p54/p1/P1_header.txt

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [p54] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

run_one() {
    local label=$1 arm_env=$2 run=$3 seed=$4 log
    log="logs/p54/p1/${label}_${run}.log"
    wait_for_sim
    # shellcheck disable=SC2086
    RUN_LIMIT=1800 scripts/154_claim_run.sh "$log" \
        $PATCH_ENV $SCEN_ENV $DIAG_ENV $arm_env \
        HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= \
        FRUIT_POLICY_SEED="$POLICY_SEED" FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1 \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" --presentation direct \
        --episodes "$EPISODES" --seeds "$seed"
    printf '  %s run %d (seed %s): exit=%s %s\n' "$label" "$run" "$seed" "$?" \
        "$(grep -oE '\[rl\] rollout success [0-9]+/[0-9]+' "$log" | tail -1)"
}

t0=$(date +%s)
echo "[p54] batch start $(date '+%F %T')"
for i in $(seq 1 "$RUNS"); do
    seed=${SEEDS[$((i - 1))]}
    run_one A "" "$i" "$seed"
    run_one B "FRUIT_POLICY_TRIGGER_ACQ=1" "$i" "$seed"
done
t1=$(date +%s)
echo "[p54] batch end $(date '+%F %T') wall=$((t1 - t0))s"

{
    echo "# P54 phase 1 batch pins after ($(date '+%F %T'))"
    md5sum "$CKPT" src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
        src/fruit_sorting/policy/trigger.py \
        configs/arm_parks.json configs/motion_reference.json \
        configs/motion_reference_twoline.json
    echo "# batch wall $((t1 - t0))s"
} > logs/p54/p1/P1_tree_md5_after.txt

echo "[p54] reports"
python3 logs/p54/p54_report.py --dir logs/p54/p1 --a A --b B \
    > logs/p54/p1/P54_report.txt 2>&1
echo "[p54] p54 report exit=$?"
python3 scripts/113_rl_report.py logs/p54/p1 --a A --b B \
    > logs/p54/p1/P54_113_A_B.txt 2>&1
echo "[p54] 113 A/B exit=$?"
python3 logs/w7/B_ab_report.py --dir logs/p54/p1 --a A --b B \
    > logs/p54/p1/P54_w7acq.txt 2>&1
echo "[p54] w7 acq report exit=$?"
echo "[p54] done $(date '+%F %T')"
