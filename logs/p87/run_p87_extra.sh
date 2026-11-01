#!/usr/bin/env bash
# P87 G2 - the inertness runs on the paths the two-line scope must not touch.
#
#   bash logs/p87/run_p87_extra.sh            # both, sequential
#   bash logs/p87/run_p87_extra.sh single     # the single-arm acceptance only
#   bash logs/p87/run_p87_extra.sh shared     # the shared-station pair only
#
# `single`  `FRUIT_BIARM=0 scripts/accept.sh` (ten attempts, the pre-P85 single
#           arm) with `FRUIT_MOTION_REPORT=1`: the raw `[fruit]` stream must be
#           346/346 identical to `logs/p71/accept_rails_none.log` and the gate
#           must read `fingerprint: matches` `configs/motion_reference_single.json`.
#           The P87 row must be **absent** here (it prints only in a bimanual
#           session): that absence is the byte-identity proof, not a caveat.
# `shared`  the shared station (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0`), 4
#           attempts, env **unset** vs `FRUIT_SPEED_RELEASE=0`: the whole
#           `[fruit]` stream must be identical (no filter at all) and both must
#           print the shipped `dwell=20 pad_hold=3 finger_hold=3`.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
OUT=logs/p87
mkdir -p "$OUT"
sel=("$@")
want() { [ "${#sel[@]}" -eq 0 ] || [[ " ${sel[*]} " == *" $1 "* ]]; }
note() { echo "[p87] $*"; }

if want single; then
    note "START $(date +%H:%M:%S) single-arm acceptance (FRUIT_BIARM=0)"
    ACCEPT_LOG="$OUT/single_accept.log" FRUIT_BIARM=0 SKIP_SELFCHECK=1 \
        scripts/accept.sh > "$OUT/single_accept.gate" 2>&1
    note "exit=$? $(date +%H:%M:%S) single-arm acceptance"
    tail -12 "$OUT/single_accept.gate" | sed 's/^/[p87]   /'
    python3 "$OUT/p87_report.py" --same-raw logs/p71/accept_rails_none.log \
        "$OUT/single_accept.log" 2>&1 | tee "$OUT/single_accept.same"
    grep -c "\[fruit\] \[biarm\] release profile:" "$OUT/single_accept.log" \
        | sed 's/^/[p87]   release-profile rows in the single-arm log: /'
fi

if want shared; then
    for arm in unset zero; do
        envs=(HEADLESS=1 FRUIT_MOTION_REPORT=1 ATTEMPTS=4
              FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0)
        [ "$arm" = zero ] && envs+=(FRUIT_SPEED_RELEASE=0)
        note "START $(date +%H:%M:%S) shared-$arm"
        RUN_LIMIT=900 scripts/154_claim_run.sh "$OUT/shared_$arm.driver" "${envs[@]}" \
            bash logs/p80/one_run.sh "$OUT/shared_$arm.log" "$OUT/shared_$arm.stamps"
        note "exit=$? $(date +%H:%M:%S) shared-$arm"
    done
    grep -m2 "\[fruit\] \[biarm\] release profile:" "$OUT/shared_unset.log" \
        "$OUT/shared_zero.log" | sed 's/^/[p87]   /'
fi

note "extra done $(date +%H:%M:%S)"
