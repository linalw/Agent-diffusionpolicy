#!/usr/bin/env bash
# P132 - the serrated pad face, fixture first.
#
#   bash logs/p132/run_p132.sh                 # the full 4 x 4 x 3 battery (~2 min)
#   P132_REPEATS=1 P132_FRUITS=pear bash logs/p132/run_p132.sh
#
# One app session; every station is authored before `play()` and the payload is
# teleported between them (P117's protocol).  The table is re-derived from the
# log by `p132_report.py`; nothing is hand-copied.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$ROOT"

OUT=${P132_LOG:-logs/p132/fixture.log}
echo "[p132] fixture -> ${OUT}"
scripts/run.sh logs/p132/fixture.py > "${OUT}" 2>&1
grep -E "\[p132\] (station|support|A1|DONE)" "${OUT}" | tail -25
echo "[p132] table"
python3 logs/p132/p132_report.py | tee logs/p132/p132_report.txt
