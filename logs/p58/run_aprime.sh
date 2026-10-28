#!/usr/bin/env bash
# P58 phase 3a: cell A' — the supply triple on the SHIPPED per-pick interface.
# Registered in logs/p58/PREREG_A_APRIME.md (written before this run).
#
#   nohup bash logs/p58/run_aprime.sh > logs/p58/p3a/Ap_batch_outer.log 2>&1 &
#
# One arm, three seeds, one claim per run. The cell is the phase-1 B stack
# MINUS the multi-pick episode: `--episodes 15` (the shipped per-pick interface)
# with the cadence + band interlock + direct feeder.
#
# Deliberately NOT set (the shipped `direct` defaults, PREREG §1):
#   FRUIT_DIRECT_CONTINUOUS   (this is the cell's whole point)
#   FRUIT_POLICY_TRIGGER_ACQ  (P54: resolves on for `direct`)
#   FRUIT_ARM_PARK            (P43: resolves `back` for `direct`)
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p58/p3a

CKPT=checkpoints/moe_v13s/policy_best.pt
PATCH_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25"
SCEN_ENV="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1"
DIAG_ENV="FRUIT_BED_DIAG=1"
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
TRIPLE_ENV="FRUIT_FEED_CADENCE=1 FRUIT_SUPPLY_BAND_INTERLOCK=1 FRUIT_SUPPLY_BAND_MAX=3 FRUIT_DIRECT_FEED=1"

SEEDS=(77 101 202)
POLICY_SEED=11

{
    echo "# P58 phase 3a cell A' header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)"
    md5sum "$CKPT" \
        src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
        src/fruit_sorting/fruits.py src/fruit_sorting/scene.py \
        src/fruit_sorting/control.py src/fruit_sorting/meshes.py \
        src/fruit_sorting/policy/trigger.py src/fruit_sorting/policy/runtime.py \
        configs/arm_parks.json configs/motion_reference.json \
        configs/motion_reference_twoline.json \
        scripts/110_rl_rollout.py scripts/113_rl_report.py scripts/154_claim_run.sh \
        logs/p58/PREREG_A_APRIME.md logs/p58/run_aprime.sh
    echo "# scenario: $PATCH_ENV $SCEN_ENV $DIAG_ENV"
    echo "# triple  : $TRIPLE_ENV"
    echo "# NOT set : FRUIT_DIRECT_CONTINUOUS (shipped per-pick interface), FRUIT_POLICY_TRIGGER_ACQ (P54 on), FRUIT_ARM_PARK (P43 back)"
    echo "# harness : $HARNESS_ENV ; ckpt=$CKPT ; --episodes 15 --seeds <seed>"
    echo "# SEEDS=${SEEDS[*]} policy_seed=$POLICY_SEED, one claim per run"
} > logs/p58/p3a/Ap_header.txt
cat logs/p58/p3a/Ap_header.txt

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [p3a] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

run_one() {
    local seed=$1 log="logs/p58/p3a/Ap_$1.log"
    wait_for_sim
    # shellcheck disable=SC2086
    RUN_LIMIT=1800 scripts/154_claim_run.sh "$log" \
        $PATCH_ENV $SCEN_ENV $DIAG_ENV $HARNESS_ENV $TRIPLE_ENV \
        FRUIT_POLICY_SEED="$POLICY_SEED" \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" --presentation direct \
        --episodes 15 --seeds "$seed"
    local code=$?
    printf '  A-prime seed %s: exit=%s picks=%s bed_rows=%s cont_rows=%s %s\n' \
        "$seed" "$code" \
        "$(grep -cE '\[rl\] episode [0-9]+: .* success=' "$log" 2>/dev/null || true)" \
        "$(grep -c '\[bed-sel\] attempt' "$log" 2>/dev/null || true)" \
        "$(grep -c '\[cont\]' "$log" 2>/dev/null || true)" \
        "$(grep -oE '\[rl\] rollout success [0-9]+/[0-9]+' "$log" | tail -1)"
}

t0=$(date +%s)
echo "[p3a] batch start $(date '+%F %T')"
for seed in "${SEEDS[@]}"; do
    run_one "$seed"
done
t1=$(date +%s)
echo "[p3a] batch end $(date '+%F %T') wall=$((t1 - t0))s"

{
    echo "# P58 phase 3a cell A' pins after ($(date '+%F %T'))"
    md5sum "$CKPT" src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
        src/fruit_sorting/fruits.py src/fruit_sorting/scene.py \
        src/fruit_sorting/control.py src/fruit_sorting/policy/trigger.py \
        configs/arm_parks.json configs/motion_reference.json \
        configs/motion_reference_twoline.json
    echo "# battery wall $((t1 - t0))s"
} > logs/p58/p3a/Ap_tree_md5_after.txt

echo "[p3a] report"
python3 logs/p58/Ap_report.py --dir logs/p58/p3a > logs/p58/Ap_report.txt 2>&1
echo "[p3a] report exit=$?"
echo "[p3a] done $(date '+%F %T')"
