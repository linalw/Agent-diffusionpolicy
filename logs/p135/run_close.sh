#!/usr/bin/env bash
# P135 phase 1e: the confirmation cells and the perception re-bench.
#   nom_w  - the prediction-gated handover on the *nominal* cell (must not move it)
#   w2     - the second wave rung with the prediction-gated handover
#   perc   - the model-based measurement bench, control path untouched
set -u
cd "$(dirname "$0")/../.." || exit 1
SEED=${SEED:-5}; OUT=logs/p135/close; mkdir -p "$OUT"
run() { local name=$1 n=$2; shift 2; echo "== $name"
  env ATTEMPTS="$n" SEED="$SEED" FRUIT_BIARM=0 SKIP_SELFCHECK=1 \
      FRUIT_MOTION_REPORT=1 FRUIT_TRACK_DIAG=1 "$@" \
      scripts/run.sh scripts/20_pick_place.py > "$OUT/$name.log" 2>&1
  grep -E '\[catch\]|\[run\] summary' "$OUT/$name.log" | sed 's/^/  /'
  grep -E '\[run\]   ' "$OUT/$name.log" | sed 's/^/  /'; }
run nom_w 3 FRUIT_TRACK=est FRUIT_DESCENT_TRACK=1 FRUIT_TRACK_WAIT=1
run w2 3 FRUIT_BELT_WAVE_AMP=0.08 FRUIT_BELT_WAVE_HZ=0.3 \
    FRUIT_TRACK=est FRUIT_DESCENT_TRACK=1 FRUIT_TRACK_WAIT=1
run perc 2 FRUIT_TRACK=est FRUIT_TRACK_APPLY=0 FRUIT_TRACK_SOURCE=depth
echo "== done"
