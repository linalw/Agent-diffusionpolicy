#!/usr/bin/env bash
# P135 phase 1b: the downstream rung - the class the catch-up cannot close.
#
# A fruit that *speeds up* downstream opens a gap at (v_fruit - v_tip): the
# catch-up's 200-tick reach budget is spent against a target that is running
# away.  The lateral rung (`run_envelope.sh`) only translates the fruit, which
# the catch-up can close (and what it cannot close lands in the *carry* class,
# not the acquisition class).
#
# C = shipped formula tracker; T = estimator + mid-descent re-aim; F = T plus
# the residual-proportional closing lead (`FRUIT_TRACK_CATCH_SPEED`).
set -u
cd "$(dirname "$0")/../.." || exit 1
SEED=${SEED:-5}
ATTEMPTS=${ATTEMPTS:-3}
OUT=logs/p135/downstream
mkdir -p "$OUT"

run() {  # name, extra env...
    local name=$1; shift
    echo "== $name"
    env ATTEMPTS="$ATTEMPTS" SEED="$SEED" FRUIT_BIARM=0 SKIP_SELFCHECK=1 \
        FRUIT_MOTION_REPORT=1 FRUIT_PERTURB_AT=20 FRUIT_TRACK_DIAG=1 "$@" \
        scripts/run.sh scripts/20_pick_place.py > "$OUT/$name.log" 2>&1
    grep -E '\[task\] dynamic descent' "$OUT/$name.log" | sed 's/^/  /' | cut -c1-120
    grep -E '\[catch\]' "$OUT/$name.log" | sed 's/^/  /'
    grep -E '\[run\] summary' "$OUT/$name.log" | sed 's/^/  /'
    grep -E '\[run\]   ' "$OUT/$name.log" | sed 's/^/  /'
}

for dy in -0.10 -0.20 -0.30; do
    run "c_dy${dy}" FRUIT_PERTURB_DY=$dy
    run "t_dy${dy}" FRUIT_PERTURB_DY=$dy FRUIT_TRACK=est FRUIT_DESCENT_TRACK=1
done
# The faster-correction arm, at the rung the screen says binds.
LEAD_AT=${LEAD_AT:--0.20}
run "f_dy${LEAD_AT}" FRUIT_PERTURB_DY=$LEAD_AT FRUIT_TRACK=est \
    FRUIT_DESCENT_TRACK=1 FRUIT_TRACK_CATCH_SPEED=0.20
echo "== done"
