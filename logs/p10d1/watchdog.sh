#!/bin/bash
# Side watchdog: kill a wedged stage-1 sim (stale log >8 min) so the 112 chain proceeds.
cd "$(dirname "$0")/../.." || exit 1
OUT=logs/p10d1/stage1
while pgrep -f "[1]12_rl_ab.sh" >/dev/null 2>&1; do
    log=$(ls -t "$OUT"/A_*.log "$OUT"/B_*.log 2>/dev/null | head -1)
    if [ -n "$log" ] && [ -n "$(find "$log" -mmin +8 2>/dev/null)" ]; then
        echo "[watchdog] WEDGE $log - killing the sim $(date +%H:%M:%S)"
        pkill -f "[1]10_rl_rollout" 2>/dev/null
        sleep 30
    fi
    sleep 60
done
echo "[watchdog] the chain is gone; exiting $(date +%H:%M:%S)"
