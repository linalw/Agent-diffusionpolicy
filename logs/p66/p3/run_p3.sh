#!/usr/bin/env bash
# P66 phase 3: the clearance-cost ladder (logs/p66/DEVIATION.md, Oracle gate 2).
#
#   bash logs/p66/p3/run_p3.sh
#
# The cell: 5 seeds (77/101/202/303/404) x 15 picks, interleaved
# control -> 0.24 -> 0.20, one claim per run.
#
#   control  FRUIT_LIFT_DZ=+0.08  -> the shipped lift end, belt_top + 0.36
#   C24      FRUIT_LIFT_DZ=-0.04  -> belt_top + 0.24   (phase-3 candidate)
#   C20      FRUIT_LIFT_DZ=-0.08  -> belt_top + 0.20   (phase-2 L2, the reference)
#
# (`FRUIT_LIFT_DZ` is the height above `tasks.jaw_target("grasp_lift")`'s
# `belt_top + 0.28` base and replaces the hand's `FRUIT_OPENARM_TRANSFER_LIFT`
# 0.08 add for that leg. The brief's `-0.12/-0.16` are `target - 0.36` and would
# land at 0.16/0.12 m under this base - `logs/p66/DEVIATION.md` D4. The control
# is **explicit** (+0.08) on purpose: it makes the phase-3 default flip inert in
# this batch, so all three arms print `(explicit)` and the comparison cannot be
# confounded by the adoption package.)
#
# Instruments, identical in all three arms: `FRUIT_CARRY_DIAG=1` (the P63/P65
# rows plus P66's `drift_end`/`res_end`/`dz_end` and the new `clr=`) and
# `FRUIT_CARRY_ATTITUDE=1` (P39's `[attitude]` row - the `|tool_y|` dose).
# `FRUIT_MOTION_REPORT` stays **unset**: the `clr` field carries the clearance
# per carry leg, so the motion monitor (the [motion] block) is not needed and its
# absence keeps the leg's work identical across arms.
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
#   FRUIT_IK_MAX_STEP / FRUIT_IK_RATE / FRUIT_MOTION_REPORT
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
mkdir -p logs/p66/p3/rollouts

CKPT=checkpoints/moe_v13s/policy_best.pt
SCEN_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1"
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
SEEDS=(77 101 202 303 404)
ARMS=(control:0.08 C24:-0.04 C20:-0.08)

{
    echo "# P66 phase 3 header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD) + the uncommitted P66 phase-2/3 instrument + FRUIT_LIFT_DZ"
    md5sum "$CKPT" \
        src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/fruits.py src/fruit_sorting/scene.py \
        src/fruit_sorting/control.py src/fruit_sorting/meshes.py \
        src/fruit_sorting/policy/trigger.py src/fruit_sorting/policy/runtime.py \
        configs/arm_parks.json configs/waypoints.json configs/waypoints_oriented.json \
        configs/motion_reference.json configs/motion_reference_twoline.json \
        scripts/110_rl_rollout.py scripts/113_rl_report.py scripts/154_claim_run.sh \
        scripts/235_p65_lift_selftest.py scripts/236_p66_lift_selftest.py \
        scripts/selfcheck.sh logs/p66/DEVIATION.md logs/p66/p3/run_p3.sh
    echo "# scenario: $SCEN_ENV"
    echo "# shipped profile: no supply env (FRUIT_FEED_CADENCE / FRUIT_SUPPLY_BAND_INTERLOCK / FRUIT_DIRECT_FEED all unset -> on for direct)"
    echo "# arms (all EXPLICIT, so the phase-3 direct default is inert here):"
    echo "#   control FRUIT_LIFT_DZ=+0.08 -> lift end belt_top+0.36 (the shipped height)"
    echo "#   C24     FRUIT_LIFT_DZ=-0.04 -> belt_top+0.24"
    echo "#   C20     FRUIT_LIFT_DZ=-0.08 -> belt_top+0.20 (phase-2 L2)"
    echo "# interleave: per seed control -> C24 -> C20, one claim per run"
    echo "# NOT set : FRUIT_DIRECT_CONTINUOUS, FRUIT_POLICY_TRIGGER_ACQ, FRUIT_ARM_PARK, FRUIT_GRASP_LEFT_TOPDOWN, FRUIT_GRASP_LEFT_PRECOMP, FRUIT_CARRY_HOLD_QUAT, FRUIT_SEAT_DIAG, FRUIT_ACQ_DIAG, FRUIT_MOTION_REPORT, FRUIT_IK_MAX_STEP, FRUIT_IK_RATE"
    echo "# harness : $HARNESS_ENV ; ckpt=$CKPT ; --episodes 15 --seeds <seed> --out logs/p66/p3/rollouts"
    echo "# SEEDS=${SEEDS[*]} policy_seed=11"
} > logs/p66/p3/header.txt
cat logs/p66/p3/header.txt
md5sum src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
    src/fruit_sorting/fruits.py src/fruit_sorting/policy/trigger.py \
    configs/arm_parks.json > logs/p66/p3/tree_md5_before.txt

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [p3] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

run_one() {
    local arm=$1 seed=$2 dz=$3
    local log="logs/p66/p3/${arm}_${seed}.log"
    wait_for_sim
    echo "  [p3] $arm seed $seed dz=$dz start $(date +%H:%M:%S)"
    RUN_LIMIT=3600 scripts/154_claim_run.sh "$log" \
        $HARNESS_ENV $SCEN_ENV FRUIT_LIFT_DZ="$dz" \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
        --presentation direct --episodes 15 --seeds "$seed" \
        --out logs/p66/p3/rollouts
    local rc=$?
    echo "  [p3] $arm seed $seed exit=$rc $(date +%H:%M:%S)"
    return $rc
}

fail=0
for seed in "${SEEDS[@]}"; do
    for spec in "${ARMS[@]}"; do
        arm=${spec%%:*}
        dz=${spec##*:}
        if ! run_one "$arm" "$seed" "$dz"; then
            echo "  [p3] $arm seed $seed failed; one retry $(date +%H:%M:%S)"
            if ! run_one "$arm" "$seed" "$dz"; then
                echo "  [p3] $arm seed $seed failed twice"
                fail=1
            fi
        fi
    done
done

md5sum src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
    src/fruit_sorting/fruits.py src/fruit_sorting/policy/trigger.py \
    configs/arm_parks.json > logs/p66/p3/tree_md5_after.txt
if ! diff -q logs/p66/p3/tree_md5_before.txt logs/p66/p3/tree_md5_after.txt >/dev/null; then
    echo "  [p3] WARNING: tree md5s changed during the batch"
fi
echo "[p3] batch end $(date '+%F %T') fail=$fail"
exit "$fail"
