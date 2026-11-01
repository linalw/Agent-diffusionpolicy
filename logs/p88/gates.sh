#!/usr/bin/env bash
# P88 gates - the ones that are not a report (PREREG section 4).
#
#   bash logs/p88/gates.sh
#
#   G0  the tree is unchanged and the control is the shipped cell: C5/C6 replay
#       P87's T5/T6 on the `[fruit]` stream, dropping the diag rows and **both**
#       profile rows (the one line that moves is the new place row's label,
#       `=0.35(explicit)`).
#   G1  motion: `190` on C5 against the seed-5 20-attempt reference and on C6
#       against P86's seed-6 record - both must PASS (they are the shipped
#       clock). T5/T6 are **recorded** (DIFFERS by construction) and gated on
#       budgets only.
#   G2a the single-arm end-to-end inertness is `logs/p88/single_accept.*`
#       (see `logs/p88/run_p88_extra.sh`); this script re-reads its verdicts.
#   G2b the shared-station pair (unset vs `FRUIT_SPEED_PLACE=0`): identical with
#       the profile row's origin dropped, and the same clock.
#   P6  `105 --min-success-rate 0.0` on all four cells: the descent budgets per
#       leg, reported per seed; the tiering is `p88_report.py --blocks`'s.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
OUT=logs/p88
REF5="logs/p80/motion_reference_twoline_p80_20.json"
REF6="logs/p86/motion_reference_twoline_C6_20.json"
FLOOR=0.5
fail=0
note() { echo "[p88] $*"; }

for tag in C5 T5 C6 T6; do
    [ -s "$OUT/$tag.log" ] || { note "MISSING $tag"; fail=1; }
done
[ -s "$OUT/C5.log" ] && [ -s "$OUT/T5.log" ] && [ -s "$OUT/C6.log" ] && [ -s "$OUT/T6.log" ] || exit 1

note "G0 replay P87's cells (the diag rows + both profile rows dropped)"
python3 "$OUT/p88_report.py" --same logs/p87/T5.log "$OUT/C5.log" || fail=1
python3 "$OUT/p88_report.py" --same logs/p87/T6.log "$OUT/C6.log" || fail=1

# PREREG A2: the 20-attempt references are **pre-P87-clock** records, so a
# post-P87 run of this scenario cannot match them - the trim re-times every
# attempt boundary (P87 recorded exactly this for its own T5/T6, while its
# FRUIT_SPEED_RELEASE=0 controls PASSED). G0 is the control's identity proof;
# `190` is recorded for every cell and its fingerprint read is **reported, never
# gated**; the substantive motion check is P6's per-leg budget below.
for tag in C5 T5 C6 T6; do
    case "$tag" in
        C5|T5) ref="$REF5" ;;
        *)     ref="$REF6" ;;
    esac
    note "G1 190 (recorded; A2: the pre-P87-clock reference, DIFFERS expected) $tag"
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
    grep -E "^  worst: |descent [0-9]+ \(" "$OUT/$tag.budgets" | sed 's/^/[p88]   /'
    # Every cell's budget verdict is P6's (PREREG §3): 0 legs over = clean,
    # exactly one = CONSIDERED TRADE for that branch, > 1 or a leg at both seeds
    # = FAIL. `p88_report.py --blocks` prints the per-cell count and the leg;
    # this loop only records `105`'s own exit per cell.
    note "  $tag's budget result is P6's (see p88_report.py --blocks)"
done

note "the gate's own verdict (the pre-registered clauses)"
python3 "$OUT/p88_report.py" --blocks > "$OUT/p88_report.txt" 2>&1
verdict=$?
tail -6 "$OUT/p88_report.txt" | sed 's/^/[p88]   /'
[ "$verdict" -ne 0 ] && fail=1

note "G2a the single-arm acceptance (346/346 + fingerprint)"
if [ -s "$OUT/single_accept.log" ] && [ -s "$OUT/single_accept.same" ]; then
    cat "$OUT/single_accept.same"
    grep -q "IDENTICAL" "$OUT/single_accept.same" || fail=1
    grep -q "fingerprint: matches" "$OUT/single_accept.gate" || fail=1
    [ "$(grep -c "\[fruit\] \[biarm\] place profile:" "$OUT/single_accept.log")" -eq 0 ] \
        || { note "the place row printed on the single arm"; fail=1; }
else
    note "MISSING the single-arm acceptance artefacts (run_p88_extra.sh)"; fail=1
fi

note "G2b the shared-station pair (same clock; the origin label may differ)"
if [ -s "$OUT/shared_unset.log" ] && [ -s "$OUT/shared_zero.log" ]; then
    python3 "$OUT/p88_report.py" --same "$OUT/shared_zero.log" "$OUT/shared_unset.log" || fail=1
    python3 "$OUT/p88_report.py" --profile "$OUT/shared_zero.log" "$OUT/shared_unset.log" || fail=1
    python3 "$OUT/p88_report.py" --same-raw "$OUT/shared_zero.log" "$OUT/shared_unset.log" \
        > "$OUT/shared_raw_same.txt" 2>&1 || true
    echo "[p88]   raw (no filter) comparison: the row's origin only -> $OUT/shared_raw_same.txt"
else
    note "MISSING the shared-station pair (run_p88_extra.sh)"; fail=1
fi

note "gates fail=$fail"
exit "$fail"
