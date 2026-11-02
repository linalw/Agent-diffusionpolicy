#!/usr/bin/env bash
# P92: run amendment A1 (and then the acceptance no-harm read) after the main
# battery has released the simulator. The pattern is the main battery's own
# script name; this file's name does not contain it, so pgrep cannot match the
# waiter itself.
cd "$(dirname "$0")/../.." || exit 1
while pgrep -f 'logs/p92/run_p92\.sh' > /dev/null; do
    sleep 10
done
echo "[chain] the main battery is done $(date +%H:%M:%S)"
bash logs/p92/run_p92_a1.sh
echo "[chain] A1 done $(date +%H:%M:%S) - running the acceptance no-harm read"
scripts/accept.sh > logs/p92/accept_noharm.log 2>&1
echo "[chain] acceptance rc=$? $(date +%H:%M:%S)"
