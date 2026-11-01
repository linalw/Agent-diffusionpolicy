#!/usr/bin/env bash
# P87 gates - the ones that are not a report (PREREG section 4).
#
#   bash logs/p87/gates.sh
#
#   G0  the flip is resolution-only: the four cells replay P86's own four cells
#       on the `[fruit]` stream, dropping the diag rows **and** P87's new
#       `[fruit] [biarm] release profile:` row (T5/T6 read `=1(default)` where
#       P86's R5/R6 read `=1(explicit)` - that one row is the whole difference).
#   G1  motion: `190` on C5 against the seed-5 20-attempt reference and on C6
#       against P86's seed-6 record - both must PASS (they are the pre-flip
#       clock). T5/T6 are **recorded** (DIFFERS by construction) and gated on
#       budgets only.
#   G2a the single-arm end-to-end inertness is `logs/p87/single_accept.*`
#       (see `logs/p87/run_p87_extra.sh`, which runs `FRUIT_BIARM=0
#       scripts/accept.sh` and the shared-station pair); this script re-reads
#       its verdicts from the artefacts.
#   P6  `105 --min-success-rate 0.0` on all four cells: the descent budgets per
#       leg, reported per seed. A rate-only failure is filtered; a *budget*
#       failure is not.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
OUT=logs/p87
REF5="logs/p80/motion_reference_twoline_p80_20.json"
REF6="logs/p86/motion_reference_twoline_C6_20.json"
FLOOR=0.5
fail=0
note() { echo "[p87] $*"; }

for tag in C5 T5 C6 T6; do
    [ -s "$OUT/$tag.log" ] || { note "MISSING $tag"; fail=1; }
done
[ -s "$OUT/C5.log" ] && [ -s "$OUT/T5.log" ] && [ -s "$OUT/C6.log" ] && [ -s "$OUT/T6.log" ] || exit 1

note "G0 replay P86's four cells (the new release row + the diag rows dropped)"
python3 "$OUT/p87_report.py" --same logs/p86/C5.log "$OUT/C5.log" || fail=1
python3 "$OUT/p87_report.py" --same logs/p86/R5.log "$OUT/T5.log" || fail=1
python3 "$OUT/p87_report.py" --same logs/p86/C6.log "$OUT/C6.log" || fail=1
python3 "$OUT/p87_report.py" --same logs/p86/R6.log "$OUT/T6.log" || fail=1

note "G1a 190 (the pre-flip clock: MUST PASS) C5"
TWOLINE_REF="$REF5" scripts/190_twoline_gate.sh -m "$FLOOR" "$OUT/C5.log" 2>&1 \
    | tee "$OUT/C5.gate"
[ "${PIPESTATUS[0]}" -ne 0 ] && fail=1

note "G1b 190 (the pre-flip clock: MUST PASS) C6"
TWOLINE_REF="$REF6" scripts/190_twoline_gate.sh -m "$FLOOR" "$OUT/C6.log" 2>&1 \
    | tee "$OUT/C6.gate"
[ "${PIPESTATUS[0]}" -ne 0 ] && fail=1

for tag in T5 T6; do
    case "$tag" in
        T5) ref="$REF5" ;;
        *)  ref="$REF6" ;;
    esac
    note "G1c 190 (recorded - DIFFERS expected: the moved release profile) $tag"
    TWOLINE_REF="$ref" scripts/190_twoline_gate.sh -m "$FLOOR" "$OUT/$tag.log" 2>&1 \
        | tee "$OUT/$tag.gate"
done

note "P6 budgets only (the descent |v|max and the lurch bound, per leg)"
# A **control** must pass its budgets outright (the pre-flip clock is the shipped
# one). A **treatment** cell's overflow is decided by PREREG S5's P6 tiering, not
# here: `p87_report.py --blocks` reads each leg against 105's own per-leg budget
# and returns CONSIDERED TRADE (exactly the one P86 R6 leg) or FAIL (>1 leg, or
# a leg at the other seed). Bubbling 105's exit up for a treatment cell would
# make the pre-registered tier unreachable.
for tag in C5 T5 C6 T6; do
    python3 scripts/105_motion_regression.py "$OUT/$tag.log" \
        --min-success-rate 0.0 > "$OUT/$tag.budgets" 2>&1
    rc=$?
    note "105 $tag exit=$rc"
    grep -E "^  worst: |descent [0-9]+ \(" "$OUT/$tag.budgets" | sed 's/^/[p87]   /'
    case "$tag" in
        C5|C6) [ "$rc" -ne 0 ] && fail=1 ;;
        *) note "  $tag's budget result is P6's (see p87_report.py --blocks)" ;;
    esac
done

note "P6 tiering (PREREG S5): the gate's own verdict"
python3 "$OUT/p87_report.py" --blocks > "$OUT/p87_report.txt" 2>&1
verdict=$?
tail -3 "$OUT/p87_report.txt" | sed 's/^/[p87]   /'
[ "$verdict" -ne 0 ] && fail=1

note "G2a the single-arm acceptance (346/346 + fingerprint)"
if [ -s "$OUT/single_accept.log" ] && [ -s "$OUT/single_accept.same" ]; then
    cat "$OUT/single_accept.same"
    grep -q "IDENTICAL" "$OUT/single_accept.same" || fail=1
    grep -q "fingerprint: matches" "$OUT/single_accept.gate" || fail=1
else
    note "MISSING the single-arm acceptance artefacts (run_p87_extra.sh)"; fail=1
fi

note "G2b the shared-station pair (unset == explicit 0; PREREG A1, see RESULTS)"
if [ -s "$OUT/shared_unset.log" ] && [ -s "$OUT/shared_zero.log" ]; then
    # DEVIATION A1 (recorded in RESULTS.md): PREREG G2b says "whole `[fruit]`
    # stream", but the two runs legitimately differ in the **origin** field of
    # the new row (`=0(scope-off)` vs `=0(explicit)`) - the label recording how
    # the value was decided, which is its whole purpose. The physics claim is:
    # identical on every other `[fruit]` line, and the same clock (holds, ticks).
    python3 "$OUT/p87_report.py" --same "$OUT/shared_zero.log" "$OUT/shared_unset.log" || fail=1
    python3 "$OUT/p87_report.py" --profile "$OUT/shared_zero.log" "$OUT/shared_unset.log" || fail=1
    python3 "$OUT/p87_report.py" --same-raw "$OUT/shared_zero.log" "$OUT/shared_unset.log" \
        > "$OUT/shared_raw_same.txt" 2>&1 || true
    echo "[p87]   raw (no filter) comparison: the row's origin only -> $OUT/shared_raw_same.txt"
else
    note "MISSING the shared-station pair (run_p87_extra.sh)"; fail=1
fi

note "gates fail=$fail"
exit "$fail"
