#!/usr/bin/env bash
# W7-A chain: `FRUIT_BIARM_PARK_EARLY` now defaults ON for the two-line session
# (the W6-C park-gate lever promoted; `_dynamic_profile(..., "0", "1")`), so
# re-record the two-line scenario of record and re-verify the no-harm.
#
#   nohup bash scripts/189_w7a_chain.sh > logs/w7/00_driver.log 2>&1 &
#
# Runs, in order (Tier A solo, one simulator at a time via 154_claim_run.sh):
#   10/11  dense two-line wave-sheet re-record (seed 5, 10 attempts) x2 - the
#          W3/W4 dense scenario; the second run is the determinism check
#   20/21  W6-B patch battery with the lever default-on (seed 5, 20 attempts)
#          x2; config-identical to logs/w6/31_lever_park_1.log (which set the
#          env explicitly) so the physics stream is the controlled replay
#   30     single-arm no-harm (patch sheet + balanced mix) on the new tree;
#          compare against the W6-C single record (logs/w6/20_single_noharm.log)
#   offline: selfcheck + supply selftest, determinism/no-harm compares, the
#          two-line fingerprint write + check (configs/motion_reference_twoline.json;
#          the single-arm configs/motion_reference.json is untouched), the W6
#          throughput report on the patch pair, and the acceptance
#          (ACCEPT_LOG=logs/w7/50_accept_w7a.log; expect 9/10 + fingerprint match).
#
# Outputs are pinned in logs/w7/A_RESULTS.md.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/w7

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
    echo "[w7a] START $(date +%H:%M:%S) $log $*"
    RUN_LIMIT="$limit" scripts/154_claim_run.sh "$log" "${BASE[@]}" "$@" \
        scripts/run.sh scripts/20_pick_place.py
    code=$?
    echo "[w7a] exit=$code $(date +%H:%M:%S) $log"
    check_log "$log" "$code"
}

echo "[w7a] chain start $(date +%H:%M:%S) tasks.py md5 $(md5sum src/fruit_sorting/tasks.py | cut -d' ' -f1)"

# --- offline pre-flight ---------------------------------------------------- #
echo "[w7a] selfcheck $(date +%H:%M:%S)"
scripts/selfcheck.sh > logs/w7/01_selfcheck.log 2>&1
sc=$?
tail -3 logs/w7/01_selfcheck.log
[ "$sc" -eq 0 ] || { echo "[w7a] FAIL: selfcheck exit=$sc"; status=1; }

echo "[w7a] supply selftest $(date +%H:%M:%S)"
python3 scripts/172_supply_selftest.py > logs/w7/02_supply_selftest.log 2>&1
ss=$?
tail -1 logs/w7/02_supply_selftest.log
[ "$ss" -eq 0 ] || { echo "[w7a] FAIL: supply selftest exit=$ss"; status=1; }

# --- the dense two-line re-record (the W3/W4 scenario) --------------------- #
run logs/w7/10_dense_twoline_1.log 3600 "${TWO[@]}" ATTEMPTS=10
run logs/w7/11_dense_twoline_2.log 3600 "${TWO[@]}" ATTEMPTS=10

# --- the W6-B patch battery with the lever default-on ---------------------- #
run logs/w7/20_patch_battery_1.log 7200 "${TWO[@]}" "${PATCH[@]}" "${MIX[@]}" ATTEMPTS=20
run logs/w7/21_patch_battery_2.log 7200 "${TWO[@]}" "${PATCH[@]}" "${MIX[@]}" ATTEMPTS=20

# --- the single-arm no-harm (same W6-C scenario) --------------------------- #
run logs/w7/30_single_noharm.log 5400 FRUIT_BIARM=0 "${PATCH[@]}" "${MIX[@]}" ATTEMPTS=20

# --- headline numbers for the record --------------------------------------- #
grep -E "\[stats\]|\[biarm\]" logs/w7/10_dense_twoline_1.log logs/w7/11_dense_twoline_2.log \
    > logs/w7/12_dense_stats.txt 2>&1 || true
grep -E "\[stats\]|\[biarm\]" logs/w7/20_patch_battery_1.log logs/w7/21_patch_battery_2.log \
    > logs/w7/22_patch_stats.txt 2>&1 || true
grep -E "\[stats\]|\[run\] summary" logs/w7/30_single_noharm.log \
    > logs/w7/31_single_stats.txt 2>&1 || true
cat logs/w7/12_dense_stats.txt logs/w7/22_patch_stats.txt logs/w7/31_single_stats.txt

# --- determinism + no-harm compares ---------------------------------------- #
: > logs/w7/40_compare.txt
compare() {  # compare <left> <right> [extra args...]
    local left=$1 right=$2
    shift 2
    {
        echo "== $left vs $right $*"
        python3 logs/w4/compare_streams.py "$@" "$left" "$right"
        echo "exit=$?"
    } | tee -a logs/w7/40_compare.txt
}

compare logs/w7/10_dense_twoline_1.log logs/w7/11_dense_twoline_2.log
compare logs/w7/20_patch_battery_1.log logs/w7/21_patch_battery_2.log
compare logs/w7/20_patch_battery_1.log logs/w6/31_lever_park_1.log
compare logs/w7/20_patch_battery_1.log logs/w6/32_lever_park_2_trace.log
compare logs/w7/30_single_noharm.log logs/w6/20_single_noharm.log --physics-only
compare logs/w7/30_single_noharm.log logs/w6/20_single_noharm.log
compare logs/w7/10_dense_twoline_1.log logs/w4/20_dense_repeat.log --physics-only

# --- the two-line fingerprint (the single-arm reference is preserved) ------ #
: > logs/w7/42_fingerprint.txt
if [ -s logs/w7/10_dense_twoline_1.log ]; then
    {
        echo "== write: logs/w7/10_dense_twoline_1.log -> configs/motion_reference_twoline.json"
        python3 scripts/105_motion_regression.py logs/w7/10_dense_twoline_1.log \
            --write-fingerprint configs/motion_reference_twoline.json
        echo "write exit=$?"
        echo "== check: logs/w7/11_dense_twoline_2.log against the written fingerprint"
        python3 scripts/105_motion_regression.py logs/w7/11_dense_twoline_2.log \
            --fingerprint configs/motion_reference_twoline.json
        echo "check exit=$?"
        echo "== sanity: the single-arm reference is byte-untouched (b9e72ca7..., pinned in 43/44_tree_md5_*.txt)"
        md5sum configs/motion_reference.json
    } | tee -a logs/w7/42_fingerprint.txt
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
echo "[w7a] acceptance $(date +%H:%M:%S)"
RUN_LIMIT=1800 scripts/154_claim_run.sh logs/w7/51_accept_w7a_full.log \
    ACCEPT_LOG=logs/w7/50_accept_w7a.log scripts/accept.sh
acc=$?
echo "[w7a] acceptance exit=$acc"
tail -8 logs/w7/51_accept_w7a_full.log 2>/dev/null || true
[ "$acc" -eq 0 ] || { echo "[w7a] FAIL: acceptance exit=$acc"; status=1; }

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
