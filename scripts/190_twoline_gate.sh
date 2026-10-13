#!/usr/bin/env bash
# Two-line scenario gate: the per-scenario motion reference + an explicit,
# two-line success floor - never 105's implicit single-arm 0.75.
#
#   scripts/190_twoline_gate.sh logs/w7/10_dense_twoline_1.log [LOG...]
#   scripts/190_twoline_gate.sh -m 0.5 logs/w6/31_lever_park_1.log
#   TWOLINE_REF=configs/motion_reference_patch.json \
#       scripts/190_twoline_gate.sh -m 0.5 logs/w7/20_patch_battery_1.log
#
# Why this exists: `scripts/105_motion_regression.py` judges a log against the
# *single-arm* dynamic line (its 0.75 floor is the single-arm 9/10 calibration
# and its reference defaults to `configs/motion_reference.json`). A two-line log
# is a different scenario - the AGENTS section 2 rule says compare it against
# its own per-scenario reference and quote its own floor - and gating one with
# the 105 defaults trips the wrong rate floor and/or the wrong fingerprint.
#
# The scenario pin: every log must carry the two-line scheduler banner
# (`[biarm] two-line scheduler:`), so a single-arm or shared-station log cannot
# be silently judged here. The reference defaults to the dense 10-attempt
# two-line fingerprint (`configs/motion_reference_twoline.json`, W7-A); a log
# from another two-line supply/branch will not match it - write that scenario's
# own reference and pass TWOLINE_REF (per-scenario references, one reference
# per scenario, is the point).
#
# The floor: the dense two-line scenario's shipped branch measures 7/10
# (`logs/w7/10`), pre-flip 8/10 (`logs/w4/20`), the W1 branch 7/10; the default
# bar is therefore 0.60, one attempt below the branch of record - a genuine
# regression to 5/10 fails. The 20-attempt W6-B patch battery measures 10-12/20
# and needs its own floor (`-m 0.5`) and its own reference. The single-arm
# 0.75 floor in 105 is untouched.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

REF=${TWOLINE_REF:-configs/motion_reference_twoline.json}
FLOOR=${TWOLINE_FLOOR:-0.60}

usage() {
    echo "usage: $0 [-r REF] [-m FLOOR] LOG [LOG...]" >&2
    echo "  REF   per-scenario fingerprint (default $REF)" >&2
    echo "  FLOOR two-line success floor (default $FLOOR; patch battery 0.5)" >&2
    exit 2
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        -r) [ "$#" -ge 2 ] || usage; REF=$2; shift 2 ;;
        -m) [ "$#" -ge 2 ] || usage; FLOOR=$2; shift 2 ;;
        -h|--help) usage ;;
        --) shift; break ;;
        -*) usage ;;
        *) break ;;
    esac
done
[ "$#" -ge 1 ] || usage
[ -f "$REF" ] || { echo "190: reference not found: $REF" >&2; exit 2; }

echo "190: two-line gate: reference=$REF floor=$FLOOR"
status=0
for log in "$@"; do
    if [ ! -f "$log" ]; then
        echo "190: FAIL missing log: $log" >&2
        status=1
        continue
    fi
    if ! grep -q '\[fruit\] \[biarm\] two-line scheduler:' "$log"; then
        echo "190: FAIL not a two-line scenario log (no two-line scheduler banner): $log" >&2
        status=1
        continue
    fi
    if python3 scripts/105_motion_regression.py "$log" \
            --fingerprint "$REF" --min-success-rate "$FLOOR"; then
        echo "190: PASS $log"
    else
        echo "190: FAIL $log" >&2
        status=1
    fi
done

if [ "$status" -eq 0 ]; then
    echo "190: every log matches $REF and is at or above the two-line floor $FLOOR"
else
    echo "190: at least one log failed" >&2
fi
exit "$status"
