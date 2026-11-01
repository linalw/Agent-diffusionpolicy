#!/usr/bin/env bash
# P88 G2 - the inertness runs on the paths the two-line scope must not touch.
#
#   bash logs/p88/run_p88_extra.sh            # all three, sequential
#   bash logs/p88/run_p88_extra.sh single     # the single-arm acceptance only
#   bash logs/p88/run_p88_extra.sh shared     # the shared-station pair only
#   bash logs/p88/run_p88_extra.sh accept10   # the 10-attempt reference source
#
# `single`    `FRUIT_BIARM=0 scripts/accept.sh` (ten attempts, the pre-P85 single
#             arm) with `FRUIT_MOTION_REPORT=1`: the raw `[fruit]` stream must be
#             346/346 identical to `logs/p71/accept_rails_none.log` and the gate
#             must read `fingerprint: matches` `configs/motion_reference_single.json`.
#             The two profile rows must be **absent** here (they print only in a
#             bimanual session): that absence is the byte-identity proof.
# `shared`    the shared station (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0`), 4
#             attempts, env **unset** vs `FRUIT_SPEED_PLACE=0`: identical on the
#             `[fruit]` stream with the place row's origin field dropped, and the
#             same clock (v_max 0.35, a_max 1.089, 362 ticks) in both.
# `accept10`  the shipped scenario at ten attempts, the same tree, for the two
#             two-line-side motion references (only used if the gate passes).
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
OUT=logs/p88
mkdir -p "$OUT"
sel=("$@")
want() { [ "${#sel[@]}" -eq 0 ] || [[ " ${sel[*]} " == *" $1 "* ]]; }
note() { echo "[p88] $*"; }

if want single; then
    note "START $(date +%H:%M:%S) single-arm acceptance (FRUIT_BIARM=0)"
    ACCEPT_LOG="$OUT/single_accept.log" FRUIT_BIARM=0 SKIP_SELFCHECK=1 \
        scripts/accept.sh > "$OUT/single_accept.gate" 2>&1
    rc=$?
    note "exit=$rc $(date +%H:%M:%S) single-arm acceptance"
    tail -12 "$OUT/single_accept.gate" | sed 's/^/[p88]   /'
    python3 "$OUT/p88_report.py" --same-raw logs/p71/accept_rails_none.log \
        "$OUT/single_accept.log" 2>&1 | tee "$OUT/single_accept.same"
    for row in "release profile:" "place profile:"; do
        echo "[p88]   '${row}' rows in the single-arm log: $(grep -c "$row" "$OUT/single_accept.log")"
    done
fi

if want shared; then
    for arm in unset zero; do
        envs=(HEADLESS=1 FRUIT_MOTION_REPORT=1 ATTEMPTS=4
              FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0)
        [ "$arm" = zero ] && envs+=(FRUIT_SPEED_PLACE=0)
        note "START $(date +%H:%M:%S) shared-$arm"
        RUN_LIMIT=900 scripts/154_claim_run.sh "$OUT/shared_$arm.driver" "${envs[@]}" \
            bash logs/p80/one_run.sh "$OUT/shared_$arm.log" "$OUT/shared_$arm.stamps"
        note "exit=$? $(date +%H:%M:%S) shared-$arm"
    done
    grep -m4 "\[fruit\] \[biarm\] \(place\|release\) profile:" "$OUT/shared_unset.log" \
        "$OUT/shared_zero.log" | sed 's/^/[p88]   /'
fi

if want accept10; then
    note "START $(date +%H:%M:%S) accept10 (the shipped scenario, 10 attempts)"
    RUN_LIMIT=1200 scripts/154_claim_run.sh "$OUT/accept10.driver" \
        ATTEMPTS=10 HEADLESS=1 FRUIT_MOTION_REPORT=1 \
        bash logs/p80/one_run.sh "$OUT/accept10.log" "$OUT/accept10.stamps"
    note "exit=$? $(date +%H:%M:%S) accept10"
    tail -4 "$OUT/accept10.log" | sed 's/^/[p88]   /'
fi

note "extra done $(date +%H:%M:%S)"
