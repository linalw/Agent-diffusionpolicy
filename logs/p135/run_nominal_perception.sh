#!/usr/bin/env bash
# P135 phase 2: the nominal pair (H3) and the perception bench (H5).
#
# * nominal: no impulse, C vs T - the tracked descent must not change the cell.
# * perception: `FRUIT_TRACK_APPLY=0 FRUIT_TRACK_SOURCE=depth` runs the estimator
#   and the model-based measurement on every frame while every control input
#   stays the shipped one, so `[track] err=` / `[perceive] err=` score the
#   measurement against the simulator's centre without the cell moving.
set -u
cd "$(dirname "$0")/../.." || exit 1
SEED=${SEED:-5}
ATTEMPTS=${ATTEMPTS:-3}
HEAVY=${HEAVY:-1}
mkdir -p logs/p135/nominal logs/p135/perception

run() {  # dir, name, extra env...
    local dir=$1 name=$2; shift 2
    echo "== $name"
    env ATTEMPTS="$ATTEMPTS" SEED="$SEED" FRUIT_BIARM=0 SKIP_SELFCHECK=1 \
        FRUIT_MOTION_REPORT=1 "$@" scripts/run.sh scripts/20_pick_place.py \
        > "$dir/$name.log" 2>&1
    grep -E '\[task\] dynamic catch-up|\[run\] summary' "$dir/$name.log" \
        | sed 's/^/  /'
    grep -E '\[track\]|\[perceive\]' "$dir/$name.log" | tail -4 | sed 's/^/  /'
}

run logs/p135/nominal nom_c
run logs/p135/nominal nom_t FRUIT_TRACK=est FRUIT_DESCENT_TRACK=1

if [ "$HEAVY" = "1" ]; then
    # The camera path renders every 1/30 s; 2 attempts is the bench, not a rate.
    ATTEMPTS=2 run logs/p135/perception perc_c \
        FRUIT_TRACK=est FRUIT_TRACK_APPLY=0 FRUIT_TRACK_SOURCE=depth \
        FRUIT_TRACK_DIAG=1
fi
echo "== done"
