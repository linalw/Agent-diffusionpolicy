#!/usr/bin/env bash
# P59 phase 2: the two catch-margin arms, one variable each.
#
#   nohup bash logs/p59/run_p2.sh > logs/p59/p2/batch_outer.log 2>&1 &
#
# Registered in logs/p59/PREREG_P2.md (written before any run):
#   A  cap 5        : FRUIT_SUPPLY_BAND_MAX=5 on the shipped profile
#   B  upstream edge: FRUIT_SUPPLY_TARGET_FROM=0.40 on the shipped profile
# The shipped profile = NO supply env at all (P58: the clock pair + the band
# interlock at cap 4 + the live feeder all resolve on for `direct`).
#
# Deliberately NOT set (the shipped `direct` defaults):
#   FRUIT_DIRECT_CONTINUOUS   (the shipped per-pick interface)
#   FRUIT_POLICY_TRIGGER_ACQ  (P54: resolves on for `direct`)
#   FRUIT_ARM_PARK            (P43: resolves `back` for `direct`)
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p59/p2

CKPT=checkpoints/moe_v13s/policy_best.pt
SCEN_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_BED_DIAG=1"
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1 FRUIT_POLICY_SEED=11"
SEEDS=(77 101 202)

{
    echo "# P59 phase 2 header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)  (working tree has the P59 gate-1 provenance-only edit)"
    md5sum "$CKPT" \
        src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
        src/fruit_sorting/fruits.py src/fruit_sorting/scene.py \
        src/fruit_sorting/control.py src/fruit_sorting/meshes.py \
        src/fruit_sorting/policy/trigger.py src/fruit_sorting/policy/runtime.py \
        configs/arm_parks.json configs/motion_reference.json \
        configs/motion_reference_twoline.json \
        scripts/110_rl_rollout.py scripts/113_rl_report.py scripts/154_claim_run.sh \
        logs/p59/PREREG_P2.md logs/p59/run_p2.sh
    echo "# scenario: $SCEN_ENV"
    echo "# shipped profile: no supply env (FRUIT_FEED_CADENCE / FRUIT_SUPPLY_BAND_INTERLOCK / FRUIT_DIRECT_FEED all unset -> on for direct)"
    echo "# arm A: FRUIT_SUPPLY_BAND_MAX=5 (one variable)   arm B: FRUIT_SUPPLY_TARGET_FROM=0.40 (one variable)"
    echo "# NOT set : FRUIT_DIRECT_CONTINUOUS, FRUIT_POLICY_TRIGGER_ACQ, FRUIT_ARM_PARK (shipped defaults)"
    echo "# harness : $HARNESS_ENV ; ckpt=$CKPT ; --episodes 15 --seeds <seed>"
    echo "# SEEDS=${SEEDS[*]} policy_seed=11, one claim per run"
} > logs/p59/p2/header.txt
cat logs/p59/p2/header.txt

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [p2] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

run_one() {
    local arm=$1 seed=$2 extra=$3 log="logs/p59/p2/$1_$2.log"
    wait_for_sim
    echo "  [p2] arm $arm seed $seed start $(date +%H:%M:%S)  extra='$extra'"
    RUN_LIMIT=2700 scripts/154_claim_run.sh "$log" \
        $HARNESS_ENV $SCEN_ENV $extra \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
        --presentation direct --episodes 15 --seeds "$seed"
    local rc=$?
    echo "  [p2] arm $arm seed $seed exit=$rc $(date +%H:%M:%S)"
}

for seed in "${SEEDS[@]}"; do
    run_one A "$seed" "FRUIT_SUPPLY_BAND_MAX=5"
done
for seed in "${SEEDS[@]}"; do
    run_one B "$seed" "FRUIT_SUPPLY_TARGET_FROM=0.40"
done

md5sum src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
    src/fruit_sorting/fruits.py src/fruit_sorting/scene.py \
    src/fruit_sorting/control.py src/fruit_sorting/meshes.py \
    src/fruit_sorting/policy/trigger.py src/fruit_sorting/policy/runtime.py \
    configs/arm_parks.json configs/motion_reference.json \
    configs/motion_reference_twoline.json \
    scripts/110_rl_rollout.py scripts/113_rl_report.py scripts/154_claim_run.sh \
    > logs/p59/p2/tree_md5_after.txt
echo "[p2] batch end $(date '+%F %T')"
