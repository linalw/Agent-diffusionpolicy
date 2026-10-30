#!/usr/bin/env bash
# P67: the place-leg **climb** re-shape of P66 phase 4's failed rail-crossing gate.
#
#   bash logs/p67/run_p67.sh
#
# The problem P66 left (`logs/p66/P4_RESULTS.md`): on the 0.20 m lift rung
# (`FRUIT_LIFT_DZ=-0.08`) the left arm's held place transit crosses the output
# rail's centreline at +5 mm against the +33 mm access floor, because the crossing
# sits 82.5 % of the way along the leg's y span (0.175:1 with the lift height).
# Only the height the transit STARTS at is 1:1 with the crossing, so P67 prepends
# a short vertical climb at the place leg's start (`FRUIT_LIFT_CLIMB`, metres,
# direct + left only, default off; prepended waypoint, `tasks.lift_climb_commands`).
#
# Two arms, one seed, the phase-3/P4 scenario verbatim otherwise:
#   A (control) FRUIT_LIFT_DZ=-0.08                      -> the P66 L2 arm (+5 mm)
#   B (climb)   FRUIT_LIFT_DZ=-0.08 FRUIT_LIFT_CLIMB=0.18 -> solving
#     z_cross = transfer - 0.175*(transfer - lift_end - climb) for the +33 mm floor
#     gives climb = 0.179 m (see scripts/237_p67_climb_selftest.py, which pins the
#     identity and the solve), so 0.18 is the rounded-up value, not a tuned one.
#
# The same arm as P4's L2 on purpose: the A/B is a same-batch pair (the direct loop
# is not reproducible - rendered frames), so the comparison is A vs B here, and
# P4's L2 is the cross-check rather than the control.
#
# Instruments: FRUIT_CARRY_DIAG=1 (the row that carries clr=/clr_win=/drift_end=
# and the tick counts) and FRUIT_CARRY_ATTITUDE=1 (the place leg's achieved tilt).
#
# Nothing here edits src/, configs/ or scripts/.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p67/rollouts

CKPT=checkpoints/moe_v13s/policy_best.pt
SCEN_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1"
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
SEEDS=(${SEEDS:-77})
EPISODES=${EPISODES:-15}
CLIMB=${CLIMB:-0.18}

{
    echo "# P67 header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD) + the uncommitted P67 lift_climb knob (tasks._carry + rl_env.resolve_lift_climb)"
    md5sum "$CKPT" \
        src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/fruits.py src/fruit_sorting/scene.py \
        src/fruit_sorting/control.py src/fruit_sorting/policy/trigger.py \
        configs/arm_parks.json configs/waypoints.json configs/waypoints_oriented.json \
        configs/motion_reference.json configs/motion_reference_twoline.json \
        scripts/110_rl_rollout.py scripts/237_p67_climb_selftest.py scripts/selfcheck.sh
    echo "# scenario (the phase-3 / P4 cell verbatim): $SCEN_ENV"
    echo "# arms: A control FRUIT_LIFT_DZ=-0.08 (the 0.20 m rung, P66 L2); B = A + FRUIT_LIFT_CLIMB=$CLIMB"
    echo "# crossing: |payload y| >= the inner rail's centreline (0.4125 m, _output_rail_y)"
    echo "# floor   : +33 mm to the rail's top (logs/p30a/RAILS_DESIGN.md)"
    echo "# climb derivation: z_cross = transfer - 0.175*(transfer - lift_end - climb);"
    echo "#   lift_end 1.370, transfer 1.530, z_cross(0) = 1.502 (+5 mm measured);"
    echo "#   +33 mm needs z_cross 1.533 -> climb = (1.533-1.502)/0.175 = 0.179 m -> 0.18"
    echo "# harness : $HARNESS_ENV ; ckpt=$CKPT ; --episodes $EPISODES --seeds ${SEEDS[*]} --out logs/p67/rollouts"
} > logs/p67/header.txt
cat logs/p67/header.txt

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [p67] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

run_one() {
    local arm=$1 seed=$2
    local log="logs/p67/${arm}_${seed}.log"
    local extra=""
    if [ "$arm" = "B" ]; then extra="FRUIT_LIFT_CLIMB=$CLIMB"; fi
    wait_for_sim
    echo "  [p67] $arm seed $seed start $(date +%H:%M:%S)"
    RUN_LIMIT=3600 scripts/154_claim_run.sh "$log" \
        $HARNESS_ENV $SCEN_ENV FRUIT_LIFT_DZ=-0.08 $extra \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
        --presentation direct --episodes "$EPISODES" --seeds "$seed" \
        --out logs/p67/rollouts
    local rc=$?
    echo "  [p67] $arm seed $seed exit=$rc $(date +%H:%M:%S)"
    return $rc
}

fail=0
for seed in "${SEEDS[@]}"; do
    for arm in A B; do
        if ! run_one "$arm" "$seed"; then
            echo "  [p67] $arm seed $seed failed; one retry $(date +%H:%M:%S)"
            if ! run_one "$arm" "$seed"; then
                echo "  [p67] $arm seed $seed failed twice"
                fail=1
            fi
        fi
    done
done

echo "[p67] batch end $(date '+%F %T') fail=$fail"
exit "$fail"
