#!/usr/bin/env bash
# P84: one two-line run, kept canonical in <plain> and wall-stamped in <stamps>.
#
#   scripts/154_claim_run.sh logs/p84/D5.driver ENV=... \
#       bash logs/p84/one_run.sh logs/p84/D5.log logs/p84/D5.stamps
#
# Same contract as `logs/p80/one_run.sh` (P84's wall column is the *same*
# measurement as P80's: from the stamp stream, never inferred): the plain branch
# is a `tee`, so `<plain>` is byte-identical to a
# `scripts/run.sh ... > <plain>` redirect, and `<stamps>` is the same stream with
# the elapsed wall seconds prefixed per line (`logs/p84/stamp.py`, a byte copy of
# `logs/p80/stamp.py`, md5 fae805cd). `say()` flushes, so the stamps are per line.
#
# Exit status is the simulator's (PIPESTATUS[0]), so the claim wrapper's
# watchdog/overlap logic and the driver's failure handling still see it.
set -uo pipefail
plain=${1:?usage: one_run.sh <plain.log> <stamps>}
stamps=${2:?usage: one_run.sh <plain.log> <stamps>}
here=$(cd "$(dirname "$0")/../.." && pwd)
cd "$here" || exit 1

t0=$(date +%s.%N)
set -o pipefail
scripts/run.sh scripts/20_pick_place.py 2>&1 \
    | tee "$plain" \
    | python3 -u "$here/logs/p84/stamp.py" > "$stamps"
rc=${PIPESTATUS[0]}
t1=$(date +%s.%N)

echo "[p84] one_run rc=$rc wall_process=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.1f", b-a}')s plain=$plain stamps=$stamps"
exit "$rc"
