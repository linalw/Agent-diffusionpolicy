#!/usr/bin/env bash
# P91 P8 - the inertness runs on the paths the two-line scope must not touch,
# plus the final tree's own replay.
#
#   bash logs/p91/run_p91_extra.sh            # all four, sequential
#   bash logs/p91/run_p91_extra.sh single     # the single-arm acceptance only
#   bash logs/p91/run_p91_extra.sh shared     # the shared-station pair only
#   bash logs/p91/run_p91_extra.sh n5         # the fresh unset replay
#
# `single`    `FRUIT_BIARM=0 scripts/accept.sh` (ten attempts, the pre-P85 single
#             arm) with `FRUIT_MOTION_REPORT=1`: the raw `[fruit]` stream must be
#             346/346 identical to `logs/p71/accept_rails_none.log` and the gate
#             must read `fingerprint: matches` `configs/motion_reference_single.json`.
#             No take-off row may print here (it prints only in a bimanual
#             session): that absence is the byte-identity proof.
# `shared`    the shared station (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0`), 4
#             attempts, env **unset** vs `FRUIT_DYNAMIC_PROBE_TICKS=60`: identical
#             on the `[fruit]` stream with the row's origin field dropped, and the
#             same clock (60 ticks) in both - the scope is `session.twoline`, and
#             the shared station is not it.
# `n5`        a fresh unset 20-attempt run on the **final** tree (the not-shipped
#             form): it must replay the pre-change record `logs/p89/T5.log`
#             (P8's second half) and its own phase control `C5`.
# `accept10`  the shipped scenario at ten attempts, the same tree, for the two
#             two-line-side motion references (only used if the gate passes).
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
OUT=logs/p91
mkdir -p "$OUT"
sel=("$@")
want() { [ "${#sel[@]}" -eq 0 ] || [[ " ${sel[*]} " == *" $1 "* ]]; }
note() { echo "[p91] $*"; }

if want single; then
    note "START $(date +%H:%M:%S) single-arm acceptance (FRUIT_BIARM=0)"
    ACCEPT_LOG="$OUT/single_accept.log" FRUIT_BIARM=0 SKIP_SELFCHECK=1 \
        scripts/accept.sh > "$OUT/single_accept.gate" 2>&1
    rc=$?
    note "exit=$rc $(date +%H:%M:%S) single-arm acceptance"
    tail -12 "$OUT/single_accept.gate" | sed 's/^/[p91]   /'
    python3 "$OUT/p91_report.py" --same-raw logs/p71/accept_rails_none.log \
        "$OUT/single_accept.log" 2>&1 | tee "$OUT/single_accept.same"
    for row in "release profile:" "place profile:" "lift profile:" "take-off profile:"; do
        echo "[p91]   '${row}' rows in the single-arm log: $(grep -c "$row" "$OUT/single_accept.log")"
    done
fi

if want shared; then
    for arm in unset zero; do
        envs=(HEADLESS=1 FRUIT_MOTION_REPORT=1 ATTEMPTS=4
              FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0)
        [ "$arm" = zero ] && envs+=(FRUIT_DYNAMIC_PROBE_TICKS=60)
        note "START $(date +%H:%M:%S) shared-$arm"
        RUN_LIMIT=900 scripts/154_claim_run.sh "$OUT/shared_$arm.driver" "${envs[@]}" \
            bash logs/p80/one_run.sh "$OUT/shared_$arm.log" "$OUT/shared_$arm.stamps"
        note "exit=$? $(date +%H:%M:%S) shared-$arm"
    done
    grep -m8 "\[fruit\] \[biarm\] \(take-off\|lift\|place\|release\) profile:" \
        "$OUT/shared_unset.log" "$OUT/shared_zero.log" | sed 's/^/[p91]   /'
fi

if want n5; then
    note "START $(date +%H:%M:%S) N5 (a fresh unset 20-attempt run, the final tree)"
    RUN_LIMIT=2400 scripts/154_claim_run.sh "$OUT/N5.driver" \
        HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 \
        FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1 ATTEMPTS=20 SEED=5 \
        bash logs/p80/one_run.sh "$OUT/N5.log" "$OUT/N5.stamps"
    note "exit=$? $(date +%H:%M:%S) N5"
    python3 "$OUT/p91_report.py" --profile "$OUT/N5.log" | sed 's/^/[p91]   /'
fi

if want accept10; then
    note "START $(date +%H:%M:%S) accept10 (the shipped scenario, 10 attempts)"
    RUN_LIMIT=1200 scripts/154_claim_run.sh "$OUT/accept10.driver" \
        ATTEMPTS=10 HEADLESS=1 FRUIT_MOTION_REPORT=1 \
        bash logs/p80/one_run.sh "$OUT/accept10.log" "$OUT/accept10.stamps"
    note "exit=$? $(date +%H:%M:%S) accept10"
    tail -4 "$OUT/accept10.log" | sed 's/^/[p91]   /'
fi

note "extra done $(date +%H:%M:%S)"
