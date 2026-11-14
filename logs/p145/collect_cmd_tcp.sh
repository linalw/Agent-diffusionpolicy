#!/usr/bin/env bash
# P145d.1: recollect the demonstrations with the **commanded** IK target per
# frame (`cmd_tcp` + `cmd_fresh`), so the cartesian action is the setpoint the
# scripted close asked for, not the servo's lagging response.
set -u
cd "$(dirname "$0")/../.." || exit 1
OUT=${OUT:-datasets/p145_tcp2}
N=${N:-50}
if [ ! -d "$OUT" ] || [ "$(ls "$OUT"/*.npz 2>/dev/null | wc -l)" -lt "$N" ]; then
    timeout 4200 env FRUIT_BIARM=0 FRUIT_CAMERA_RES=240,424 FRUIT_EPISODES="$N" \
        FRUIT_DEMO_DIR="$OUT" SKIP_SELFCHECK=1 \
        scripts/run.sh scripts/40_collect_demos.py
fi
echo "[p145] $(ls "$OUT"/*.npz 2>/dev/null | wc -l) episodes in $OUT $(date +%H:%M)"
