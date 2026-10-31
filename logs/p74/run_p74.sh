#!/usr/bin/env bash
# P74: the place-profile SPEED vs the left arm's place-leg loaded slide
# (logs/p74/PREREG.md, md5 1c3546de8e3b9f0f58cadc983f87e875).
#
#   SEEDS="77" bash logs/p74/run_p74.sh        # the registered first read
#   SEEDS="101 202" bash logs/p74/run_p74.sh   # the registered EXPANSION only
#
# The one variable is `FRUIT_SPEED_PLACE` (the P44 S1 cell):
#   C = unset (shipped place profile, v_max 0.35, a_max 1.089)
#   S = 0.52    (v_max 0.52, a_max still 1.089 - the registered cell)
# It reaches the DIRECT place leg through `_speed["place_vmax"]`, the fallback
# default of `FRUIT_DYNAMIC_PLACE_VMAX` at tasks.py:3853 inside
# `elif self._dynamic_capture_active:`, which the direct presentation arms
# (PREREG section 1.1; the P73 SLOW arm is the measured control for it).
#
# Every arm is one claim. The cell is the P66-phase-3 / P71-phase-2 / P73
# scenario verbatim, so C is comparable to the shipped corpus and to P73's C.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p74/direct logs/p74/rollouts

SEEDS=${SEEDS:-"77"}
ARMS=${ARMS:-"C S"}
CKPT=checkpoints/moe_v13s/policy_best.pt
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
SCEN_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1 FRUIT_MOTION_REPORT=1"

arm_env() {
    case "$1" in
        # an explicit empty value = the shipped profile (the control arm)
        C) echo "FRUIT_SPEED_PLACE=" ;;
        S) echo "FRUIT_SPEED_PLACE=0.52" ;;
        *) echo "?"; return 1 ;;
    esac
}

{
    echo "# P74 header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)"
    echo "# prereg: $(cat logs/p74/PREREG.md5 2>/dev/null | tr '\n' ' ')"
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
        scripts/235_p65_lift_selftest.py scripts/239_p72_clr_edge_selftest.py \
        scripts/240_p73_tilt_selftest.py scripts/selfcheck.sh
    echo "# arms: {$ARMS} seeds: {$SEEDS}; C=shipped place profile (0.35/1.089) S=FRUIT_SPEED_PLACE=0.52"
    echo "# scenario (P66 phase-3 / P71 phase-2 / P73 verbatim): $SCEN_ENV"
    echo "# harness: $HARNESS_ENV"
} > logs/p74/header.txt
cat logs/p74/header.txt

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [p74] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

fail=0
for seed in $SEEDS; do
    for arm in $ARMS; do
        log="logs/p74/direct/${arm}_${seed}.log"
        extra=$(arm_env "$arm") || exit 1
        wait_for_sim
        echo "  [p74] $arm ($(arm_env "$arm")) seed $seed start $(date +%H:%M:%S)"
        RUN_LIMIT=3600 scripts/154_claim_run.sh "$log" \
            $HARNESS_ENV $SCEN_ENV $extra \
            scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
            --presentation direct --episodes 15 --seeds "$seed" \
            --out "logs/p74/rollouts/${arm}_${seed}"
        rc=$?
        echo "  [p74] $arm seed $seed exit=$rc $(date +%H:%M:%S)"
        tail -3 "$log"
        [ "$rc" -eq 0 ] || fail=1
    done
done

echo "[p74] end $(date '+%F %T') fail=$fail"
exit "$fail"
