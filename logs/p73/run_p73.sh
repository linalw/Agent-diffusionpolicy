#!/usr/bin/env bash
# P73 phase 1: the place-transfer-height screen (logs/p73/PREREG.md).
#
#   SEEDS="77" bash logs/p73/run_p73.sh          # the registered first read
#   SEEDS="101 202" bash logs/p73/run_p73.sh     # the registered EXPANSION only
#   ARMS="C SLOW" SEEDS="77" bash logs/p73/run_p73.sh   # the conditional
#                                                # rotation-vs-acceleration arm
#
# The one variable is `FRUIT_OPENARM_TRANSFER_LIFT` (default 0.08), read in
# `jaw_target` for the openarm hand. On the direct line the left arm's
# `grasp_lift` is taken by the P71 `FRUIT_LIFT_DZ` override, so the knob moves
# that arm's **place transfer only**; the right's lift end moves too (registered
# limitation, PREREG §1).
#
# Every arm is one claim. The cell is the P66-phase-3 / P71-phase-2 scenario
# verbatim, so the C arm is comparable to the shipped corpus.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p73/direct logs/p73/rollouts

SEEDS=${SEEDS:-"77"}
ARMS=${ARMS:-"C T1 T2"}
CKPT=checkpoints/moe_v13s/policy_best.pt
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
SCEN_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1 FRUIT_MOTION_REPORT=1"

transfer_of() {
    case "$1" in
        C)    echo "0.08" ;;
        T1)   echo "0.14" ;;
        T2)   echo "0.20" ;;
        SLOW) echo "0.08" ;;
        *)    echo "?" ;;
    esac
}

arm_env() {
    local arm=$1 lift
    lift=$(transfer_of "$arm")
    local extra="FRUIT_OPENARM_TRANSFER_LIFT=$lift"
    # The conditional discriminator arm: the shipped transfer, the place profile
    # slowed to the P44 S1 value (same `jerk_limited` machinery, longer leg).
    if [ "$arm" = "SLOW" ]; then
        extra="$extra FRUIT_SPEED_PLACE=0.20"
    fi
    echo "$extra"
}

{
    echo "# P73 header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)"
    echo "# prereg: $(cat logs/p73/PREREG.md5 2>/dev/null | tr '\n' ' ')"
    md5sum "$CKPT" \
        src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/assets.py src/fruit_sorting/conveyor.py \
        src/fruit_sorting/fruits.py src/fruit_sorting/scene.py \
        src/fruit_sorting/meshes.py src/fruit_sorting/control.py \
        src/fruit_sorting/policy/trigger.py src/fruit_sorting/policy/runtime.py \
        configs/arm_parks.json configs/waypoints.json \
        configs/motion_reference.json configs/motion_reference_twoline.json \
        scripts/235_p65_lift_selftest.py scripts/240_p73_tilt_selftest.py \
        scripts/selfcheck.sh
    echo "# arms: {$ARMS} seeds: {$SEEDS}; C=0.08 T1=0.14 T2=0.20 (place z 1.530/1.590/1.650)"
    echo "# scenario (P66 phase-3 / P71 phase-2 verbatim): $SCEN_ENV"
    echo "# harness: $HARNESS_ENV"
} > logs/p73/header.txt
cat logs/p73/header.txt

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [p73] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

fail=0
for seed in $SEEDS; do
    for arm in $ARMS; do
        log="logs/p73/direct/${arm}_${seed}.log"
        extra=$(arm_env "$arm")
        wait_for_sim
        echo "  [p73] $arm (transfer $(transfer_of "$arm")) seed $seed start $(date +%H:%M:%S)"
        RUN_LIMIT=3600 scripts/154_claim_run.sh "$log" \
            $HARNESS_ENV $SCEN_ENV $extra \
            scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
            --presentation direct --episodes 15 --seeds "$seed" \
            --out "logs/p73/rollouts/${arm}_${seed}"
        rc=$?
        echo "  [p73] $arm seed $seed exit=$rc $(date +%H:%M:%S)"
        tail -3 "$log"
        [ "$rc" -eq 0 ] || fail=1
    done
done

echo "[p73] end $(date '+%F %T') fail=$fail"
exit "$fail"
