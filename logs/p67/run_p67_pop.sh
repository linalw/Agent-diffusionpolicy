#!/usr/bin/env bash
# P67 **population cell**: the same re-shape on an all-grade-A supply, so every
# attempt is the **left** arm's place leg (the arm P66 phase 4's gate exists for).
#
#   bash logs/p67/run_p67_pop.sh
#
# Why this cell exists (recorded as a deviation from the registered A/B, which is
# `logs/p67/run_p67.sh`): in the registered cell the climb arm drew only **two**
# left attempts and both payloads were lost inside the climb, so gate (a) had no
# left read at all. The crossing is a **geometric** quantity of the left's place
# leg (bin 0, drop point y = +0.50, rail centreline |y| = 0.4125), and the direct
# env picks the arm from the fruit's grade (`rl_env`: grade A -> bin 0 -> left), so
# a grade-A supply populates that leg directly without touching the path under
# test. `FRUIT_SUPPLY_GRADES` needs all three keys (`_mix_env`), and
# `A:0.96,B:0.02,C:0.02` allocates 16/0/0 by largest remainder, i.e. a pure-A pool.
#
# Everything else is the registered cell verbatim: seed 77, 15 picks, the same
# checkpoint, the same instruments, `FRUIT_LIFT_DZ=-0.08`, `FRUIT_LIFT_CLIMB=0.18`.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p67/rollouts_pop

CKPT=checkpoints/moe_v13s/policy_best.pt
SCEN_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.96,B:0.02,C:0.02 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1"
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
SEEDS=(${SEEDS:-77})
EPISODES=${EPISODES:-15}
CLIMB=${CLIMB:-0.18}

{
    echo "# P67 population-cell header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD) + the uncommitted P67 lift_climb knob"
    md5sum "$CKPT" src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
        configs/motion_reference.json configs/motion_reference_twoline.json
    echo "# scenario (all-A supply, so every attempt is the left's place leg): $SCEN_ENV"
    echo "# arms: A2 control FRUIT_LIFT_DZ=-0.08 ; B2 = A2 + FRUIT_LIFT_CLIMB=$CLIMB"
} > logs/p67/pop_header.txt
cat logs/p67/pop_header.txt

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [p67-pop] simulator busy (${n}); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

run_one() {
    local arm=$1 seed=$2
    local log="logs/p67/${arm}_${seed}.log"
    local extra=""
    if [ "$arm" = "B2" ]; then extra="FRUIT_LIFT_CLIMB=$CLIMB"; fi
    wait_for_sim
    echo "  [p67-pop] $arm seed $seed start $(date +%H:%M:%S)"
    RUN_LIMIT=3600 scripts/154_claim_run.sh "$log" \
        $HARNESS_ENV $SCEN_ENV FRUIT_LIFT_DZ=-0.08 $extra \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
        --presentation direct --episodes "$EPISODES" --seeds "$seed" \
        --out logs/p67/rollouts_pop
    local rc=$?
    echo "  [p67-pop] $arm seed $seed exit=$rc $(date +%H:%M:%S)"
    return $rc
}

fail=0
for seed in "${SEEDS[@]}"; do
    for arm in A2 B2; do
        if ! run_one "$arm" "$seed"; then
            echo "  [p67-pop] $arm seed $seed failed; one retry $(date +%H:%M:%S)"
            if ! run_one "$arm" "$seed"; then
                echo "  [p67-pop] $arm seed $seed failed twice"
                fail=1
            fi
        fi
    done
done

echo "[p67-pop] batch end $(date '+%F %T') fail=$fail"
exit "$fail"
