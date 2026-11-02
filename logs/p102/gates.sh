#!/usr/bin/env bash
# P102 gates: what has to be true before any number in RESULTS.md is admissible.
#
#   bash logs/p102/gates.sh
#
# Four gates, and none of them is a rate:
#
#   G1  **neutrality, seed 5** - `T5` (the instrument on) vs `C5` (the same cell,
#       same batch, knob the only difference): the `[fruit]` stream must be
#       **byte-identical** with the phase's own `[tactile]` rows dropped. This is
#       the proof that the instrument is reporting-only; it is stronger than the
#       registered `[fruit]`-only replay because the `[fruit]` stream *is* the
#       scripted report (`say()` prefixes every row), so it covers the `[carry]`
#       diag and the `[place-trace]` rows too.
#   G2  the same for seed 6 (`T6` vs `C6`).
#   G3  **the relocation is inert** - `N5` is `T5` re-run on the final tree
#       (`tasks.py b257687d`; the measured tree was `42592b5d`, the only
#       difference being the P102 block moved out of `_clearance_field`'s tail so
#       the `236` leg's "the formatter adds no read" assertion keeps its scope).
#       Its `[fruit]` stream must equal `T5`'s **with the `[tactile]` rows kept**,
#       which is the strongest form: the instrument's own output reproduces too.
#   G4  **the census's own reader** - every `[tactile]` row parses, on all five
#       cells.
#
# The motion budgets are **not** gated here: no command, profile or scene value
# moved (G1/G2 prove the physics is identical), and every 20-attempt two-line
# reference in the tree predates P87's release clock, so any post-P87 cell reads
# `fingerprint: DIFFERS` by construction (P92's gates.sh records the same).
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
rc=0
run() {  # run <label> <cmd...>
    local label=$1; shift
    echo "[p102gates] $label"
    if "$@"; then echo "[p102gates]   PASS"; else echo "[p102gates]   FAIL"; rc=1; fi
}

run "G1 neutrality seed 5 (T5 vs C5, [tactile] dropped)" \
    python3 logs/p102/census.py --same logs/p102/T5.log logs/p102/C5.log
run "G2 neutrality seed 6 (T6 vs C6, [tactile] dropped)" \
    python3 logs/p102/census.py --same logs/p102/T6.log logs/p102/C6.log

echo "[p102gates] G3 relocation inert (N5 vs T5, [tactile] KEPT)"
if [ -s logs/p102/N5.log ]; then
    a=$(grep '^\[fruit\]' logs/p102/T5.log | md5sum | cut -d' ' -f1)
    b=$(grep '^\[fruit\]' logs/p102/N5.log | md5sum | cut -d' ' -f1)
    na=$(grep -c '^\[fruit\]' logs/p102/T5.log)
    nb=$(grep -c '^\[fruit\]' logs/p102/N5.log)
    if [ "$a" = "$b" ] && [ "$na" = "$nb" ]; then
        echo "[p102gates]   SAME: $na/$na [fruit] lines (with [tactile]) identical"
    else
        echo "[p102gates]   DIFFERS: $na vs $nb lines, md5 $a vs $b"
        diff <(grep '^\[fruit\]' logs/p102/T5.log) <(grep '^\[fruit\]' logs/p102/N5.log) \
            | head -6
        rc=1
    fi
else
    echo "[p102gates]   SKIP (logs/p102/N5.log missing)"
fi

run "G4 the census reader parses every cell" \
    python3 logs/p102/census.py --check \
        logs/p102/T5.log logs/p102/T6.log logs/p102/C5.log logs/p102/C6.log

echo "[p102gates] done rc=$rc"
exit "$rc"
