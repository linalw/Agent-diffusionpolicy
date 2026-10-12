#!/usr/bin/env bash
# W7-A chain: `FRUIT_BIARM_PARK_EARLY` now defaults ON for the two-line session
# (the W6-C park-gate lever promoted; `_dynamic_profile(..., "0", "1")`), so
# re-record the two-line scenario of record and re-verify the no-harm.
#
#   nohup bash scripts/189_w7a_chain.sh > logs/w7/00_driver.log 2>&1 &
#
# Modes:
#   * full (default): pre-flight, the simulator runs, then the offline evidence.
#   * `W7A_OFFLINE=1`: skip the pre-flight and the simulator runs and re-assert
#     the offline evidence from the logs already on disk (the compares, the
#     fingerprint write/check, the floor-override re-check, the two-line gate,
#     the report). Every assertion below fails the run on a bad compare or a
#     missing/wrong fingerprint, so this mode is the cheap re-verification.
#
# Runs, in order (Tier A solo, one simulator at a time via 154_claim_run.sh):
#   10/11  dense two-line wave-sheet re-record (seed 5, 10 attempts) x2 - the
#          W3/W4 dense scenario; the second run is the determinism check
#   15     the attribution control: the same dense run with the flip explicitly
#          off (`FRUIT_BIARM_PARK_EARLY=0`); it must replay the pre-W7 record
#          logs/w4/20_dense_repeat.log bit-for-bit (physics stream), so the
#          default flip is the only cause of 10/11's moved branch
#   20/21  W6-B patch battery with the lever default-on (seed 5, 20 attempts)
#          x2; config-identical to logs/w6/31_lever_park_1.log (which set the
#          env explicitly) so the physics stream is the controlled replay
#   30     single-arm no-harm (patch sheet + balanced mix) on the new tree;
#          compare against the W6-C single record (logs/w6/20_single_noharm.log)
#   offline: selfcheck + supply selftest, determinism/no-harm compares (all
#          asserted IDENTICAL except the expected-DIFFERENT moved branch), the
#          two-line fingerprint write + check + the explicit floor-override
#          re-check + the 190 two-line gate (configs/motion_reference_twoline.json;
#          the single-arm configs/motion_reference.json is untouched), the W6
#          throughput report on the patch pair, and the acceptance
#          (ACCEPT_LOG=logs/w7/50_accept_w7a.log; expect 9/10 + fingerprint match)
#          whose stream is compared (asserted IDENTICAL) against W6-C and W4.
#
# Outputs are pinned in logs/w7/A_RESULTS.md.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/w7

OFFLINE=${W7A_OFFLINE:-0}

md5sum src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
    src/fruit_sorting/fruits.py configs/motion_reference.json \
    scripts/186_w6_report.py scripts/105_motion_regression.py \
    logs/w4/compare_streams.py \
    > logs/w7/43_tree_md5_before.txt

BASE=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 SEED=5)
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1)
PATCH=(FRUIT_SUPPLY_PATCH=1)
MIX=(FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25)

status=0

check_log() {  # check_log <log> <exit-code>
    local log=$1 code=$2
    if [ "$code" -ne 0 ]; then
        echo "[w7a] FAIL: exit=$code log=$log"
        status=1
        return 1
    fi
    if [ ! -s "$log" ]; then
        echo "[w7a] FAIL: missing or empty log=$log (exit=0 but no output)"
        status=1
        return 1
    fi
    echo "[w7a] ok: exit=0 log=$log"
    return 0
}

run() {  # run <log> <run-limit-s> <env...>
    local log=$1 limit=$2 code
    shift 2
    if [ "$OFFLINE" = 1 ]; then
        if [ ! -s "$log" ]; then
            echo "[w7a] FAIL: W7A_OFFLINE=1 but log missing: $log"
            status=1
        else
            echo "[w7a] offline: reusing log=$log"
        fi
        return 0
    fi
    echo "[w7a] START $(date +%H:%M:%S) $log $*"
    RUN_LIMIT="$limit" scripts/154_claim_run.sh "$log" "${BASE[@]}" "$@" \
        scripts/run.sh scripts/20_pick_place.py
    code=$?
    echo "[w7a] exit=$code $(date +%H:%M:%S) $log"
    check_log "$log" "$code"
}

