#!/usr/bin/env bash
# P75: the place leg's first ~40 ticks at 1-tick resolution
# (logs/p75/METHOD.md, md5 c3683b5e421be4eb1875d0c8dea4f532).
#
#   SEEDS="77 101" bash logs/p75/run_p75.sh
#
# One arm only - the trace ON at 60 ticks. This is a **diagnostic**: it arms the
# carry block and adds two reporting reads per traced tick, so its run may differ
# from the shipped one and NO RATE may be quoted from it. The shipped default's
# inertness is proven separately by `scripts/accept.sh` (346 `[fruit]` lines vs
# logs/p73/accept_noharm.log).
#
# The cell is the P66-phase-3 / P71-phase-2 / P73 / P74 scenario verbatim, with
# FRUIT_PLACE_ONSET_TRACE=60 added.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p75/direct logs/p75/rollouts

SEEDS=${SEEDS:-"77 101"}
CKPT=checkpoints/moe_v13s/policy_best.pt
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
SCEN_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1 FRUIT_MOTION_REPORT=1 FRUIT_PLACE_ONSET_TRACE=60"

{
    echo "# P75 header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)"
    echo "# prereg: $(cat logs/p75/PREREG.md5 2>/dev/null | tr '\n' ' ')"
    md5sum "$CKPT" \
        src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/assets.py src/fruit_sorting/conveyor.py \
        src/fruit_sorting/fruits.py src/fruit_sorting/scene.py \
        src/fruit_sorting/meshes.py src/fruit_sorting/control.py \
        src/fruit_sorting/motion.py \
        src/fruit_sorting/policy/trigger.py src/fruit_sorting/policy/runtime.py \
        configs/arm_parks.json configs/waypoints.json \
        configs/motion_reference.json configs/motion_reference_twoline.json \
        scripts/110_rl_rollout.py scripts/154_claim_run.sh \
        scripts/241_p75_place_trace_selftest.py scripts/242_p75_classify.py \
        scripts/235_p65_lift_selftest.py scripts/240_p73_tilt_selftest.py \
        scripts/selfcheck.sh
    echo "# seeds: {$SEEDS}; one arm - FRUIT_PLACE_ONSET_TRACE=60 (diagnostic, no rate)"
    echo "# scenario (P66 phase-3 / P71 phase-2 / P73 / P74 verbatim + the trace): $SCEN_ENV"
    echo "# harness: $HARNESS_ENV"
} > logs/p75/header.txt
cat logs/p75/header.txt

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [p75] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

fail=0
for seed in $SEEDS; do
    log="logs/p75/direct/A_${seed}.log"
    wait_for_sim
    echo "  [p75] trace seed $seed start $(date +%H:%M:%S)"
    RUN_LIMIT=3600 scripts/154_claim_run.sh "$log" \
        $HARNESS_ENV $SCEN_ENV \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
        --presentation direct --episodes 15 --seeds "$seed" \
        --out "logs/p75/rollouts/A_${seed}"
    rc=$?
    echo "  [p75] seed $seed exit=$rc $(date +%H:%M:%S)"
    tail -3 "$log"
    [ "$rc" -eq 0 ] || fail=1
done

echo "[p75] end $(date '+%F %T') fail=$fail"
exit "$fail"
