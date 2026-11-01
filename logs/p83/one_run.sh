#!/usr/bin/env bash
# P83: one scripted run, kept canonical in <plain> and wall-stamped in <stamps>.
#
#   scripts/154_claim_run.sh logs/p83/C5.driver ENV=... \
#       bash logs/p83/one_run.sh logs/p83/C5.log logs/p83/C5.stamps
#
# Same contract as `logs/p80/one_run.sh` (P83's wall column is the *same*
# measurement as P80's, so the two are comparable): the plain branch is a `tee`,
# so `<plain>` is byte-identical to a `scripts/run.sh ... > <plain>` redirect,
# and `<stamps>` is the same stream with the elapsed wall seconds prefixed per
# line (`logs/p80/stamp.py`). `say()` flushes, so the stamps are per line.
#
# Exit status is the simulator's (PIPESTATUS[0]).
set -uo pipefail
plain=${1:?usage: one_run.sh <plain.log> <stamps>}
stamps=${2:?usage: one_run.sh <plain.log> <stamps>}
here=$(cd "$(dirname "$0")/../.." && pwd)
cd "$here" || exit 1

t0=$(date +%s.%N)
set -o pipefail
scripts/run.sh scripts/20_pick_place.py 2>&1 \
    | tee "$plain" \
    | python3 -u "$here/logs/p80/stamp.py" > "$stamps"
rc=${PIPESTATUS[0]}
t1=$(date +%s.%N)

echo "[p83] one_run rc=$rc wall_process=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.1f", b-a}')s plain=$plain stamps=$stamps"
exit "$rc"