echo "[w7a] chain start $(date +%H:%M:%S) tasks.py md5 $(md5sum src/fruit_sorting/tasks.py | cut -d' ' -f1)"
[ "$OFFLINE" = 1 ] && echo "[w7a] W7A_OFFLINE=1: simulator runs and the acceptance are skipped; evidence is re-asserted on the existing logs"

# --- offline pre-flight ---------------------------------------------------- #
echo "[w7a] selfcheck $(date +%H:%M:%S)"
if [ "$OFFLINE" = 1 ]; then
    scripts/selfcheck.sh > logs/w7/01_selfcheck_offline.log 2>&1
    sc_log=logs/w7/01_selfcheck_offline.log
else
    scripts/selfcheck.sh > logs/w7/01_selfcheck.log 2>&1
    sc_log=logs/w7/01_selfcheck.log
fi
sc=$?
tail -3 "$sc_log"
[ "$sc" -eq 0 ] || { echo "[w7a] FAIL: selfcheck exit=$sc"; status=1; }

echo "[w7a] supply selftest $(date +%H:%M:%S)"
if [ "$OFFLINE" = 1 ]; then
    python3 scripts/172_supply_selftest.py > logs/w7/02_supply_selftest_offline.log 2>&1
    ss_log=logs/w7/02_supply_selftest_offline.log
else
    python3 scripts/172_supply_selftest.py > logs/w7/02_supply_selftest.log 2>&1
    ss_log=logs/w7/02_supply_selftest.log
fi
ss=$?
tail -1 "$ss_log"
[ "$ss" -eq 0 ] || { echo "[w7a] FAIL: supply selftest exit=$ss"; status=1; }

# --- the dense two-line re-record (the W3/W4 scenario) --------------------- #
run logs/w7/10_dense_twoline_1.log 3600 "${TWO[@]}" ATTEMPTS=10
run logs/w7/11_dense_twoline_2.log 3600 "${TWO[@]}" ATTEMPTS=10

# --- the attribution control (the same scenario with the flip off) --------- #
run logs/w7/15_dense_control_park_off.log 3600 "${TWO[@]}" \
    FRUIT_BIARM_PARK_EARLY=0 ATTEMPTS=10

# --- the W6-B patch battery with the lever default-on ---------------------- #
run logs/w7/20_patch_battery_1.log 7200 "${TWO[@]}" "${PATCH[@]}" "${MIX[@]}" ATTEMPTS=20
run logs/w7/21_patch_battery_2.log 7200 "${TWO[@]}" "${PATCH[@]}" "${MIX[@]}" ATTEMPTS=20

# --- the single-arm no-harm (same W6-C scenario) --------------------------- #
run logs/w7/30_single_noharm.log 5400 FRUIT_BIARM=0 "${PATCH[@]}" "${MIX[@]}" ATTEMPTS=20

# --- headline numbers for the record --------------------------------------- #
grep -E "\[stats\]|\[biarm\]" logs/w7/10_dense_twoline_1.log logs/w7/11_dense_twoline_2.log \
    logs/w7/15_dense_control_park_off.log \
    > logs/w7/12_dense_stats.txt 2>&1 || true
grep -E "\[stats\]|\[biarm\]" logs/w7/20_patch_battery_1.log logs/w7/21_patch_battery_2.log \
    > logs/w7/22_patch_stats.txt 2>&1 || true
grep -E "\[stats\]|\[run\] summary" logs/w7/30_single_noharm.log \
    > logs/w7/31_single_stats.txt 2>&1 || true
cat logs/w7/12_dense_stats.txt logs/w7/22_patch_stats.txt logs/w7/31_single_stats.txt

# --- determinism + no-harm compares (asserted, never pass-through) ---------- #
: > logs/w7/40_compare.txt
compare() {  # compare <want: IDENTICAL|DIFFERENT> <left> <right> [--physics-only] [--pattern REGEX]
    local want=$1 left=$2 right=$3
    shift 3
    local pattern="" args=() out code got
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --pattern) pattern=$2; shift 2 ;;
            *) args+=("$1"); shift ;;
        esac
    done
    out=$(python3 logs/w4/compare_streams.py "${args[@]}" "$left" "$right" 2>&1)
    code=$?
    {
        echo "== $left vs $right ${args[*]:-}"
        printf '%s\n' "$out"
        echo "exit=$code"
    } | tee -a logs/w7/40_compare.txt
    got=$([ "$code" -eq 0 ] && echo IDENTICAL || echo DIFFERENT)
    if [ "$want" != "$got" ]; then
        echo "[w7a] FAIL: compare $left vs $right: expected $want, got $got"
        status=1
    elif [ -n "$pattern" ] && ! grep -Eq "$pattern" <<<"$out"; then
        echo "[w7a] FAIL: compare $left vs $right: first difference does not match /$pattern/"
        status=1
    fi
}

