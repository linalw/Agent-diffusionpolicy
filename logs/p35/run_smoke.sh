#!/usr/bin/env bash
# P35 phase 2 smoke: two one-episode runs (park off / park back) that exercise
# the new `[park]` diag row before the N=5 A/B is claimed.
#
#   nohup bash logs/p35/run_smoke.sh > logs/p35/10_smoke_outer.log 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p35

SCEN="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25"
TRIG="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1"
DIAG="FRUIT_ACQ_DIAG=1 FRUIT_RESET_ALIGN_DIAG=1 FRUIT_PARK_DIAG=1 FRUIT_POLICY_TRIGGER_ACQ=1"
BASE="HEADLESS=1 FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1 FRUIT_CAMERA_RES=240,424 FRUIT_POLICY_SEED=11"

CKPT=checkpoints/moe_v13s/policy_best.pt
run() {
    local log=$1 extra=$2
    RUN_LIMIT=1800 scripts/154_claim_run.sh "$log" \
        $BASE $SCEN $TRIG $DIAG $extra \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
        --presentation direct --episodes 2 --seeds 77
    echo "[smoke] $log exit=$?"
}

run logs/p35/10_smoke_off.log "FRUIT_ARM_PARK=ready"
run logs/p35/11_smoke_back.log "FRUIT_ARM_PARK=back"
echo "[smoke] done $(date +%H:%M:%S)"
