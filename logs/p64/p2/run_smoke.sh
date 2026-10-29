#!/usr/bin/env bash
# P64 phase 1 -> 2 GATE: does the pre-compensated hold actually move the left's
# achieved attitude? One short run (4 episodes, seed 77), knob ON, with the two
# reporting-only reads that say so (`[attitude] tool_axis` per carry leg).
#
#   bash logs/p64/p2/run_smoke.sh
#
# This is NOT the cell: 4 episodes is a gate on the *channel* (P62's lesson: the
# attitude channel can be inert), not an endpoint. It is spent before the 3 x 15
# cell so that the cell is not a 40-minute measurement of nothing.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
mkdir -p logs/p64/p2

CKPT=checkpoints/moe_v13s/policy_best.pt
SCEN_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_ACQ_DIAG=1"
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"

{
    echo "# P64 smoke header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD) + the uncommitted P64 knob (default off)"
    md5sum "$CKPT" \
        src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
        configs/waypoints.json configs/motion_reference.json \
        scripts/234_p64_precomp_selftest.py scripts/selfcheck.sh
    echo "# scenario: $SCEN_ENV"
    echo "# armed   : FRUIT_GRASP_LEFT_PRECOMP=1 FRUIT_CARRY_ATTITUDE=1"
    echo "# harness : $HARNESS_ENV ; --episodes 4 --seeds 77"
} > logs/p64/p2/smoke_header.txt
cat logs/p64/p2/smoke_header.txt

n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
if [ "${n:-0}" -gt 0 ]; then
    echo "[smoke] simulator busy (${n} python.sh); refusing to start" >&2
    exit 1
fi
t0=$(date +%s)
RUN_LIMIT=1800 scripts/154_claim_run.sh logs/p64/p2/S_77.log \
    $HARNESS_ENV $SCEN_ENV FRUIT_GRASP_LEFT_PRECOMP=1 FRUIT_CARRY_ATTITUDE=1 \
    scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
    --presentation direct --episodes 4 --seeds 77 \
    --out logs/p64/p2/rollouts_smoke
rc=$?
echo "[smoke] exit=$rc in $(( $(date +%s) - t0 )) s"
exit $rc