# The attribution control: with the flip explicitly off the pre-W7 record must
# replay bit-for-bit, so the default flip is the only cause of the moved branch.
compare IDENTICAL logs/w7/15_dense_control_park_off.log logs/w4/20_dense_repeat.log --physics-only
compare IDENTICAL logs/w7/15_dense_control_park_off.log logs/w4/20_dense_repeat.log
compare IDENTICAL logs/w7/10_dense_twoline_1.log logs/w7/11_dense_twoline_2.log
compare IDENTICAL logs/w7/20_patch_battery_1.log logs/w7/21_patch_battery_2.log
compare IDENTICAL logs/w7/20_patch_battery_1.log logs/w6/31_lever_park_1.log
compare IDENTICAL logs/w7/20_patch_battery_1.log logs/w6/32_lever_park_2_trace.log
compare IDENTICAL logs/w7/30_single_noharm.log logs/w6/20_single_noharm.log --physics-only
compare IDENTICAL logs/w7/30_single_noharm.log logs/w6/20_single_noharm.log
# The moved branch is expected: the gates open at payload-clear, first
# divergence at the left station acquisition (t=30.4 vs t=31.4).
compare DIFFERENT logs/w7/10_dense_twoline_1.log logs/w4/20_dense_repeat.log \
    --physics-only --pattern 'station acquired at t=30\.4'

# --- the two-line fingerprint (the single-arm reference is preserved) ------ #
: > logs/w7/42_fingerprint.txt
if [ -s logs/w7/10_dense_twoline_1.log ]; then
    fp=configs/motion_reference_twoline.json
    out=$(python3 scripts/105_motion_regression.py logs/w7/10_dense_twoline_1.log \
        --write-fingerprint "$fp" 2>&1)
    code=$?
    {
        echo "== write: logs/w7/10_dense_twoline_1.log -> $fp"
        printf '%s\n' "$out"
        echo "write exit=$code"
    } | tee -a logs/w7/42_fingerprint.txt
    # The write must have produced the reference; a rate-only failure (the
    # single-arm 0.75 floor meeting a two-line log) does not block it, a motion
    # budget failure does (105 refuses).
    if ! grep -q "^  wrote fingerprint -> $fp$" logs/w7/42_fingerprint.txt; then
        echo "[w7a] FAIL: the fingerprint was not written (105 refused or the log is unusable)"
        status=1
    fi
    if grep -qE "^  - (descent|carry|refusing) " logs/w7/42_fingerprint.txt; then
        echo "[w7a] FAIL: 105 reports a motion-budget failure in the write run"
        status=1
    fi
    # Pin the newly written reference before anything else reads it.
    {
        echo "== pin: md5 of the written two-line reference"
        md5sum "$fp"
        python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$fp" \
            && echo "  (valid JSON)"
    } | tee -a logs/w7/42_fingerprint.txt
    if [ ! -s "$fp" ]; then
        echo "[w7a] FAIL: $fp missing or empty after the write"
        status=1
    fi

    out=$(python3 scripts/105_motion_regression.py logs/w7/11_dense_twoline_2.log \
        --fingerprint "$fp" 2>&1)
    code=$?
    {
        echo "== check: logs/w7/11_dense_twoline_2.log against the written fingerprint"
        printf '%s\n' "$out"
        echo "check exit=$code"
    } | tee -a logs/w7/42_fingerprint.txt
    if ! grep -q "^  fingerprint: matches $fp$" logs/w7/42_fingerprint.txt; then
        echo "[w7a] FAIL: the determinism twin does not match the written fingerprint"
        status=1
    fi

    echo "== sanity: the single-arm reference is byte-untouched (b9e72ca7..., pinned in 43/44_tree_md5_*.txt)" \
        | tee -a logs/w7/42_fingerprint.txt
    md5sum configs/motion_reference.json | tee -a logs/w7/42_fingerprint.txt

    out=$(python3 scripts/105_motion_regression.py logs/w7/11_dense_twoline_2.log \
        --fingerprint "$fp" --min-success-rate 0.5 2>&1)
    code=$?
    {
        echo "== floor-override re-check (the 105 dynamic 0.75 floor is the single-arm calibration;"
        echo "   the two-line is a different scenario and its rate bar is not 0.75 - see A_RESULTS)"
        printf '%s\n' "$out"
        echo "floor-override check exit=$code"
    } | tee -a logs/w7/42_fingerprint.txt
    if [ "$code" -ne 0 ] || ! grep -q "^  fingerprint: matches $fp$" <<<"$out"; then
        echo "[w7a] FAIL: the floor-override re-check did not pass with a matching fingerprint"
        status=1
    fi

    # The formal two-line gate (the scenario pin + the explicit two-line floor).
    scripts/190_twoline_gate.sh logs/w7/10_dense_twoline_1.log logs/w7/11_dense_twoline_2.log \
        > logs/w7/45_twoline_gate.txt 2>&1
    gt=$?
    tail -2 logs/w7/45_twoline_gate.txt
    echo "[w7a] two-line gate (190) exit=$gt"
    [ "$gt" -eq 0 ] || { echo "[w7a] FAIL: 190_twoline_gate.sh exit=$gt"; status=1; }
