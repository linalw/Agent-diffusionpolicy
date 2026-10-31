#!/usr/bin/env bash
# P81: one scripted run, kept canonical in <plain> and wall-stamped in <stamps>.
#
#   scripts/154_claim_run.sh logs/p81/Tp5.driver ENV=... \
#       bash logs/p81/one_run.sh logs/p81/Tp5.log logs/p81/Tp5.stamps
#
# The plain branch is a `tee`, so `<plain>` is byte-identical to what a
# `scripts/run.sh ... > <plain>` redirect produces; `<stamps>` is the same stream
# with the elapsed wall seconds prefixed per line (`logs/p81/stamp.py`, the byte
# copy of P80's instrument), which is the only clock the scripted line does not
# print. `say()` flushes, so the stamps are per-line, not per-buffer.
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
    | python3 -u "$here/logs/p81/stamp.py" > "$stamps"
rc=${PIPESTATUS[0]}
t1=$(date +%s.%N)

echo "[p81] one_run rc=$rc wall_process=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.1f", b-a}')s plain=$plain stamps=$stamps"
exit "$rc"
