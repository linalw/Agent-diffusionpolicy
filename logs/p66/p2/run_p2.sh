#!/usr/bin/env bash
# P66 phase 2: the lift-end-height ladder (logs/p66/PREREG_P2.md).
#
#   bash logs/p66/p2/run_p2.sh
#
# The registered cell: 3 seeds (77/101/202) x 15 picks, interleaved
# control -> L1 -> L2 -> control, one claim per run.
#
#   control  FRUIT_LIFT_DZ unset      -> the shipped lift end, belt_top + 0.36
#   L1       FRUIT_LIFT_DZ=0.00       -> belt_top + 0.28
#   L2       FRUIT_LIFT_DZ=-0.08      -> belt_top + 0.20
#
# (`FRUIT_LIFT_DZ` is the height above `tasks.jaw_target("grasp_lift")`'s
# `belt_top + 0.28` base and replaces the hand's `FRUIT_OPENARM_TRANSFER_LIFT`
# 0.08 add for that leg, so the registered control row's `+0.08` is exactly the
# unset arm - `logs/p66/P2_RESULTS.md` section 1.)
#
# Instruments, identical in all four arms: `FRUIT_CARRY_DIAG=1` (the P63/P65
# rows plus P66's `drift_end`/`res_end`/`dz_end`) and `FRUIT_CARRY_ATTITUDE=1`
# (P39's `[attitude]` row - the registered achieved-belt-projection check needs
# the achieved tool axis, and it is one TCP read per leg, reporting only).
# `FRUIT_BED_DIAG=1` is the registered cell's own.
#
# Nothing here edits src/, configs/ or scripts/.
#
# Deliberately NOT set (the shipped `direct` defaults):
#   FRUIT_DIRECT_CONTINUOUS   (the shipped per-pick interface)
#   FRUIT_POLICY_TRIGGER_ACQ  (P54: resolves on for `direct`)
#   FRUIT_ARM_PARK            (P43: resolves `back` for `direct`)
#   FRUIT_GRASP_LEFT_TOPDOWN / FRUIT_GRASP_LEFT_PRECOMP (P62/P64: off)
#   FRUIT_CARRY_GUARD / FRUIT_CARRY_RELIEF / FRUIT_CARRY_MONITOR (the diag must not actuate)
#   FRUIT_CARRY_HOLD_QUAT     (the grip-attitude channel - stays unset)
#   FRUIT_IK_MAX_STEP / FRUIT_IK_RATE
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
mkdir -p logs/p66/p2/rollouts

CKPT=checkpoints/moe_v13s/policy_best.pt
SCEN_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1"
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
SEEDS=(77 101 202)

{
    echo "# P66 phase 2 header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD) + the uncommitted P66 lift-end instrument + FRUIT_LIFT_DZ"
    md5sum "$CKPT" \
        src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/fruits.py src/fruit_sorting/scene.py \
        src/fruit_sorting/control.py src/fruit_sorting/meshes.py \
        src/fruit_sorting/policy/trigger.py src/fruit_sorting/policy/runtime.py \
        configs/arm_parks.json configs/waypoints.json configs/waypoints_oriented.json \
        configs/motion_reference.json configs/motion_reference_twoline.json \
        scripts/110_rl_rollout.py scripts/113_rl_report.py scripts/154_claim_run.sh \
        scripts/236_p66_lift_selftest.py scripts/selfcheck.sh \
        logs/p66/p2/run_p2.sh logs/p66/PREREG_P2.md
    echo "# scenario: $SCEN_ENV"
    echo "# shipped profile: no supply env (FRUIT_FEED_CADENCE / FRUIT_SUPPLY_BAND_INTERLOCK / FRUIT_DIRECT_FEED all unset -> on for direct)"
    echo "# arms: control=FRUIT_LIFT_DZ unset (lift end belt_top+0.36); L1==0.00 (0.28); L2==-0.08 (0.20)"
    echo "# interleave: control -> L1 -> L2 -> control, per seed, one claim per run"
    echo "# NOT set : FRUIT_DIRECT_CONTINUOUS, FRUIT_POLICY_TRIGGER_ACQ, FRUIT_ARM_PARK, FRUIT_GRASP_LEFT_TOPDOWN, FRUIT_GRASP_LEFT_PRECOMP, FRUIT_CARRY_HOLD_QUAT, FRUIT_SEAT_DIAG, FRUIT_ACQ_DIAG, FRUIT_MOTION_REPORT, FRUIT_IK_MAX_STEP, FRUIT_IK_RATE"
    echo "# harness : $HARNESS_ENV ; ckpt=$CKPT ; --episodes 15 --seeds <seed> --out logs/p66/p2/rollouts"
    echo "# SEEDS=${SEEDS[*]} policy_seed=11"
} > logs/p66/p2/header.txt
cat logs/p66/p2/header.txt
md5sum src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
    src/fruit_sorting/fruits.py src/fruit_sorting/policy/trigger.py \
    configs/arm_parks.json > logs/p66/p2/tree_md5_before.txt

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
    local arm=$1 seed=$2 dz=$3
    local log="logs/p66/p2/${1}_${2}.log"
    wait_for_sim
    echo "  [p2] $arm seed $seed start $(date +%H:%M:%S)"
    if [ -n "$dz" ]; then
        RUN_LIMIT=3600 scripts/154_claim_run.sh "$log" \
            $HARNESS_ENV $SCEN_ENV FRUIT_LIFT_DZ="$dz" \
            scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
            --presentation direct --episodes 15 --seeds "$seed" \
            --out logs/p66/p2/rollouts
    else
        RUN_LIMIT=3600 scripts/154_claim_run.sh "$log" \
            $HARNESS_ENV $SCEN_ENV \
            scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
            --presentation direct --episodes 15 --seeds "$seed" \
            --out logs/p66/p2/rollouts
    fi
    local rc=$?
    echo "  [p2] $arm seed $seed exit=$rc $(date +%H:%M:%S)"
    return $rc
}

fail=0
for seed in "${SEEDS[@]}"; do
    if ! run_one C1 "$seed" ""; then
        echo "  [p2] C1 seed $seed failed; F1: one retry $(date +%H:%M:%S)"
        run_one C1 "$seed" "" || { echo "  [p2] C1 seed $seed failed twice"; fail=1; }
    fi
    if ! run_one L1 "$seed" "0.00"; then
        echo "  [p2] L1 seed $seed failed; F1: one retry $(date +%H:%M:%S)"
        run_one L1 "$seed" "0.00" || { echo "  [p2] L1 seed $seed failed twice"; fail=1; }
    fi
    if ! run_one L2 "$seed" "-0.08"; then
        echo "  [p2] L2 seed $seed failed; F1: one retry $(date +%H:%M:%S)"
        run_one L2 "$seed" "-0.08" || { echo "  [p2] L2 seed $seed failed twice"; fail=1; }
    fi
    if ! run_one C2 "$seed" ""; then
        echo "  [p2] C2 seed $seed failed; F1: one retry $(date +%H:%M:%S)"
        run_one C2 "$seed" "" || { echo "  [p2] C2 seed $seed failed twice"; fail=1; }
    fi
done

md5sum src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
    src/fruit_sorting/fruits.py src/fruit_sorting/policy/trigger.py \
    configs/arm_parks.json > logs/p66/p2/tree_md5_after.txt
if ! diff -q logs/p66/p2/tree_md5_before.txt logs/p66/p2/tree_md5_after.txt >/dev/null; then
    echo "  [p2] WARNING: tree md5s changed during the batch"
fi
echo "[p2] batch end $(date '+%F %T') fail=$fail"
exit "$fail"
