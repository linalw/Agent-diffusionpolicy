#!/usr/bin/env bash
# P135: re-check the phase's two working results on the current estimator.
#   wave_w - the prediction-gated handover under the belt wave (3 attempts)
#   head   - the head camera in the loop (2 attempts)
set -u
cd "$(dirname "$0")/../.." || exit 1
OUT=logs/p135/recheck; mkdir -p "$OUT"
run() { local name=$1 n=$2; shift 2; echo "== $name"
  env ATTEMPTS="$n" SEED=5 FRUIT_BIARM=0 SKIP_SELFCHECK=1 FRUIT_MOTION_REPORT=1 \
      FRUIT_TRACK_DIAG=1 "$@" scripts/run.sh scripts/20_pick_place.py > "$OUT/$name.log" 2>&1
  grep -aE '\[catch\]|\[track\]|\[run\] summary|\[run\]   |perceive\] renders' "$OUT/$name.log" | cut -c1-150 | sed 's/^/  /'
}
run wave_w 3 FRUIT_BELT_WAVE_AMP=0.04 FRUIT_BELT_WAVE_HZ=0.5 \
    FRUIT_TRACK=est FRUIT_DESCENT_TRACK=1 FRUIT_TRACK_WAIT=1
run head 2 FRUIT_TRACK=est FRUIT_DESCENT_TRACK=1 FRUIT_TRACK_WAIT=1 \
    FRUIT_TRACK_SOURCE=depth FRUIT_PERCEPTION_CLOSE=1
echo "== done"
