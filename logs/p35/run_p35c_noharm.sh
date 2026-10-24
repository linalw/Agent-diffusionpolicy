#!/usr/bin/env bash
# P35 phase 2 no-harm (after the A/B releases the simulator):
#   1. the selfcheck (offline) - the tree after the diag addition;
#   2. the scripted acceptance with `FRUIT_ARM_PARK` **unset** (the shipped
#      path), compared `[fruit]`-stream-identical to the current record
#      (`logs/p34/73_accept_no_harm.log`, 376 lines, the P33/P34 record).
#
#   bash logs/p35/run_p35b_noharm.sh
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p35/B_ab

echo "[p35c-noharm] selfcheck $(date +%H:%M:%S)"
bash scripts/selfcheck.sh > logs/p35/C_selfcheck.log 2>&1
echo "[p35c-noharm] selfcheck exit=$?"
tail -3 logs/p35/C_selfcheck.log

echo "[p35c-noharm] acceptance (knob unset) $(date +%H:%M:%S)"
RUN_LIMIT=3600 scripts/154_claim_run.sh logs/p35/C_accept_driver.log \
    ACCEPT_LOG=logs/p35/C_accept_no_harm.log scripts/accept.sh
echo "[p35c-noharm] acceptance exit=$? $(date +%H:%M:%S)"

python3 logs/p33/stream_identity.py logs/p34/73_accept_no_harm.log \
    logs/p35/C_accept_no_harm.log > logs/p35/B_accept_identity.txt 2>&1
echo "[p35c-noharm] identity exit=$?"
cat logs/p35/C_accept_identity.txt
grep -E 'success:|fingerprint:' logs/p35/C_accept_no_harm.log | tail -4
echo "[p35c-noharm] done $(date +%H:%M:%S)"
