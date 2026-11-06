#!/usr/bin/env bash
cd "$(dirname "$0")/../.." || exit 1
bash logs/p123/run_p123.sh T5
SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p123/accept_noharm.log scripts/accept.sh > logs/p123/accept_noharm.driver 2>&1
echo "[chain] accept rc=$?" >> logs/p123/chain.log
bash logs/p123/run_p123.sh C6 T6
echo "[chain] done $(date '+%F %T')" >> logs/p123/chain.log
