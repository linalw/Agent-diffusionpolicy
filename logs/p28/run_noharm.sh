#!/bin/bash
# P28-D's blocking no-harm: the standing acceptance + the policy canary on the P28-B tree.
cd "$(dirname "$0")/../.." || exit 1
echo "[p28n] ACCEPT START $(date +%H:%M:%S)"
RUN_LIMIT=3600 scripts/154_claim_run.sh logs/p28/noharm_accept.log HEADLESS=1 ATTEMPTS=10 \
    FRUIT_MOTION_REPORT=1 scripts/run.sh scripts/20_pick_place.py > logs/p28/noharm_accept_driver.log 2>&1
echo "[p28n] ACCEPT exit=$? $(date +%H:%M:%S)"
echo "[p28n] POLICY START $(date +%H:%M:%S)"
RUN_LIMIT=5400 scripts/154_claim_run.sh logs/p28/noharm_policy.log EPISODES=10 HEADLESS=1 \
    scripts/accept_policy.sh > logs/p28/noharm_policy_driver.log 2>&1
echo "[p28n] POLICY exit=$? $(date +%H:%M:%S)"
echo "[p28n] DONE $(date +%H:%M:%S)"
