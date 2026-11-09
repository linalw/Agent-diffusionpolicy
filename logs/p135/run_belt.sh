#!/usr/bin/env bash
# P135 phase 1c: the non-uniform conveyor.
#
# A velocity impulse is damped by the belt's friction in ~30 ms (the fruit slides
# a few millimetres and re-settles), so it perturbs the *grasp quality*, not the
# transport.  A belt whose speed varies is the transport itself being
# non-uniform, which is the assumption the shipped formula makes.  The fruit
# ride the belt (no slip), so their velocity is exactly the belt's - and it is
# not constant.
set -u
cd "$(dirname "$0")/../.." || exit 1
SEED=${SEED:-5}
ATTEMPTS=${ATTEMPTS:-3}
OUT=logs/p135/belt
mkdir -p "$OUT"

run() {  # name, extra env...
    local name=$1; shift
    echo "== $name"
    env ATTEMPTS="$ATTEMPTS" SEED="$SEED" FRUIT_BIARM=0 SKIP_SELFCHECK=1 \
        FRUIT_MOTION_REPORT=1 FRUIT_TRACK_DIAG=1 "$@" \
        scripts/run.sh scripts/20_pick_place.py > "$OUT/$name.log" 2>&1
    grep -E '\[task\] dynamic descent' "$OUT/$name.log" | sed 's/^/  /' | cut -c1-130
    grep -E '\[catch\]' "$OUT/$name.log" | sed 's/^/  /'
    grep -E '\[run\] summary' "$OUT/$name.log" | sed 's/^/  /'
    grep -E '\[run\]   ' "$OUT/$name.log" | sed 's/^/  /'
}

for spec in "0.04:0.5" "0.08:0.3"; do
    amp=${spec%%:*}; hz=${spec##*:}
    run "c_w${amp}_${hz}" FRUIT_BELT_WAVE_AMP=$amp FRUIT_BELT_WAVE_HZ=$hz
    run "t_w${amp}_${hz}" FRUIT_BELT_WAVE_AMP=$amp FRUIT_BELT_WAVE_HZ=$hz \
        FRUIT_TRACK=est FRUIT_DESCENT_TRACK=1
    run "a_w${amp}_${hz}" FRUIT_BELT_WAVE_AMP=$amp FRUIT_BELT_WAVE_HZ=$hz \
        FRUIT_TRACK=est FRUIT_TRACK_ACCEL=1 FRUIT_DESCENT_TRACK=1
done
echo "== done"
