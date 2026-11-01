#!/usr/bin/env bash
# P82: one run, kept canonical in <plain> and wall-stamped in <stamps>.
#
#   scripts/154_claim_run.sh logs/p82/R1.driver ENV=... \
#       bash logs/p82/one_run.sh logs/p82/R1.log logs/p82/R1.stamps [entry.py]
#
# `<plain>` is a plain `tee` (byte-identical to a `>` redirect, so P80's parser and
# `105`/`190` can read it); `<stamps>` prefixes the elapsed wall seconds per line
# (`logs/p80/stamp.py`, unchanged) - the same instrument P80's wall column used, so
# P82's wall numbers and P80's are one measurement.
#
# `entry` defaults to the shipped `scripts/20_pick_place.py`; the profile builds
# pass `logs/p82/profile_20.py` (I2 timers) or override the launcher with
# `P82_LAUNCH="bash logs/p82/run_pyspy.sh"` (I1, which sets P82_PSPY).
set -uo pipefail
plain=${1:?usage: one_run.sh <plain.log> <stamps> [entry.py]}
stamps=${2:?usage: one_run.sh <plain.log> <stamps> [entry.py]}
entry=${3:-scripts/20_pick_place.py}
launch=${P82_LAUNCH:-scripts/run.sh}
here=$(cd "$(dirname "$0")/../.." && pwd)
cd "$here" || exit 1

t0=$(date +%s.%N)
set -o pipefail
$launch "$entry" 2>&1 \
    | tee "$plain" \
    | python3 -u "$here/logs/p80/stamp.py" > "$stamps"
rc=${PIPESTATUS[0]}
t1=$(date +%s.%N)

echo "[p82] one_run rc=$rc wall_process=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.1f", b-a}')s plain=$plain stamps=$stamps entry=$entry launch=$launch"
exit "$rc"
