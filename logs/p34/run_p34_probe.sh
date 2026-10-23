#!/usr/bin/env bash
# P34 phase 2: the mask/occluder attribution probe, both arms (one episode each).
#   bash logs/p34/run_p34_probe.sh
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

PATCH_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25"
SCENARIO="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 $PATCH_ENV FRUIT_ACQ_DIAG=1 FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_RESET_ALIGN_DIAG=1"
COMMON="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_POLICY_SEED=11 FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"

echo "[p34-probe] control $(date +%H:%M:%S)"
RUN_LIMIT=2400 scripts/154_claim_run.sh logs/p34/260_probe_control.log \
    env $COMMON $SCENARIO scripts/run.sh logs/p34/260_mask_probe.py
echo "[p34-probe] control exit=$? $(date +%H:%M:%S)"

echo "[p34-probe] aligned $(date +%H:%M:%S)"
RUN_LIMIT=2400 scripts/154_claim_run.sh logs/p34/261_probe_align.log \
    env $COMMON $SCENARIO FRUIT_RESET_ALIGN=1 scripts/run.sh logs/p34/260_mask_probe.py
echo "[p34-probe] aligned exit=$? $(date +%H:%M:%S)"
echo "[p34-probe] done $(date +%H:%M:%S)"
