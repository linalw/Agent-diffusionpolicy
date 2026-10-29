#!/usr/bin/env bash
# P61 phase 2: the slip-**direction** cell on the direct line (logs/p61/PREREG.md).
#
#   nohup bash logs/p61/p2/run_p2.sh > logs/p61/p2/batch_outer.log 2>&1 &
#
# P60 phase 3's cell verbatim (the F3 comparator, logs/p60/p3/D_{77,101,202}.log)
# plus FRUIT_MOTION_REPORT=1 (endpoint P3). The only difference from the P60 tree
# is the reporting-only `slip_xyz=` field in the [carry] row (tasks.py), whose
# md5 is pinned below; nothing in this script edits src/ or configs/.
#
# Deliberately NOT set (the shipped `direct` defaults):
#   FRUIT_DIRECT_CONTINUOUS   (the shipped per-pick interface)
#   FRUIT_POLICY_TRIGGER_ACQ  (P54: resolves on for `direct`)
#   FRUIT_ARM_PARK            (P43: resolves `back` for `direct`)
#   FRUIT_CARRY_GUARD / FRUIT_CARRY_RELIEF / FRUIT_CARRY_MONITOR (the diag must not actuate)
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
mkdir -p logs/p61/p2

CKPT=checkpoints/moe_v13s/policy_best.pt
SCEN_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_MOTION_REPORT=1"
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1 FRUIT_POLICY_SEED=11"
SEEDS=(77 101 202)

{
    echo "# P61 phase 2 header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD) + the uncommitted P61 slip_xyz instrument (reporting only)"
    md5sum "$CKPT" \
        src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
        src/fruit_sorting/fruits.py src/fruit_sorting/scene.py \
        src/fruit_sorting/control.py src/fruit_sorting/meshes.py \
        src/fruit_sorting/policy/trigger.py src/fruit_sorting/policy/runtime.py \
        configs/arm_parks.json configs/motion_reference.json \
        configs/motion_reference_twoline.json configs/waypoints_oriented.json \
        scripts/110_rl_rollout.py scripts/113_rl_report.py scripts/154_claim_run.sh \
        scripts/231_p61_slip_selftest.py scripts/selfcheck.sh \
        logs/p61/p2/run_p2.sh logs/p61/PREREG.md
    echo "# scenario: $SCEN_ENV"
    echo "# shipped profile: no supply env (FRUIT_FEED_CADENCE / FRUIT_SUPPLY_BAND_INTERLOCK / FRUIT_DIRECT_FEED all unset -> on for direct)"
    echo "# instrument: FRUIT_CARRY_DIAG=1 + FRUIT_MOTION_REPORT=1 (both default off; reporting only, guard/relief/monitor unset)"
    echo "# NOT set : FRUIT_DIRECT_CONTINUOUS, FRUIT_POLICY_TRIGGER_ACQ, FRUIT_ARM_PARK, FRUIT_CARRY_GUARD, FRUIT_CARRY_RELIEF, FRUIT_CARRY_MONITOR"
    echo "# F3 control: logs/p60/p3/D_{77,101,202}.log (same scenario/checkpoint; tree differs only by slip_xyz)"
    echo "# harness : $HARNESS_ENV ; ckpt=$CKPT ; --episodes 15 --seeds <seed> --out logs/p61/p2/rollouts"
    echo "# SEEDS=${SEEDS[*]} policy_seed=11, one claim per run"
} > logs/p61/p2/header.txt
cat logs/p61/p2/header.txt
md5sum src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
    src/fruit_sorting/fruits.py src/fruit_sorting/policy/trigger.py \
    configs/arm_parks.json > logs/p61/p2/tree_md5_before.txt

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
    local seed=$1 log="logs/p61/p2/S_$1.log"
    wait_for_sim
    echo "  [p2] slip seed $seed start $(date +%H:%M:%S)"
    RUN_LIMIT=2700 scripts/154_claim_run.sh "$log" \
        $HARNESS_ENV $SCEN_ENV \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
        --presentation direct --episodes 15 --seeds "$seed" \
        --out logs/p61/p2/rollouts
    local rc=$?
    echo "  [p2] slip seed $seed exit=$rc $(date +%H:%M:%S)"
    return $rc
}

fail=0
for seed in "${SEEDS[@]}"; do
    if ! run_one "$seed"; then
        echo "  [p2] seed $seed failed; F2: one retry $(date +%H:%M:%S)"
        run_one "$seed" || { echo "  [p2] seed $seed failed twice"; fail=1; }
    fi
done

md5sum src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
    src/fruit_sorting/fruits.py src/fruit_sorting/policy/trigger.py \
    configs/arm_parks.json > logs/p61/p2/tree_md5_after.txt
if ! diff -q logs/p61/p2/tree_md5_before.txt logs/p61/p2/tree_md5_after.txt >/dev/null; then
    echo "  [p2] WARNING: tree md5s changed during the batch"
fi
echo "[p2] batch end $(date '+%F %T') fail=$fail"
exit "$fail"