else
    echo "[w7a] FAIL: no dense log, fingerprint not written" | tee -a logs/w7/42_fingerprint.txt
    status=1
fi

# --- the W6 throughput report on the patch pair ---------------------------- #
python3 scripts/186_w6_report.py --label w7a-patch \
    logs/w7/20_patch_battery_1.log logs/w7/21_patch_battery_2.log \
    logs/w7/30_single_noharm.log | tee logs/w7/41_w7_report.txt
rp=$?
echo "[w7a] report exit=$rp"
[ "$rp" -eq 0 ] || status=1

# --- the acceptance (selfcheck + 9/10 + the single-arm fingerprint) -------- #
if [ "$OFFLINE" = 1 ]; then
    [ -s logs/w7/50_accept_w7a.log ] || {
        echo "[w7a] FAIL: W7A_OFFLINE=1 but the acceptance log is missing"
        status=1
    }
    echo "[w7a] offline: reusing logs/w7/50_accept_w7a.log"
else
    echo "[w7a] acceptance $(date +%H:%M:%S)"
    RUN_LIMIT=1800 scripts/154_claim_run.sh logs/w7/51_accept_w7a_full.log \
        ACCEPT_LOG=logs/w7/50_accept_w7a.log scripts/accept.sh
    acc=$?
    echo "[w7a] acceptance exit=$acc"
    tail -8 logs/w7/51_accept_w7a_full.log 2>/dev/null || true
    [ "$acc" -eq 0 ] || { echo "[w7a] FAIL: acceptance exit=$acc"; status=1; }
fi

# The acceptance stream is the strongest single-arm no-harm proof; assert it.
if [ -s logs/w7/50_accept_w7a.log ]; then
    compare IDENTICAL logs/w7/50_accept_w7a.log logs/w6/60_accept_w6c.log --physics-only
    compare IDENTICAL logs/w7/50_accept_w7a.log logs/w6/60_accept_w6c.log
    compare IDENTICAL logs/w7/50_accept_w7a.log logs/w4/70_accept_w4_tree.log --physics-only
else
    echo "[w7a] FAIL: no acceptance log to compare"
    status=1
fi

# --- tree no-change check --------------------------------------------------- #
md5sum src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
    src/fruit_sorting/fruits.py configs/motion_reference.json \
    scripts/186_w6_report.py scripts/105_motion_regression.py \
    logs/w4/compare_streams.py \
    > logs/w7/44_tree_md5_after.txt
if ! diff -q logs/w7/43_tree_md5_before.txt logs/w7/44_tree_md5_after.txt >/dev/null; then
    echo "[w7a] WARNING: the pinned tree changed while the battery ran"
    diff logs/w7/43_tree_md5_before.txt logs/w7/44_tree_md5_after.txt
    status=1
fi

echo "[w7a] chain done $(date +%H:%M:%S) status=$status"
exit "$status"
