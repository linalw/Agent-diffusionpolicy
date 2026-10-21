#!/bin/bash
# P30-A verification batch: the rail census' simulator arms.
#
#   logs/p30a/run_p30a.sh            # everything (probes, acceptance pair, battery quad)
#   ONLY=probe|accept|battery logs/p30a/run_p30a.sh
#
# Every run goes through `scripts/154_claim_run.sh` (never kill another lane's
# sim, abort on overlap, stall guard) and `scripts/run.sh` (the fd-limit wrapper).
# The two-line battery repeats the P12-A.2 anchor exactly (two-line + patch sheet
# + balanced mix, SEED=11, ATTEMPTS=20, real mass) so `logs/p12a2/10_seed11_mass.log`
# (11/20) is the cross-tree reference; the A/B itself is same-tree, both arms.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
only=${ONLY:-all}
mkdir -p logs/p30a

run() {  # run <simlog> <env...>   -- claim_run writes the sim output to <simlog>
    local log=$1; shift
    echo "[p30a] START $(date +%H:%M:%S) $log :: $*"
    RUN_LIMIT=${RUN_LIMIT:-2400} scripts/154_claim_run.sh "$log" "$@" \
        > "${log%.log}_driver.log" 2>&1
    echo "[p30a] exit=$? $(date +%H:%M:%S) $log"
    return 0
}

run_accept() {  # run_accept <name> <env...>  -- accept.sh owns the sim log
    local name=$1; shift
    echo "[p30a] START $(date +%H:%M:%S) $name (acceptance)"
    RUN_LIMIT=${RUN_LIMIT:-1800} scripts/154_claim_run.sh "logs/p30a/${name}_driver.log" \
        ACCEPT_LOG="logs/p30a/${name}.log" SKIP_SELFCHECK=1 \
        "$@" scripts/accept.sh > /dev/null 2>&1
    echo "[p30a] exit=$? $(date +%H:%M:%S) $name"
    return 0
}

if [ "$only" = all ] || [ "$only" = probe ]; then
    # (a) the grasp-side null: the descent's stop is the belt slab, not a rail.
    run logs/p30a/10_probe_parts_default.log scripts/run.sh scripts/47_robot_collision.py
    run logs/p30a/11_probe_rails_on.log \
        FRUIT_RAILS=1 scripts/run.sh scripts/47_robot_collision.py
    run logs/p30a/12_probe_output_belts.log \
        FRUIT_PARTS=environment,pedestal,robot,conveyor,output_belts \
        scripts/run.sh scripts/47_robot_collision.py
    run logs/p30a/13_probe_output_belts_outer.log \
        FRUIT_OUTPUT_RAILS=outer FRUIT_PARTS=environment,pedestal,robot,conveyor,output_belts \
        scripts/run.sh scripts/47_robot_collision.py
fi

if [ "$only" = all ] || [ "$only" = accept ]; then
    # (b) the shipped acceptance (the B1c-flip branch reads 7/10) and the rail arm.
    run_accept 01_accept_control
    run_accept 02_accept_rails_outer FRUIT_OUTPUT_RAILS=outer
    run_accept 03_accept_rails_outer_lift0 FRUIT_OUTPUT_RAILS=outer FRUIT_OPENARM_TRANSFER_LIFT=0
fi

if [ "$only" = all ] || [ "$only" = lift ]; then
    # (d) the viable-lift pair: at a 40 mm-lower transfer the *rail* is the binding
    # constraint (payload bottom ~1.380 vs the rail top 1.385, the slab top 1.350),
    # so removing the inner rail is the difference between a 5 mm rail contact and
    # a 30 mm slab clearance.
    run_accept 04_accept_lift040 FRUIT_OPENARM_TRANSFER_LIFT=0.04
    run_accept 05_accept_rails_outer_lift040 FRUIT_OUTPUT_RAILS=outer FRUIT_OPENARM_TRANSFER_LIFT=0.04
fi

if [ "$only" = all ] || [ "$only" = battery ]; then
    # (c) the P12-A.2 anchor, seed 11, 20 attempts; the arms differ only in the rail.
    TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
         FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 HEADLESS=1
         FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1
         FRUIT_CARRY_MONITOR_DIAG=1 FRUIT_PHYSICS_REAL_MASS=1 SEED=11)
    run logs/p30a/20_patch_control.log "${TWO[@]}" \
        scripts/run.sh scripts/20_pick_place.py
    run logs/p30a/21_patch_rails_outer.log "${TWO[@]}" FRUIT_OUTPUT_RAILS=outer \
        scripts/run.sh scripts/20_pick_place.py
    run logs/p30a/22_patch_rails_outer_lift0.log "${TWO[@]}" FRUIT_OUTPUT_RAILS=outer \
        FRUIT_OPENARM_TRANSFER_LIFT=0 scripts/run.sh scripts/20_pick_place.py
    run logs/p30a/23_patch_lift0.log "${TWO[@]}" FRUIT_OPENARM_TRANSFER_LIFT=0 \
        scripts/run.sh scripts/20_pick_place.py
fi
echo "[p30a] DONE $(date +%H:%M:%S)"
