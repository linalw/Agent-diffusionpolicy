#!/usr/bin/env bash
# P135 phase 1: the non-uniform-motion envelope.
#
# One scripted single-arm cell per (arm, impulse), the shipped scenario, the
# fruit selected as usual.  `FRUIT_PERTURB_DX` is a lateral velocity impulse
# applied `FRUIT_PERTURB_AT` ticks into the descent - the scripted stand-in for
# the collision `logs/p95` measured by accident.  Control = every P135 knob
# unset (the shipped formula tracker); treatment = the model-based tracker with
# mid-descent re-aim.
set -u
cd "$(dirname "$0")/../.." || exit 1
SEED=${SEED:-5}
ATTEMPTS=${ATTEMPTS:-3}
OUT=logs/p135/envelope
mkdir -p "$OUT"

run() {  # name, extra env...
    local name=$1; shift
    echo "== $name"
    env ATTEMPTS="$ATTEMPTS" SEED="$SEED" FRUIT_BIARM=0 SKIP_SELFCHECK=1 \
        FRUIT_MOTION_REPORT=1 FRUIT_PERTURB_AT=20 \
        "$@" scripts/run.sh scripts/20_pick_place.py \
        > "$OUT/$name.log" 2>&1
    grep -c '\[perturb\]' "$OUT/$name.log" | xargs echo "  impulses:"
    grep -E '\[task\] dynamic catch-up|\[run\] summary' "$OUT/$name.log" \
        | sed 's/^/  /'
    grep -E '\[run\]   ' "$OUT/$name.log" | sed 's/^/  /'
}

for dx in 0.10 0.20 0.35; do
    run "c_dx${dx}" FRUIT_PERTURB_DX=$dx
    run "t_dx${dx}" FRUIT_PERTURB_DX=$dx FRUIT_TRACK=est FRUIT_DESCENT_TRACK=1
done
echo "== done"
