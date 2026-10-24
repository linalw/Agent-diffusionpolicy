#!/usr/bin/env bash
# P35 phase 2 smoke #2: M1 at the band call (the pose the sightline is scored at).
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
SCEN="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25"
TRIG="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1"
DIAG="FRUIT_ACQ_DIAG=1 FRUIT_RESET_ALIGN_DIAG=1 FRUIT_PARK_DIAG=1 FRUIT_POLICY_TRIGGER_ACQ=1"
BASE="HEADLESS=1 FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1 FRUIT_CAMERA_RES=240,424 FRUIT_POLICY_SEED=11"
CKPT=checkpoints/moe_v13s/policy_best.pt
run() { RUN_LIMIT=1800 scripts/154_claim_run.sh "$1" $BASE $SCEN $TRIG $DIAG $2 \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" --presentation direct \
        --episodes 2 --seeds 77; echo "[smoke2] $1 exit=$?"; }
run logs/p35/12_smoke2_ready.log "FRUIT_ARM_PARK=ready"
run logs/p35/13_smoke2_back.log "FRUIT_ARM_PARK=back"
echo "[smoke2] done $(date +%H:%M:%S)"
