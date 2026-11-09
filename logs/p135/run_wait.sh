#!/usr/bin/env bash
# P135 phase 1d: the handover gate. The belt wave's damage is a 300-400 mm miss
# created *before* the descent - the gate is `fruit - grip <= speed*(t_desc+margin)`,
# a speed formula. `FRUIT_TRACK_WAIT=1` replaces it with "start when the estimate
# says the fruit will be at the catch point when the leg ends".
set -u
cd "$(dirname "$0")/../.." || exit 1
SEED=${SEED:-5}; ATTEMPTS=${ATTEMPTS:-3}; OUT=logs/p135/wait; mkdir -p "$OUT"
run() { local name=$1; shift; echo "== $name"
  env ATTEMPTS="$ATTEMPTS" SEED="$SEED" FRUIT_BIARM=0 SKIP_SELFCHECK=1 \
      FRUIT_MOTION_REPORT=1 FRUIT_TRACK_DIAG=1 "$@" \
      scripts/run.sh scripts/20_pick_place.py > "$OUT/$name.log" 2>&1
  grep -E '\[catch\]|\[run\] summary' "$OUT/$name.log" | sed 's/^/  /'
  grep -E '\[run\]   ' "$OUT/$name.log" | sed 's/^/  /'; }
W="FRUIT_BELT_WAVE_AMP=0.04 FRUIT_BELT_WAVE_HZ=0.5"
run c $W
run t $W FRUIT_TRACK=est FRUIT_DESCENT_TRACK=1
run w $W FRUIT_TRACK=est FRUIT_DESCENT_TRACK=1 FRUIT_TRACK_WAIT=1
echo "== done"
