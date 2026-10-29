#!/usr/bin/env bash
# P63 phase 2, ADDENDUM A1 (reporting only, NOT an arm of the registered cell):
# one 10-episode run, seed 77, with FRUIT_CARRY_ATTITUDE=1 added.
#
#   bash logs/p63/p2/run_a1.sh
#
# Why: `hold_drift` is the *total* commanded-vs-achieved angle. P62 measured the
# achieved belt projection (+0.32..+0.36 left) on two seeds x two episodes only;
# this run reads `[attitude] ... tilt= ... tool_axis=(x,y,z)` on every carry leg
# of a longer draw, so the drift can be *decomposed* into its belt component and
# the rest. `_carry_attitude` is one TCP-pose read per leg at the leg's end, no
# per-tick work, no control input (tasks.py:3162-3225); it is NOT read as a rate
# and no count from this run is quoted against the cell.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
mkdir -p logs/p63/p2

CKPT=checkpoints/moe_v13s/policy_best.pt
SCEN_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_ACQ_DIAG=1"
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [a1] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

run_one() {
    wait_for_sim
    echo "  [a1] attitude seed 77 start $(date +%H:%M:%S)"
    RUN_LIMIT=2700 scripts/154_claim_run.sh logs/p63/p2/A1_77.log \
        $HARNESS_ENV $SCEN_ENV FRUIT_CARRY_ATTITUDE=1 \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
        --presentation direct --episodes 10 --seeds 77 \
        --out logs/p63/p2/rollouts_a1
    local rc=$?
    echo "  [a1] attitude seed 77 exit=$rc $(date +%H:%M:%S)"
    return $rc
}

if ! run_one; then
    echo "  [a1] failed; one retry (F1) $(date +%H:%M:%S)"
    run_one || { echo "  [a1] failed twice"; exit 1; }
fi
echo "[a1] end $(date '+%F %T')"
