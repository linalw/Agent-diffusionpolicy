#!/usr/bin/env bash
# P81 battery: the two-line's scheduler on the single arm's shipped supply.
#
#   nohup bash logs/p81/run_p81.sh > logs/p81/battery_driver.log 2>&1 &
#
# PREREG: logs/p81/PREREG.md (md5 in logs/p81/PREREG.md5), pinned before any run.
#
# Arms (one scripts/154_claim_run.sh claim each, sequential, one simulator):
#   Tp5  the two-line scheduler + routing on the shipped scattered supply,
#        package DISABLED (FRUIT_SUPPLY_WAVE=0 -> 50/30/20 from the code default),
#        20 attempts, seed 5
#   Tp6  the same, seed 6
#   accept  the shipped acceptance (10 attempts) - the branch/no-harm probe
#
# Controls are P80's records on the identical tree md5s (logs/p80/S20,S6,T20,T6);
# they are NOT re-run (PREREG section 1).
#
# Nothing here writes src/, configs/, datasets/ or a checkpoint. No motion
# reference is written: Tp is a different scenario from P80's 20-attempt
# reference (different supply), so `190` records the expected DIFFER and the
# budgets are judged separately by 105.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p81

BASE=(HEADLESS=1 ATTEMPTS=20 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1)
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1)
PKG_OFF=(FRUIT_SUPPLY_WAVE=0)
PICK="scripts/run.sh scripts/20_pick_place.py"
REF20="logs/p80/motion_reference_twoline_p80_20.json"

{
    echo "# P81 header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)  dirty=$(git status --porcelain | wc -l)"
    md5sum src/fruit_sorting/tasks.py src/fruit_sorting/bimanual.py \
        src/fruit_sorting/assets.py src/fruit_sorting/conveyor.py \
        src/fruit_sorting/scene.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/fruits.py src/fruit_sorting/control.py \
        configs/motion_reference.json configs/motion_reference_twoline.json \
        scripts/186_w6_report.py scripts/175_twoline_report.py \
        scripts/190_twoline_gate.sh scripts/105_motion_regression.py \
        scripts/accept.sh scripts/154_claim_run.sh scripts/selfcheck.sh \
        logs/p80/S20.log logs/p80/T20.log logs/p80/S6.log logs/p80/T6.log \
        logs/p80/motion_reference_twoline_p80_20.json \
        logs/p80/p80lib.py logs/p80/stamp.py \
        logs/p81/PREREG.md logs/p81/p81_report.py logs/p81/one_run.sh \
        logs/p81/stamp.py
    echo "# arms: Tp5/Tp6 = ${TWO[*]} ${PKG_OFF[*]} at 20 attempts, seeds 5/6"
    echo "# controls (read, not re-run): logs/p80/{S20,T20,S6,T6}.log"
    echo "# instrumentation: ${BASE[*]}"
    echo "# rails: shipped (FRUIT_OUTPUT_RAILS unset = none, P71); no patch/bed/"
    echo "# grades env - the 50/30/20 must come from the code default (PREREG F1)"
} | tee logs/p81/header.txt

fail=0
note() { echo "[p81] $*"; }

claim_run() {  # claim_run <tag> <limit> <env...>
    local tag=$1 limit=$2; shift 2
    local log="logs/p81/${tag}.log"
    note "START $(date +%H:%M:%S) $tag  $*"
    RUN_LIMIT="$limit" scripts/154_claim_run.sh "logs/p81/${tag}.driver" "$@" \
        bash logs/p81/one_run.sh "$log" "logs/p81/${tag}.stamps"
    local rc=$?
    note "exit=$rc $(date +%H:%M:%S) $tag"
    if [ "$rc" -ne 0 ] || [ ! -s "$log" ]; then
        note "FAIL $tag rc=$rc (see logs/p81/${tag}.driver)"
        fail=1
        return 1
    fi
    grep -E '\[stats\]|\[biarm\] [0-9]+ pipelined' "$log" | tail -2 | sed 's/^/    /'
    return 0
}

# --------------------------------------------------------------------------- #
# 1. the two arms (PREREG section 1)
# --------------------------------------------------------------------------- #
claim_run Tp5 2400 "${BASE[@]}" SEED=5 "${TWO[@]}" "${PKG_OFF[@]}" || true
claim_run Tp6 2400 "${BASE[@]}" SEED=6 "${TWO[@]}" "${PKG_OFF[@]}" || true

# --------------------------------------------------------------------------- #
# 2. the package-off proof (PREREG E0 / F1) - before any interpretation
# --------------------------------------------------------------------------- #
note "supply proof"
{
    for tag in Tp5 Tp6; do
        echo "-- $tag"
        grep -h "\[supply\]" "logs/p81/${tag}.log" | grep "wave=" || echo "MISSING [supply] row"
        n=$(grep -c "A:0.375" "logs/p81/${tag}.log" || true)
        echo "A:0.375 rows: ${n:-0}"
        grep -q "wave=off" "logs/p81/${tag}.log" \
            && echo "wave=off: yes" || echo "wave=off: NO"
        grep -q "grades=A:0.5,B:0.3,C:0.2" "logs/p81/${tag}.log" \
            && echo "shipped 50/30/20: yes" || echo "shipped 50/30/20: NO"
    done
} | tee logs/p81/supply_proof.txt

# --------------------------------------------------------------------------- #
# 3. the motion budgets (105, no fingerprint, no rate floor) and the recorded
#    190 comparison against P80's 20-attempt reference (expected DIFFER)
# --------------------------------------------------------------------------- #
for tag in Tp5 Tp6; do
    [ -s "logs/p81/${tag}.log" ] || continue
    note "105 budgets $tag"
    python3 scripts/105_motion_regression.py "logs/p81/${tag}.log" \
        --min-success-rate 0.0 2>&1 | tee "logs/p81/${tag}.budgets"
    note "105 $tag exit=${PIPESTATUS[0]} (budgets only; the rate is reported)"
    note "190 (recorded) $tag"
    TWOLINE_REF="$REF20" scripts/190_twoline_gate.sh -m 0.60 "logs/p81/${tag}.log" \
        2>&1 | tee "logs/p81/${tag}.gate"
    note "190 $tag exit=${PIPESTATUS[0]} (DIFFERS is expected: different supply)"
done

# --------------------------------------------------------------------------- #
# 4. the branch / no-harm probe (the tree is unchanged; P80's G-S10 replay)
# --------------------------------------------------------------------------- #
note "accept probe start $(date +%H:%M:%S)"
RUN_LIMIT=1500 scripts/154_claim_run.sh logs/p81/accept.driver \
    SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p81/accept_noharm.log bash scripts/accept.sh
rc=$?
note "accept probe exit=$rc (the standing rate-only FAIL is expected at 6/9)"
python3 scripts/105_motion_regression.py logs/p81/accept_noharm.log \
    --fingerprint configs/motion_reference.json 2>&1 | tee logs/p81/accept.gate
note "accept gate exit=${PIPESTATUS[0]} (fingerprint must read matches)"

# --------------------------------------------------------------------------- #
# 5. the report and the offline self-check
# --------------------------------------------------------------------------- #
note "report"
python3 logs/p81/p81_report.py 2>&1 | tee logs/p81/p81_report.txt
note "report exit=${PIPESTATUS[0]}"
note "selfcheck"
scripts/selfcheck.sh 2>&1 | tee logs/p81/selfcheck.log
note "selfcheck exit=${PIPESTATUS[0]}"
note "battery done $(date +%H:%M:%S) fail=$fail"
exit "$fail"
