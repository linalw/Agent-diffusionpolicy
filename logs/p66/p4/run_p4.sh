#!/usr/bin/env bash
# P66 phase 4: the rail-crossing clearance read (`logs/p66/P4_RESULTS.md`).
#
#   bash logs/p66/p4/run_p4.sh
#
# Gate (a) of `logs/p66/P3_RESULTS.md`: the `[carry]` row's `clr=` used to be the
# leg **minimum** (which includes the phase where the payload is still over the
# input belt), so it could not answer "does the lowered lift clip the output rail
# at the crossing". This batch reads the **phase-4 reduction**: `clr=` = the
# sample at the first tick whose |payload y| reaches the inner rail's centreline
# (0.4125 m), `clr_win=` = the minimum inside the rail's 25 mm footprint (the
# transfer segment), `clr_min=` = the leg minimum (the old field's meaning).
#
# Two arms, one seed, the phase-3 cell verbatim otherwise:
#   control  FRUIT_LIFT_DZ=+0.08  -> lift end belt_top + 0.36 (the shipped height)
#   L2       FRUIT_LIFT_DZ=-0.08  -> belt_top + 0.20 (phase-2/3's L2 rung)
#
# `FRUIT_LIFT_DZ` is the height above `tasks.jaw_target("grasp_lift")`'s
# `belt_top + 0.28` base and **replaces** the hand's `FRUIT_OPENARM_TRANSFER_LIFT`
# 0.08 add on that leg, so `+0.08` is the shipped 0.36 m and `-0.08` the 0.20 m
# rung. The control is **explicit**: the phase-3 package made the `direct`
# presentation's default the 0.20 m rung, so an unset value is *not* the control
# (`logs/p66/DEVIATION.md` D4/D5).
#
# Instruments: `FRUIT_CARRY_DIAG=1` (the row that carries all three clearance
# fields) and `FRUIT_CARRY_ATTITUDE=1`; `FRUIT_MOTION_REPORT` unset. Scenario env
# is the phase-3 cell's, so a correct print-only change replays the phase-3 run
# branch: control should be `[fruit]`-identical to `logs/p66/p3/control_77.log`
# and L2 to `logs/p66/p3/C20_77.log`.
#
# Nothing here edits src/, configs/ or scripts/.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
mkdir -p logs/p66/p4/rollouts

CKPT=checkpoints/moe_v13s/policy_best.pt
SCEN_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1"
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
SEEDS=(${SEEDS:-77})
ARMS=(control:0.08 L2:-0.08)
EPISODES=${EPISODES:-15}

{
    echo "# P66 phase 4 header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD) + the uncommitted P66 phase-4 clr reduction (_clearance_field / _output_rail_y)"
    md5sum "$CKPT" \
        src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/fruits.py src/fruit_sorting/scene.py \
        src/fruit_sorting/control.py src/fruit_sorting/policy/trigger.py \
        configs/arm_parks.json configs/waypoints.json configs/waypoints_oriented.json \
        configs/motion_reference.json configs/motion_reference_twoline.json \
        scripts/110_rl_rollout.py scripts/236_p66_lift_selftest.py scripts/selfcheck.sh
    echo "# scenario (the phase-3 cell verbatim): $SCEN_ENV"
    echo "# arms: control FRUIT_LIFT_DZ=+0.08 -> 0.36 m (shipped); L2 FRUIT_LIFT_DZ=-0.08 -> 0.20 m"
    echo "# crossing: |payload y| >= the inner rail's centreline (0.4125 m, _output_rail_y)"
    echo "# floor   : +33 mm to the rail's top (logs/p30a/RAILS_DESIGN.md)"
    echo "# harness : $HARNESS_ENV ; ckpt=$CKPT ; --episodes $EPISODES --seeds ${SEEDS[*]} --out logs/p66/p4/rollouts"
} > logs/p66/p4/header.txt
cat logs/p66/p4/header.txt

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [p4] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

run_one() {
    local arm=$1 seed=$2 dz=$3
    local log="logs/p66/p4/${arm}_${seed}.log"
    wait_for_sim
    echo "  [p4] $arm seed $seed dz=$dz start $(date +%H:%M:%S)"
    RUN_LIMIT=3600 scripts/154_claim_run.sh "$log" \
        $HARNESS_ENV $SCEN_ENV FRUIT_LIFT_DZ="$dz" \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
        --presentation direct --episodes "$EPISODES" --seeds "$seed" \
        --out logs/p66/p4/rollouts
    local rc=$?
    echo "  [p4] $arm seed $seed exit=$rc $(date +%H:%M:%S)"
    return $rc
}

fail=0
for seed in "${SEEDS[@]}"; do
    for spec in "${ARMS[@]}"; do
        arm=${spec%%:*}
        dz=${spec##*:}
        if ! run_one "$arm" "$seed" "$dz"; then
            echo "  [p4] $arm seed $seed failed; one retry $(date +%H:%M:%S)"
            if ! run_one "$arm" "$seed" "$dz"; then
                echo "  [p4] $arm seed $seed failed twice"
                fail=1
            fi
        fi
    done
done

echo "[p4] batch end $(date '+%F %T') fail=$fail"
exit "$fail"
