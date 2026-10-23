#!/usr/bin/env bash
# P34-B: the reset first-call pose + rendered-mask probe, the settle sweep and
# the 0.441 treatment check. One episode per run (seed 77), one simulator.
#   bash logs/p34/run_p34b_probe.sh
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

PATCH_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25"
SCENARIO="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 $PATCH_ENV FRUIT_ACQ_DIAG=1 FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_RESET_ALIGN_DIAG=1"
COMMON="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_POLICY_SEED=11 FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1 PROBE_CALLS=3 PROBE_EPISODES=2"

run() {  # run <log> <env...>
    local log="$1"; shift
    echo "[p34b-probe] $log $(date +%H:%M:%S)"
    RUN_LIMIT=1800 scripts/154_claim_run.sh "$log" \
        env $COMMON $SCENARIO "$@" scripts/run.sh logs/p34/B_mask_probe.py
    echo "[p34b-probe] $log exit=$? $(date +%H:%M:%S)"
}

# 0) the control (knob off, shipped settle) - the reference first call.
run logs/p34/B_probe_control.log FRUIT_RESET_SETTLE=20
# 1) the settle sweep at the phase-2 aim (0.399).
run logs/p34/B_probe_a399_s20.log   FRUIT_RESET_SETTLE=20  FRUIT_RESET_ALIGN=1 FRUIT_RESET_ALIGN_ALONG=0.399
run logs/p34/B_probe_a399_s60.log   FRUIT_RESET_SETTLE=60  FRUIT_RESET_ALIGN=1 FRUIT_RESET_ALIGN_ALONG=0.399
run logs/p34/B_probe_a399_s120.log  FRUIT_RESET_SETTLE=120 FRUIT_RESET_ALIGN=1 FRUIT_RESET_ALIGN_ALONG=0.399
# 2) the treatment check: the store's own first view (0.441).
run logs/p34/B_probe_a441_s20.log   FRUIT_RESET_SETTLE=20  FRUIT_RESET_ALIGN=1 FRUIT_RESET_ALIGN_ALONG=0.441
run logs/p34/B_probe_a441_s60.log   FRUIT_RESET_SETTLE=60  FRUIT_RESET_ALIGN=1 FRUIT_RESET_ALIGN_ALONG=0.441
run logs/p34/B_probe_a441_s120.log  FRUIT_RESET_SETTLE=120 FRUIT_RESET_ALIGN=1 FRUIT_RESET_ALIGN_ALONG=0.441
echo "[p34b-probe] done $(date +%H:%M:%S)"
