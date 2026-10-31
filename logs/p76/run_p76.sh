#!/usr/bin/env bash
# P76: the clamp-force ladder on the DIRECT line - the force at which the pry
# stops, per class, and the force at which the smallest fruit is crushed
# (logs/p76/PREREG.md, md5 62567d8bfda3411fde92ff2021ecb4f2).
#
#   SEEDS="77" bash logs/p76/run_p76.sh        # the registered first read
#   SEEDS="101" bash logs/p76/run_p76.sh       # only if a rung is ambiguous (§5)
#
# The one variable is `FRUIT_FINGER_MAXFORCE` (the per-joint drive cap the build
# writes on both arms' `joint1`, scene.py resolve_finger_maxforce /
# apply_finger_maxforce):
#   F10 = unset (the shipped asset cap, 10 N)
#   F15 = 15   F20 = 20   F30 = 30
#   F45 / F60 = PREREG A2 DECLARED EXTENSIONS (the crush anchor), not rungs
# The scenario is the P66-phase-3 / P71-phase-2 / P73 / P74 / P75 cell verbatim
# and the instrument (`FRUIT_CARRY_DIAG=1`) is identical in every arm.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p76/direct logs/p76/rollouts

SEEDS=${SEEDS:-"77"}
ARMS=${ARMS:-"F10 F15 F20 F30"}
CKPT=checkpoints/moe_v13s/policy_best.pt
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
SCEN_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1 FRUIT_MOTION_REPORT=1"

arm_env() {
    case "$1" in
        # an explicit empty value = the shipped asset cap (10 N)
        F10) echo "FRUIT_FINGER_MAXFORCE=" ;;
        F15) echo "FRUIT_FINGER_MAXFORCE=15" ;;
        F20) echo "FRUIT_FINGER_MAXFORCE=20" ;;
        F30) echo "FRUIT_FINGER_MAXFORCE=30" ;;
        # PREREG amendment A2: DECLARED EXTENSION cells, not rungs (P75's A4
        # convention) - the crush's upper anchor on the direct line.
        F45) echo "FRUIT_FINGER_MAXFORCE=45" ;;
        F60) echo "FRUIT_FINGER_MAXFORCE=60" ;;
        *) echo "?"; return 1 ;;
    esac
}

{
    echo "# P76 header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)"
    echo "# prereg: $(cat logs/p76/PREREG.md5 2>/dev/null | tr '\n' ' ')"
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
        scripts/243_p76_sep_selftest.py scripts/selfcheck.sh
    echo "# arms: {$ARMS} seeds: {$SEEDS}; F10=unset(asset 10 N) F15/F20/F30=FRUIT_FINGER_MAXFORCE"
    echo "# scenario (P66 phase-3 / P71 phase-2 / P73 / P74 / P75 verbatim): $SCEN_ENV"
    echo "# harness: $HARNESS_ENV"
} > logs/p76/header.txt
cat logs/p76/header.txt

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [p76] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

fail=0
for seed in $SEEDS; do
    for arm in $ARMS; do
        log="logs/p76/direct/${arm}_${seed}.log"
        extra=$(arm_env "$arm") || exit 1
        wait_for_sim
        echo "  [p76] $arm ($(arm_env "$arm")) seed $seed start $(date +%H:%M:%S)"
        RUN_LIMIT=3600 scripts/154_claim_run.sh "$log" \
            $HARNESS_ENV $SCEN_ENV $extra \
            scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
            --presentation direct --episodes 15 --seeds "$seed" \
            --out "logs/p76/rollouts/${arm}_${seed}"
        rc=$?
        echo "  [p76] $arm seed $seed exit=$rc $(date +%H:%M:%S)"
        tail -3 "$log"
        [ "$rc" -eq 0 ] || fail=1
    done
done

echo "[p76] end $(date '+%F %T') fail=$fail"
exit "$fail"
