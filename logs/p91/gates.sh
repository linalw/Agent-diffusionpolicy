#!/usr/bin/env bash
# P91 gates - the ones that are not a report (PREREG sections 4 and 6).
#
#   bash logs/p91/gates.sh
#
#   G0  the tree is unchanged *before* the cell: C5/C6 (the explicit 60-tick
#       probe) replay the pre-change records `logs/p89/T5.log` / `logs/p89/T6.log`
#       on the `[fruit]` stream, dropping the diag/trace rows and **all four**
#       profile rows (the one line that moves is the new take-off row).
#   G1  motion: `190` on every cell is **recorded** (the 20-attempt references in
#       logs/ are pre-P87-clock records, so a post-P87 run cannot match them -
#       P87/P88/P89's registered read); the substantive check is P6's per-leg
#       budget via `105 --min-success-rate 0.0`.
#   P8a the single-arm end-to-end inertness is `logs/p91/single_accept.*`
#       (see `run_p91_extra.sh`); this script re-reads its verdicts.
#   P8b the shared-station pair (unset vs `FRUIT_DYNAMIC_PROBE_TICKS=60`):
#       identical with the row's origin dropped, and the same clock.
#   P8c a fresh unset 20-attempt run (N5) on the final tree replays the pre-change
#       record `logs/p89/T5.log` and its own phase control `C5`.
#   P6  `105 --min-success-rate 0.0` on all four cells: the descent budgets per
#       leg, reported per seed; the tiering is `p91_report.py --blocks`'s.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
OUT=logs/p91
REF5="logs/p80/motion_reference_twoline_p80_20.json"
REF6="logs/p86/motion_reference_twoline_C6_20.json"
FLOOR=0.5
fail=0
note() { echo "[p91] $*"; }

for tag in C5 T5 C6 T6; do
    [ -s "$OUT/$tag.log" ] || { note "MISSING $tag"; fail=1; }
done
[ -s "$OUT/C5.log" ] && [ -s "$OUT/T5.log" ] && [ -s "$OUT/C6.log" ] && [ -s "$OUT/T6.log" ] || exit 1

note "G0 the controls are the pre-change cell (the diag rows + all four profile rows dropped)"
python3 "$OUT/p91_report.py" --same logs/p89/T5.log "$OUT/C5.log" || fail=1
python3 "$OUT/p91_report.py" --same logs/p89/T6.log "$OUT/C6.log" || fail=1

for tag in C5 T5 C6 T6; do
    case "$tag" in
        C5|T5) ref="$REF5" ;;
        *)     ref="$REF6" ;;
    esac
    note "G1 190 (recorded; the pre-P87-clock reference, DIFFERS expected) $tag"
    TWOLINE_REF="$ref" scripts/190_twoline_gate.sh -m "$FLOOR" "$OUT/$tag.log" 2>&1 \
        | tee "$OUT/$tag.gate"
    note "    $tag fingerprint: $(grep -m1 'fingerprint:' "$OUT/$tag.gate" | sed 's/^ *//')"
done

note "P6 budgets only (the descent |v|max and the lurch bound, per leg)"
for tag in C5 T5 C6 T6; do
    python3 scripts/105_motion_regression.py "$OUT/$tag.log" \
        --min-success-rate 0.0 > "$OUT/$tag.budgets" 2>&1
    rc=$?
    note "105 $tag exit=$rc"
    grep -E "^  worst: |descent [0-9]+ \(" "$OUT/$tag.budgets" | sed 's/^/[p91]   /'
    note "  $tag's budget result is P6's (see p91_report.py --blocks)"
done

note "the gate's own verdict (the pre-registered clauses)"
python3 "$OUT/p91_report.py" --blocks > "$OUT/p91_report.txt" 2>&1
tail -10 "$OUT/p91_report.txt" | sed 's/^/[p91]   /'

note "P8a the single-arm acceptance (346/346 + fingerprint)"
if [ -s "$OUT/single_accept.log" ] && [ -s "$OUT/single_accept.same" ]; then
    cat "$OUT/single_accept.same"
    grep -q "IDENTICAL" "$OUT/single_accept.same" || fail=1
    grep -q "fingerprint: matches" "$OUT/single_accept.gate" || fail=1
    [ "$(grep -c "\[fruit\] \[biarm\] take-off profile:" "$OUT/single_accept.log")" -eq 0 ] \
        || { note "the take-off row printed on the single arm"; fail=1; }
else
    note "MISSING the single-arm acceptance artefacts (run_p91_extra.sh)"; fail=1
fi

note "P8b the shared-station pair (same clock; the origin label may differ)"
if [ -s "$OUT/shared_unset.log" ] && [ -s "$OUT/shared_zero.log" ]; then
    python3 "$OUT/p91_report.py" --same "$OUT/shared_zero.log" "$OUT/shared_unset.log" || fail=1
    python3 "$OUT/p91_report.py" --profile "$OUT/shared_zero.log" "$OUT/shared_unset.log" || fail=1
    python3 "$OUT/p91_report.py" --same-raw "$OUT/shared_zero.log" "$OUT/shared_unset.log" \
        > "$OUT/shared_raw_same.txt" 2>&1 || true
    echo "[p91]   raw (no filter) comparison: the row's origin only -> $OUT/shared_raw_same.txt"
else
    note "MISSING the shared-station pair (run_p91_extra.sh)"; fail=1
fi

note "P8c the final tree's default is the shipped clock (N5 replays the pre-change record)"
if [ -s "$OUT/N5.log" ]; then
    python3 "$OUT/p91_report.py" --same logs/p89/T5.log "$OUT/N5.log" || fail=1
    python3 "$OUT/p91_report.py" --same "$OUT/C5.log" "$OUT/N5.log" || fail=1
    grep -q "FRUIT_DYNAMIC_PROBE_TICKS=60(two-line)" "$OUT/N5.log" \
        || { note "N5 did not resolve the shipped probe clock as the default"; fail=1; }
else
    note "MISSING the N5 replay (run_p91_extra.sh)"; fail=1
fi

note "gates fail=$fail"
exit "$fail"
