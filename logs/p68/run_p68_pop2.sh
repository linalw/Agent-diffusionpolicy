#!/usr/bin/env bash
# P68 phase 1, THE ONE NAMED CELL: the P67 climb pair **plus** the shipped
# place-leg wrist hold.
#
#   bash logs/p68/run_p68_pop2.sh              # the batch (3 new runs)
#   SMOKE=1 bash logs/p68/run_p68_pop2.sh      # one 1-pick fixture of arm A
#
# Arm A (treatment, both seeds):
#     FRUIT_LIFT_DZ=-0.08 FRUIT_LIFT_CLIMB=0.18 FRUIT_DYNAMIC_PLACE_WRIST_HOLD_S=1.0
# Arm B (control, seed 101 only - seed 77 is P67's own B2_77.log, re-used):
#     FRUIT_LIFT_DZ=-0.08 FRUIT_LIFT_CLIMB=0.18
#
# Scenario: P67's **population cell** verbatim (`logs/p67/run_p67_pop.sh`), whose
# supply is grade-A only (`A:0.96,B:0.02,C:0.02` -> 16/0/0), so every attempt is
# the **left** arm's place leg and the arm mix is fixed by construction. 8 picks
# per run, the same count P67's population cell ran (the all-A supply makes every
# attempt the slow arm).
#
# Why the wrist hold: P67 measured the climb clearing the crossing (+33..+54 mm)
# and losing the payload on 3/8 climbed left place legs, onset at rows 113-152 =
# the climb's own exit, on a leg that runs with `hold_drift=0.0deg(no-hold)`.
# `FRUIT_DYNAMIC_PLACE_WRIST_HOLD_S` is the shipped knob that installs the
# leg-start attitude for the first N seconds of a dynamic place leg
# (`tasks.py` `_carry`: `place_hold_s / CONTROL_DT` ticks, then released), which
# is exactly the free-wrist window the losses sit in.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p68/rollouts_pop2 logs/p68/smoke_rollouts

CKPT=checkpoints/moe_v13s/policy_best.pt
SCEN_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.96,B:0.02,C:0.02 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1"
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
SEEDS=(${SEEDS:-77 101})
EPISODES=${EPISODES:-8}
CLIMB=${CLIMB:-0.18}
HOLD=${HOLD:-1.0}
PAIR="FRUIT_LIFT_DZ=-0.08 FRUIT_LIFT_CLIMB=$CLIMB"
HOLD_ENV="FRUIT_DYNAMIC_PLACE_WRIST_HOLD_S=$HOLD"

if [ "${SMOKE:-0}" = "1" ]; then
    echo "=== P68 smoke: arm A, 1 pick ($(date '+%F %T')) ==="
    RUN_LIMIT=1200 scripts/154_claim_run.sh logs/p68/smoke_A.log \
        $HARNESS_ENV $SCEN_ENV $PAIR $HOLD_ENV \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
        --presentation direct --episodes 1 --seeds 77 \
        --out logs/p68/smoke_rollouts
    echo "exit=$?"
    exit 0
fi

{
    echo "# P68 population-cell header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)"
    md5sum "$CKPT" src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
        configs/motion_reference.json configs/motion_reference_twoline.json
    echo "# scenario (all-A supply, so every attempt is the left's place leg): $SCEN_ENV"
    echo "# arm A (treatment): $PAIR $HOLD_ENV"
    echo "# arm B (control):   $PAIR   [seed 77 re-used from logs/p67/B2_77.log]"
} > logs/p68/pop2_header.txt
cat logs/p68/pop2_header.txt

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [p68] simulator busy (${n}); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

run_one() {
    local arm=$1 seed=$2
    local log="logs/p68/pop2/${arm}_${seed}.log"
    local extra="$PAIR"
    if [ "$arm" = "A" ]; then extra="$PAIR $HOLD_ENV"; fi
    mkdir -p logs/p68/pop2
    wait_for_sim
    echo "  [p68] $arm seed $seed start $(date +%H:%M:%S)"
    RUN_LIMIT=3600 scripts/154_claim_run.sh "$log" \
        $HARNESS_ENV $SCEN_ENV $extra \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
        --presentation direct --episodes "$EPISODES" --seeds "$seed" \
        --out logs/p68/rollouts_pop2
    local rc=$?
    echo "  [p68] $arm seed $seed exit=$rc $(date +%H:%M:%S)"
    return $rc
}

fail=0
for job in A:77 A:101 B:101; do
    arm=${job%%:*}; seed=${job##*:}
    if ! run_one "$arm" "$seed"; then
        echo "  [p68] $arm seed $seed failed; one retry $(date +%H:%M:%S)"
        if ! run_one "$arm" "$seed"; then
            echo "  [p68] $arm seed $seed failed twice"
            fail=1
        fi
    fi
done

echo "[p68] batch end $(date '+%F %T') fail=$fail"
exit "$fail"
