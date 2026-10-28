#!/usr/bin/env bash
# P56 phase 2: the pre-registered battery (logs/p56/PREREG.md section 1).
#
#   bash logs/p56/p2/run_batch.sh                 # seeds 77 101 202
#   P56_SEEDS="77" bash logs/p56/p2/run_batch.sh  # the mechanical pre-check pair
#
#   A = the shipped per-pick loop   `--episodes 15`  + FRUIT_DIRECT_FEED=1
#   B = the continuous episode      `--episodes 1`   + FRUIT_DIRECT_CONTINUOUS=15
#
# Everything else is identical in both arms (the PREREG's fixed configuration):
# `checkpoints/moe_v13s/policy_best.pt` (`61da390a`), the W6-A/W8-A patch sheet
# balanced A:B:C, `FRUIT_POLICY_TRIGGER=arrival` lead 0.9 lateral 0.16 with ACQ
# on (the P54 shipped default for `direct`), the park default (`back`, P43),
# `FRUIT_POLICY_SEED=11`, camera 240x424, `--record` in BOTH arms (P5 reads the
# recorder's index; an asymmetric instrument is not a measurement), and the two
# P56 reports on both arms (`FRUIT_BED_DIAG` = P3, `FRUIT_GRASP_DIAG` = P6/P1).
#
# The episode counts differ **on purpose**: `--episodes 15` on arm B would
# deliver 225 picks. `p2_report.py` asserts `picks_seen == 15` per run before it
# reports anything (PREREG section 1).
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
mkdir -p logs/p56/p2

CKPT=checkpoints/moe_v13s/policy_best.pt
PATCH_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25"
SCEN_ENV="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1"
P56_DIAG="FRUIT_BED_DIAG=1 FRUIT_GRASP_DIAG=1"
FIX_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_POLICY_SEED=11 FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
ARM_A="FRUIT_DIRECT_FEED=1"
ARM_B="FRUIT_DIRECT_CONTINUOUS=15"

SEEDS=(${P56_SEEDS:-77 101 202})
PICKS=15

{
    echo "# P56 phase 2 batch header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD) (+ the P56 working-tree edit)"
    md5sum "$CKPT" src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
        src/fruit_sorting/control.py src/fruit_sorting/scene.py \
        src/fruit_sorting/policy/runtime.py src/fruit_sorting/policy/trigger.py \
        src/fruit_sorting/fruits.py configs/arm_parks.json \
        configs/motion_reference.json configs/motion_reference_twoline.json \
        scripts/110_rl_rollout.py scripts/113_rl_report.py scripts/154_claim_run.sh \
        logs/p56/PREREG.md logs/p56/DESIGN.md logs/p56/p2/run_batch.sh \
        logs/p56/p2_report.py
    echo "# scenario (both arms): $PATCH_ENV $SCEN_ENV $P56_DIAG"
    echo "# A: $ARM_A --episodes $PICKS   |   B: $ARM_B --episodes 1 (=$PICKS picks)"
    echo "# ckpt=$CKPT on BOTH arms; park unset = the P43 default (back); ACQ unset = the P54 default (on)"
    echo "# SEEDS=${SEEDS[*]} policy_seed=11, interleaved A then B per seed"
} > logs/p56/p2/P2_header.txt
cat logs/p56/p2/P2_header.txt

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [p56] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

run_one() {
    local arm=$1 run=$2 seed=$3
    local log="logs/p56/p2/${arm}_${run}.log"
    local episodes=$PICKS arm_env=$ARM_A
    if [ "$arm" = "B" ]; then
        episodes=1
        arm_env="$ARM_A $ARM_B"
    fi
    wait_for_sim
    # shellcheck disable=SC2086
    RUN_LIMIT=3600 scripts/154_claim_run.sh "$log" \
        $PATCH_ENV $SCEN_ENV $P56_DIAG $arm_env $FIX_ENV \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
        --presentation direct --episodes "$episodes" --seeds "$seed" \
        --record --out "logs/p56/p2/store/${arm}"
    printf '  %s run %d (seed %s): exit=%s picks=%s %s\n' "$arm" "$run" "$seed" "$?" \
        "$(grep -cE '^\[fruit\] \[rl\] episode [0-9]+: .* success=' "$log")" \
        "$(grep -oE '\[rl\] rollout success [0-9]+/[0-9]+' "$log" | tail -1)"
}

t0=$(date +%s)
echo "[p56] batch start $(date '+%F %T')"
i=0
for seed in "${SEEDS[@]}"; do
    i=$((i + 1))
    run_one A "$i" "$seed"
    run_one B "$i" "$seed"
done
t1=$(date +%s)
echo "[p56] batch end $(date '+%F %T') wall=$((t1 - t0))s"

python3 logs/p56/p2_report.py --dir logs/p56/p2 > logs/p56/p2/P2_report.txt 2>&1
echo "[p56] p2 report exit=$?"
python3 scripts/113_rl_report.py logs/p56/p2 --a A --b B \
    > logs/p56/p2/P56_113_A_B.txt 2>&1
echo "[p56] 113 A/B exit=$?"
echo "[p56] done $(date '+%F %T')"
