#!/usr/bin/env bash
# P135: the wrist camera, in order.
#   wide  - the fixed forward aim with a 114-degree lens, so the approach
#           corridor and the grasp point are inside one frame.
#   mid   - the fixed aim at 6 cm past the jaw (the compromise between the two
#           phases the phase-1 screen separated).
set -u
cd "$(dirname "$0")/../.." || exit 1
OUT=logs/p135/perception
run() { local name=$1; shift; echo "== $name"
  env ATTEMPTS=2 SEED=5 FRUIT_BIARM=0 SKIP_SELFCHECK=1 FRUIT_MOTION_REPORT=1 \
      FRUIT_TRACK_DIAG=1 FRUIT_TRACK=est FRUIT_DESCENT_TRACK=1 FRUIT_TRACK_WAIT=1 \
      FRUIT_TRACK_SOURCE=depth FRUIT_WRIST_CAMERA=1 FRUIT_PERCEPTION_CLOSE=1 "$@" \
      scripts/run.sh scripts/20_pick_place.py > "$OUT/$name.log" 2>&1
  grep -aE '\[track\]|\[catch\]|\[run\] summary|\[run\]   |perceive\] renders' "$OUT/$name.log" | cut -c1-150 | sed 's/^/  /'
}
run wrist_wide FRUIT_WRIST_APERTURE=0.050,0.0280 FRUIT_WRIST_LOOK=0.12
run wrist_mid  FRUIT_WRIST_LOOK=0.06
echo "== done"
