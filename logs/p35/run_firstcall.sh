#!/usr/bin/env bash
# P35 phase 1: the rendered first call with the inactive arm parked (`back`) vs
# the shipped `ready`, one episode per process (the only valid first-call frame,
# logs/p34/B_READ.md section 3). Seed 77 = the outer-band pear (x 0.219, 68 mm).
#   bash logs/p35/run_firstcall.sh
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

SCENARIO="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 \
FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 \
FRUIT_ACQ_DIAG=1 FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_RESET_ALIGN_DIAG=1"
COMMON="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_POLICY_SEED=11 FRUIT_NO_ATTACH=1 \
FRUIT_NO_SLEEP=1 PROBE_EPISODES=1 PROBE_CALLS=12 PROBE_SEED=77"

run() {  # run <log> <env...>
    local log="$1"; shift
    echo "[p35-firstcall] $log $(date +%H:%M:%S)"
    RUN_LIMIT=1500 scripts/154_claim_run.sh "$log" \
        env $COMMON $SCENARIO "$@" scripts/run.sh logs/p34/B_mask_probe.py
    echo "[p35-firstcall] $log exit=$? $(date +%H:%M:%S)"
}

run logs/p35/40_firstcall_ready.log PROBE_LABELS=1
run logs/p35/41_firstcall_back.log  PROBE_LABELS=1 FRUIT_ARM_PARK=back
echo "[p35-firstcall] done $(date +%H:%M:%S)"
# A left-active episode (seed 101 = the A-grade apple): the park must NOT touch
# the active arm, so its reset must match the P34-B left control's along_reset.
echo "[p35-firstcall] seed 101 left-active park-on"
RUN_LIMIT=1500 scripts/154_claim_run.sh logs/p35/42_firstcall_left_active.log \
    env HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_POLICY_SEED=11 FRUIT_NO_ATTACH=1 \
    FRUIT_NO_SLEEP=1 PROBE_EPISODES=1 PROBE_CALLS=6 PROBE_SEED=101 PROBE_LABELS=1 \
    FRUIT_ARM_PARK=back FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 \
    FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival \
    FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_ACQ_DIAG=1 \
    FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_RESET_ALIGN_DIAG=1 \
    scripts/run.sh logs/p34/B_mask_probe.py
echo "[p35-firstcall] exit=$? $(date +%H:%M:%S)"
