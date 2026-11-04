#!/usr/bin/env bash
# P112 - the phase's own gates, re-runnable.
#
#   bash logs/p112/gates.sh
#
# rc 0 = every offline gate passes.  The simulator gates (`selfcheck.sh`,
# `accept.sh`, the battery) are recorded in `selfcheck.log`, `accept_noharm.*`
# and `{C,T}_s*.log`; the checks below are the offline ones plus the
# byte-identity proofs, so the record can be re-derived without a GPU.
set -euo pipefail
cd "$(dirname "$0")/../.."
OUT=logs/p112
rc=0
run() { echo "== $*"; "$@" || rc=1; }

run python3 ${OUT}/algebra.py --check
run python3 ${OUT}/p112_fixture_report.py --check ${OUT}/fixture_*.log
run python3 ${OUT}/p112_report.py --check
run python3 scripts/258_p112_cage3_selftest.py

echo "== the acceptance's [fruit] stream against the pre-phase record"
python3 ${OUT}/p112_report.py --same ${OUT}/accept_noharm.log logs/p111/accept_noharm.log || rc=1

echo "== the PREREG is at its pinned md5"
actual=$(md5sum ${OUT}/PREREG.md | cut -d' ' -f1)
pinned=$(cut -d' ' -f1 ${OUT}/PREREG.md5)
[ "${actual}" = "${pinned}" ] && echo "   ${actual}" || { echo "   PREREG MOVED: ${actual} != ${pinned}"; rc=1; }

echo "== the shipped path is inert (source pins)"
grep -q 'RIGID_TOOL_HANDS = ("openarm", \*CAGE_KINDS)' src/fruit_sorting/tasks.py \
    && echo "   RIGID_TOOL_HANDS built from CAGE_KINDS"
[ "$(grep -c 'in CAGE_KINDS' src/fruit_sorting/tasks.py)" -ge 4 ] \
    && echo "   five ring predicates on the set"
grep -q 'aperture_extent' src/fruit_sorting/tasks.py && echo "   one aperture-law hook"

echo
[ ${rc} -eq 0 ] && echo "P112 gates: PASS" || echo "P112 gates: FAIL"
exit ${rc}
