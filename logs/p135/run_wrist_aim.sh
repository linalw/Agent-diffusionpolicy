#!/usr/bin/env bash
# P135: where should the eye-in-hand camera look?
# The first mount aimed 3 cm past the jaw, i.e. at the grasp point itself; during
# the descent the fruit is 10 cm upstream, so it left the frame and the filter ran
# on refusals. Aim further ahead along the approach axis and the approach corridor
# stays in view.
set -u
cd "$(dirname "$0")/../.." || exit 1
OUT=logs/p135/perception
for look in 0.10 0.16; do
  for back in 0.03; do
    name="waim_${look}_${back}"
    echo "== $name"
    env ATTEMPTS=1 SEED=5 FRUIT_BIARM=0 SKIP_SELFCHECK=1 FRUIT_TRACK=est \
        FRUIT_TRACK_APPLY=0 FRUIT_TRACK_SOURCE=depth FRUIT_TRACK_DIAG=1 \
        FRUIT_WRIST_CAMERA=1 FRUIT_WRIST_LOOK=$look FRUIT_WRIST_BACK=$back \
        scripts/run.sh scripts/20_pick_place.py > "$OUT/$name.log" 2>&1
    grep -aE 'perceive\] renders|\[run\] summary' "$OUT/$name.log" | sed 's/^/  /'
    grep -a '\[perceive\] idx' "$OUT/$name.log" | awk 'NR%6==1' | cut -c1-118 | sed 's/^/  /'
  done
done
echo "== done"
