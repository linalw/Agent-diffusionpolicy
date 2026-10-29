#!/usr/bin/env bash
# P62 phase 2, gate P0b: does the T0 knob reach the attitude the catch runs?
#
#   bash logs/p62/p2/run_p0b.sh
#
# Two 2-episode arms, seed 101 (an independent draw on the FINAL tree), the cell's scenario, the control arm and the
# armed arm, both with FRUIT_CARRY_ATTITUDE=1 (reporting only: one TCP-pose read
# per carry leg). The endpoint is the left's achieved `grasp_lift` tool-axis belt
# projection per arm (logs/p62/PREREG_P2.md section 3): a move of < 0.05 means the
# override cannot reach the mechanism and the registered falsifier F3 fires.
#
# Nothing here edits src/ or configs/; the only difference between the arms is
# FRUIT_GRASP_LEFT_TOPDOWN.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
mkdir -p logs/p62/p2

CKPT=checkpoints/moe_v13s/policy_best.pt
SCEN_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_ACQ_DIAG=1"
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
ATTITUDE_ENV="FRUIT_CARRY_ATTITUDE=1"

{
    echo "# P62 phase 2 gate P0b header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD) + the uncommitted P62 grasp_quat_override kwarg"
    md5sum "$CKPT" \
        src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
        src/fruit_sorting/fruits.py src/fruit_sorting/scene.py \
        src/fruit_sorting/control.py src/fruit_sorting/motion.py \
        configs/waypoints.json configs/waypoints_oriented.json \
        configs/arm_parks.json configs/motion_reference.json \
        scripts/110_rl_rollout.py scripts/232_p62_grasp_selftest.py \
        logs/p62/PREREG_P2.md logs/p62/p2/run_p0b.sh
    echo "# scenario: $SCEN_ENV"
    echo "# harness : $HARNESS_ENV"
    echo "# instrument: $ATTITUDE_ENV (reporting only, P39)"
    echo "# arms   : A = control (knob unset), B = FRUIT_GRASP_LEFT_TOPDOWN=1"
    echo "# --episodes 2 --seeds 101 ; one claim per run"
} > logs/p62/p2/p0b_header.txt
cat logs/p62/p2/p0b_header.txt

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [p0b] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

run_one() {
    local arm=$1 extra=$2 log="logs/p62/p2/P0b_$1.log"
    wait_for_sim
    echo "  [p0b] $arm start $(date +%H:%M:%S)"
    RUN_LIMIT=1800 scripts/154_claim_run.sh "$log" \
        $HARNESS_ENV $SCEN_ENV $ATTITUDE_ENV ${extra} \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
        --presentation direct --episodes 2 --seeds 101 \
        --out logs/p62/p2/rollouts_p0b
    local rc=$?
    echo "  [p0b] $arm exit=$rc $(date +%H:%M:%S)"
    return $rc
}

fail=0
run_one A ""                          || { echo "  [p0b] A failed; F1 retry"; run_one A "" || fail=1; }
run_one B "FRUIT_GRASP_LEFT_TOPDOWN=1" || { echo "  [p0b] B failed; F1 retry"; run_one B "FRUIT_GRASP_LEFT_TOPDOWN=1" || fail=1; }
echo "[p0b] end $(date '+%F %T') fail=$fail"
exit "$fail"
