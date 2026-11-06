#!/usr/bin/env bash
# P121: one direct cell.  $1=log  $2=episodes  $3=seed  $4..=extra env assignments
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
log=$1; episodes=$2; seed=$3; shift 3
CKPT=checkpoints/moe_v13s/policy_best.pt
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
SCEN_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1 FRUIT_MOTION_REPORT=1"
RUN_LIMIT=${RUN_LIMIT:-3600} scripts/154_claim_run.sh "$log" \
    $HARNESS_ENV $SCEN_ENV "$@" \
    scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
    --presentation direct --episodes "$episodes" --seeds "$seed" \
    --out "logs/p121/rollouts/$(basename "$log" .log)"
