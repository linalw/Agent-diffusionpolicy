#!/usr/bin/env bash
# P129 bench A - the pad material: the pair friction (A0) and the pinch's trade (A1).
#
#   bash logs/p129/run_p129_pinch.sh            # the full ladder (~4 min)
#   P129_REPEATS=1 P129_FRUITS=pear,orange bash logs/p129/run_p129_pinch.sh
#
# One app session: every station is authored before `play()`, and the payload is
# teleported between them (P117's protocol).
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$ROOT"

OUT=${P129_PINCH_LOG:-logs/p129/fixture_pinch.log}
echo "[p129] bench A -> ${OUT}"
scripts/run.sh logs/p129/fixture_pinch.py > "${OUT}" 2>&1
grep -E "\[p129\] (station|support|A0 done)" "${OUT}" | tail -30
echo "[p129] A0"
sed -n '/^A0 - the pair friction/,/^$/p' "${OUT}"
echo "[p129] A1"
sed -n '/^profile    fruit/,/\[p129\] DONE/p' "${OUT}"
