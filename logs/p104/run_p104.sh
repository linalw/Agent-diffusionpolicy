#!/usr/bin/env bash
# P104 driver: every form is its own app session (the pad set is authored before
# `play()`), three fruits x three repeats inside one session.
#
#   bash logs/p104/run_p104.sh              # the battery -> logs/p104/fixture.txt
#   P104_FORMS="pinch_tip tripod" bash logs/p104/run_p104.sh
set -uo pipefail
cd "$(dirname "$0")/../.."

OUT=${P104_OUT:-logs/p104/fixture.txt}
FORMS=${P104_FORMS:-"pinch_plate pinch_tip tripod quad lip pinch_tip_moment tripod_moment"}
FRUITS=${P104_FRUITS:-"pear,orange,strawberry"}
REPEATS=${P104_REPEATS:-3}

: > "$OUT"
echo "# P104 axial break-away fixture - $(date -u +%FT%TZ)" | tee -a "$OUT"
echo "# forms: $FORMS" | tee -a "$OUT"
echo "# fruits: $FRUITS repeats: $REPEATS" | tee -a "$OUT"

for form in $FORMS; do
    P104_FORM="$form" P104_FRUITS="$FRUITS" P104_REPEATS="$REPEATS" \
        scripts/run.sh logs/p104/fixture_probe.py 2>&1 \
        | grep -E '^\[fruit\] \[p104\]|^(form|pinch_|tripod|quad|lip)' \
        | tee -a "$OUT"
    echo | tee -a "$OUT"
done

echo "# done $(date -u +%FT%TZ)" | tee -a "$OUT"
