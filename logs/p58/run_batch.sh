#!/usr/bin/env bash
# P58 phase 1: the continuous-supply stack's adoption A/B (PREREG.md, written first).
#
#   nohup bash logs/p58/run_batch.sh > logs/p58/batch_outer.log 2>&1 &
#
#   A = today's shipped direct config            --episodes 15          (15 picks)
#   B = the continuous stack                     --episodes 1 + env     (15 picks)
#       FRUIT_DIRECT_CONTINUOUS=15 FRUIT_DIRECT_FEED=1 FRUIT_FEED_CADENCE=1
#       FRUIT_SUPPLY_BAND_INTERLOCK=1 FRUIT_SUPPLY_BAND_MAX=3
#
# Both arms (PREREG §1): the W6-A/W8-A patch sheet, balanced A:B:C,
# trigger arrival + lead 0.9, dynamic pick, ACQ **unset** (P54: on for `direct`),
# park **unset** (P43: `back` for `direct`), FRUIT_BED_DIAG=1 in BOTH arms,
# checkpoint `moe_v13s` on both, seeds 77/101/202 interleaved A then B, one
# `154_claim_run.sh` claim per run, one `[rl] episode` row per pick.
#
# Order: P3 (the scripted no-harm) runs FIRST - it is cheap (~4 min) and F4 says
# a moved shipped path voids the battery, so it must not be discovered after
# 50 minutes of simulator time. Nothing here writes `src/`, `configs/`,
# `datasets/` or a checkpoint.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p58/p1

CKPT=checkpoints/moe_v13s/policy_best.pt
PATCH_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25"
SCEN_ENV="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1"
DIAG_ENV="FRUIT_BED_DIAG=1"
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
ARM_B_ENV="FRUIT_DIRECT_CONTINUOUS=15 FRUIT_DIRECT_FEED=1 FRUIT_FEED_CADENCE=1 FRUIT_SUPPLY_BAND_INTERLOCK=1 FRUIT_SUPPLY_BAND_MAX=3"

SEEDS=(77 101 202)
POLICY_SEED=11

{
    echo "# P58 phase 1 batch header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)"
    md5sum "$CKPT" \
        src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
        src/fruit_sorting/fruits.py src/fruit_sorting/scene.py \
        src/fruit_sorting/control.py src/fruit_sorting/meshes.py \
        src/fruit_sorting/policy/trigger.py src/fruit_sorting/policy/runtime.py \
        configs/arm_parks.json configs/motion_reference.json \
        configs/motion_reference_twoline.json \
        scripts/110_rl_rollout.py scripts/113_rl_report.py scripts/154_claim_run.sh \
        scripts/accept.sh scripts/105_motion_regression.py \
        logs/p34/73_accept_no_harm.log logs/p53/03b_accept_noharm_run.log \
        logs/p58/PREREG.md logs/p58/run_batch.sh logs/p58/p1_report.py
    echo "# scenario (both arms): $PATCH_ENV $SCEN_ENV $DIAG_ENV"
    echo "# ACQ unset (P54 default on for direct) ; FRUIT_ARM_PARK unset (P43 default back) ; ckpt=$CKPT BOTH arms"
    echo "# A = --episodes 15 (no other env) ; B = --episodes 1 + $ARM_B_ENV"
    echo "# SEEDS=${SEEDS[*]} policy_seed=$POLICY_SEED, interleaved A then B, one claim per run"
} > logs/p58/p1/P1_header.txt
cat logs/p58/p1/P1_header.txt

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [p58] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

# ---------------------------------------------------------------- P3 first --
echo "[p58] P3 scripted no-harm $(date '+%F %T')"
wait_for_sim
ACCEPT_LOG=logs/p58/p3_accept.log scripts/accept.sh > logs/p58/p3_accept_outer.log 2>&1
echo "[p58] accept.sh exit=$? $(date '+%H:%M:%S')"
grep -E "fingerprint|\[stats\]" logs/p58/p3_accept_outer.log | tail -3
echo "[p58] P3 [fruit] lines: $(grep -c '\[fruit\]' logs/p58/p3_accept.log) (same-tree ref 377 logs/p53/03b_accept_noharm_run.log; pre-P41 p34 ref 376 - amendment A2)"

run_one() {
    local label=$1 arm_env=$2 seed=$3 episodes=$4 log
    log="logs/p58/p1/${label}_${seed}.log"
    wait_for_sim
    # shellcheck disable=SC2086
    RUN_LIMIT=1800 scripts/154_claim_run.sh "$log" \
        $PATCH_ENV $SCEN_ENV $DIAG_ENV $HARNESS_ENV $arm_env \
        FRUIT_POLICY_SEED="$POLICY_SEED" \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" --presentation direct \
        --episodes "$episodes" --seeds "$seed"
    local code=$?
    local picks
    picks=$(grep -cE '\[rl\] episode [0-9]+: .* success=' "$log" 2>/dev/null || true)
    printf '  %s seed %s: exit=%s picks=%s %s\n' "$label" "$seed" "$code" "$picks" \
        "$(grep -oE '\[rl\] rollout success [0-9]+/[0-9]+' "$log" | tail -1)"
}

t0=$(date +%s)
echo "[p58] battery start $(date '+%F %T')"
for seed in "${SEEDS[@]}"; do
    run_one A "" "$seed" 15
    # shellcheck disable=SC2086
    run_one B "$ARM_B_ENV" "$seed" 1
done
t1=$(date +%s)
echo "[p58] battery end $(date '+%F %T') wall=$((t1 - t0))s"

{
    echo "# P58 phase 1 pins after ($(date '+%F %T'))"
    md5sum "$CKPT" src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
        src/fruit_sorting/fruits.py src/fruit_sorting/scene.py \
        src/fruit_sorting/control.py src/fruit_sorting/policy/trigger.py \
        configs/arm_parks.json configs/motion_reference.json \
        configs/motion_reference_twoline.json
    echo "# battery wall $((t1 - t0))s"
} > logs/p58/p1/P1_tree_md5_after.txt

echo "[p58] report"
python3 logs/p58/p1_report.py --dir logs/p58/p1 \
    > logs/p58/p1_report.txt 2>&1
echo "[p58] report exit=$?"
echo "[p58] done $(date '+%F %T')"
