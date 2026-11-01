#!/usr/bin/env bash
# P89 gates - the ones that are not a report (PREREG section 4).
#
#   bash logs/p89/gates.sh
#
#   G0  the tree is unchanged and the control is the shipped cell: C5/C6 replay
#       P88's T5/T6 on the `[fruit]` stream, dropping the diag rows and **all
#       three** profile rows (P88's logs have no lift row; the one line that
#       moves is the new lift row's label, `=0.30(explicit)`).
#   G1  motion: `190` on every cell is **recorded** (the 20-attempt references in
#       logs/ are pre-P87-clock records, so a post-P87 run cannot match them -
#       P87/P88's registered read); the substantive check is P6's per-leg budget
#       via `105 --min-success-rate 0.0`.
#   G2a the single-arm end-to-end inertness is `logs/p89/single_accept.*`
#       (see `run_p89_extra.sh`); this script re-reads its verdicts.
#   G2b the shared-station pair (unset vs `FRUIT_SPEED_LIFT=0`): identical with
#       the profile row's origin dropped, and the same clock.
#   G2c a fresh unset 20-attempt run (N5) on the final tree replays C5.
#   P6  `105 --min-success-rate 0.0` on all four cells: the descent budgets per
#       leg, reported per seed; the tiering is `p89_report.py --blocks`'s.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
OUT=logs/p89
REF5="logs/p80/motion_reference_twoline_p80_20.json"
REF6="logs/p86/motion_reference_twoline_C6_20.json"
FLOOR=0.5
fail=0
note() { echo "[p89] $*"; }

for tag in C5 T5 C6 T6; do
    [ -s "$OUT/$tag.log" ] || { note "MISSING $tag"; fail=1; }
done
[ -s "$OUT/C5.log" ] && [ -s "$OUT/T5.log" ] && [ -s "$OUT/C6.log" ] && [ -s "$OUT/T6.log" ] || exit 1

note "G0 replay P88's *control* cells (the diag rows + all three profile rows dropped)"
# PREREG A1: the targets are P88's **C5/C6** - the cells that ran the shipped
# place cap (0.35). P88's T5/T6 carried the place raise and would differ by that
# cell, which is the diagnostic below, not the clause.
python3 "$OUT/p89_report.py" --same logs/p88/C5.log "$OUT/C5.log" || fail=1
python3 "$OUT/p89_report.py" --same logs/p88/C6.log "$OUT/C6.log" || fail=1
note "G0 diagnostic (recorded, not gated): against P88's T cells the replay must DIFFER"
python3 "$OUT/p89_report.py" --same logs/p88/T5.log "$OUT/C5.log" > "$OUT/C5_vs_p88T5.txt" 2>&1 || true
python3 "$OUT/p89_report.py" --same logs/p88/T6.log "$OUT/C6.log" > "$OUT/C6_vs_p88T6.txt" 2>&1 || true
sed 's/^/[p89]   /' "$OUT/C5_vs_p88T5.txt"
grep -q "DIFFERS" "$OUT/C5_vs_p88T5.txt" \
    && note "    (differs, as it must: P88's T5 ran the place raise)" \
    || { note "    the place cell left no trace - the filter may be hiding everything"; fail=1; }

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
    grep -E "^  worst: |descent [0-9]+ \(" "$OUT/$tag.budgets" | sed 's/^/[p89]   /'
    note "  $tag's budget result is P6's (see p89_report.py --blocks)"
done

note "the gate's own verdict (the pre-registered clauses)"
python3 "$OUT/p89_report.py" --blocks > "$OUT/p89_report.txt" 2>&1
verdict=$?
tail -8 "$OUT/p89_report.txt" | sed 's/^/[p89]   /'
[ "$verdict" -ne 0 ] && fail=1

note "G2a the single-arm acceptance (346/346 + fingerprint)"
if [ -s "$OUT/single_accept.log" ] && [ -s "$OUT/single_accept.same" ]; then
    cat "$OUT/single_accept.same"
    grep -q "IDENTICAL" "$OUT/single_accept.same" || fail=1
    grep -q "fingerprint: matches" "$OUT/single_accept.gate" || fail=1
    [ "$(grep -c "\[fruit\] \[biarm\] lift profile:" "$OUT/single_accept.log")" -eq 0 ] \
        || { note "the lift row printed on the single arm"; fail=1; }
else
    note "MISSING the single-arm acceptance artefacts (run_p89_extra.sh)"; fail=1
fi

note "G2b the shared-station pair (same clock; the origin label may differ)"
if [ -s "$OUT/shared_unset.log" ] && [ -s "$OUT/shared_zero.log" ]; then
    python3 "$OUT/p89_report.py" --same "$OUT/shared_zero.log" "$OUT/shared_unset.log" || fail=1
    python3 "$OUT/p89_report.py" --profile "$OUT/shared_zero.log" "$OUT/shared_unset.log" || fail=1
    python3 "$OUT/p89_report.py" --same-raw "$OUT/shared_zero.log" "$OUT/shared_unset.log" \
        > "$OUT/shared_raw_same.txt" 2>&1 || true
    echo "[p89]   raw (no filter) comparison: the row's origin only -> $OUT/shared_raw_same.txt"
else
    note "MISSING the shared-station pair (run_p89_extra.sh)"; fail=1
fi

note "G2c the final tree's default is the shipped clock (N5 replays C5)"
if [ -s "$OUT/N5.log" ]; then
    python3 "$OUT/p89_report.py" --same "$OUT/C5.log" "$OUT/N5.log" || fail=1
    [ "$(grep -c "\[fruit\] \[biarm\] lift profile: FRUIT_SPEED_LIFT=0.30(scope-off)" \
        "$OUT/N5.log")" -ge 1 ] \
        || { note "N5 did not resolve the shipped lift clock as the default"; fail=1; }
else
    note "MISSING the N5 replay (run_p89_extra.sh)"; fail=1
fi

note "gates fail=$fail"
exit "$fail"
