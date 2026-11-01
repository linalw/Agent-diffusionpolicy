#!/usr/bin/env bash
# P82 stage 2: the one optimization (the arbiter's wake-on-request), A/B'd on the
# same session, plus the two no-harm gates for the code it touches.
#
#   bash logs/p82/run_p82_stage2.sh
#
# W0  two-line, knob OFF (same-session control: must replay logs/p80/T20.log)
# W1  two-line, knob ON  (bit-identity vs T20 + the wall delta)
# W2  two-line, knob ON, repeat (determinism + wall stability -> the A arm's spread)
# W3  two-line, knob ON + I2 timers (where the wall went)
# A1  scripts/accept.sh with the knob SET, 10 attempts (single-arm no-harm: the
#     knob is read by CoopSession only, and the single-arm line never builds one)
# F0/F1 the F2 shared-station scheduler (the same code's other consumer), 10
#     attempts each, OFF then ON
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
export HEADLESS=1 SEED=5
MINE="FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1"
ON="FRUIT_BIARM_WAKE_ON_REQUEST=1"

cell() {  # name, then env assignments; P82_ENTRY=<script> picks the profile build
    name=$1; shift
    echo "[p82] === $name $(date +%H:%M:%S) ==="
    scripts/154_claim_run.sh "logs/p82/$name.driver" "$@" \
        bash logs/p82/one_run.sh "logs/p82/$name.log" "logs/p82/$name.stamps" \
        "${P82_ENTRY:-scripts/20_pick_place.py}"
    echo "[p82] $name exit=$? $(date +%H:%M:%S)"
}

export ATTEMPTS=20 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
cell W0 $MINE
cell W1 $MINE $ON
cell W2 $MINE $ON
P82_ENTRY=logs/p82/profile_20.py cell W3 $MINE $ON P82_TIMERS=logs/p82/W3.timers.json
SEED=6 cell W4 $MINE $ON   # seed 6: the pair whose control is P80's T6

echo "[p82] === A1 accept, single arm, knob set $(date +%H:%M:%S) ==="
ATTEMPTS=10 SKIP_SELFCHECK=1 \
  scripts/154_claim_run.sh logs/p82/A1.driver $ON ACCEPT_LOG=logs/p82/A1.log \
    bash scripts/accept.sh > logs/p82/A1.claim 2>&1
echo "[p82] A1 exit=$? $(date +%H:%M:%S)"

export ATTEMPTS=10
cell F0 FRUIT_BIARM=1
cell F1 FRUIT_BIARM=1 $ON

echo "[p82] stage 2 done $(date +%H:%M:%S)"
