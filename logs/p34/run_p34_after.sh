#!/usr/bin/env bash
# P34 phase 2 follow-ups (after the A/B has released the simulator):
#   1. the mask/occluder probe, control (knob 0) and aligned (knob 1);
#   2. the no-harm acceptance with the knob unset, compared to the current
#      `[fruit]` record (`logs/p33/40_accept_final.log`).
#
#   bash logs/p34/run_p34_after.sh
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

PATCH_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25"
SCENARIO="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 $PATCH_ENV FRUIT_ACQ_DIAG=1 FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_RESET_ALIGN_DIAG=1"
COMMON="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_POLICY_SEED=11 FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"

echo "[p34-after] probe control $(date +%H:%M:%S)"
RUN_LIMIT=2400 scripts/154_claim_run.sh logs/p34/260_probe_control.log \
    env $COMMON $SCENARIO scripts/run.sh logs/p34/260_mask_probe.py
echo "[p34-after] probe control exit=$? $(date +%H:%M:%S)"

echo "[p34-after] probe aligned $(date +%H:%M:%S)"
RUN_LIMIT=2400 scripts/154_claim_run.sh logs/p34/261_probe_align.log \
    env $COMMON $SCENARIO FRUIT_RESET_ALIGN=1 scripts/run.sh logs/p34/260_mask_probe.py
echo "[p34-after] probe aligned exit=$? $(date +%H:%M:%S)"

echo "[p34-after] acceptance (knob unset) $(date +%H:%M:%S)"
RUN_LIMIT=3600 scripts/154_claim_run.sh logs/p34/73_accept_driver.log \
    env ACCEPT_LOG=logs/p34/73_accept_no_harm.log scripts/accept.sh
echo "[p34-after] acceptance exit=$? $(date +%H:%M:%S)"

python3 logs/p33/stream_identity.py logs/p33/40_accept_final.log \
    logs/p34/73_accept_no_harm.log > logs/p34/74_accept_identity.txt 2>&1
echo "[p34-after] identity exit=$?"
cat logs/p34/74_accept_identity.txt
echo "[p34-after] done $(date +%H:%M:%S)"
