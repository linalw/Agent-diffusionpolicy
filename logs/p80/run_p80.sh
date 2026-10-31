#!/usr/bin/env bash
# P80 battery: the cell's throughput on the shipped tree + the two throughput levers.
#
#   nohup bash logs/p80/run_p80.sh > logs/p80/battery_driver.log 2>&1 &
#
# PREREG: logs/p80/PREREG.md (md5 in logs/p80/PREREG.md5), pinned before any run.
#
# Arms (one `scripts/154_claim_run.sh` claim each, sequential, one simulator):
#   G-S10  the shipped acceptance, 10 attempts  -> 105 --fingerprint (must match 8952c320)
#   S20    the shipped single arm, 20 attempts, seed 5           (BASE)
#   T20    the two-line, 20 attempts, seed 5                     (BASE + two-line)
#   U20    the single arm on the P44 speed union, 20 attempts     (BASE + FRUIT_SPEED_ALL=1)
#   V20    the two-line on the union - only if logs/p80/licence.py licenses it
#   G-T10  the two-line, 10 attempts -> 190 against configs/motion_reference_twoline.json
#   S6/X6  the seed-6 pair for the arm whose interval moved most (logs/p80/pick_mover.py)
#
# Every 20-attempt arm carries the identical instrumentation set
# (FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1); the gate arms carry exactly the
# shipped instrumentation so the fingerprints stay comparable.
#
# Nothing here writes src/, configs/, datasets/ or a checkpoint. The two-line
# 20-attempt reference is written to logs/p80/ - the shipped
# configs/motion_reference_twoline.json (a 10-attempt record) is never touched.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p80

BASE=(HEADLESS=1 ATTEMPTS=20 SEED=5 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1)
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1)
SPEED=(FRUIT_SPEED_ALL=1)
PICK="scripts/run.sh scripts/20_pick_place.py"

{
    echo "# P80 header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)  dirty=$(git status --porcelain | wc -l)"
    md5sum src/fruit_sorting/tasks.py src/fruit_sorting/bimanual.py \
        src/fruit_sorting/assets.py src/fruit_sorting/conveyor.py \
        src/fruit_sorting/scene.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/fruits.py src/fruit_sorting/control.py \
        configs/motion_reference.json configs/motion_reference_twoline.json \
        scripts/186_w6_report.py scripts/190_twoline_gate.sh \
        scripts/105_motion_regression.py scripts/accept.sh scripts/154_claim_run.sh \
        logs/p80/PREREG.md logs/p80/p80lib.py logs/p80/one_run.sh logs/p80/stamp.py
    echo "# 20-attempt instrumentation: ${BASE[*]}"
    echo "# arms: S=(none) T=${TWO[*]} U=${SPEED[*]} V=both ; gate arms at 10 attempts"
    echo "# rails: shipped (FRUIT_OUTPUT_RAILS unset = none, P71); no supply/grade/knob env"
} | tee logs/p80/header.txt

fail=0
note() { echo "[p80] $*"; }

claim_run() {  # claim_run <tag> <limit> <env...>
    local tag=$1 limit=$2; shift 2
    local log="logs/p80/${tag}.log"
    note "START $(date +%H:%M:%S) $tag  $*"
    RUN_LIMIT="$limit" scripts/154_claim_run.sh "logs/p80/${tag}.driver" "$@" \
        bash logs/p80/one_run.sh "$log" "logs/p80/${tag}.stamps"
    local rc=$?
    note "exit=$rc $(date +%H:%M:%S) $tag"
    if [ "$rc" -ne 0 ] || [ ! -s "$log" ]; then
        note "FAIL $tag rc=$rc (see logs/p80/${tag}.driver)"
        fail=1
        return 1
    fi
    grep -E '\[stats\]|\[biarm\] [0-9]+ pipelined' "$log" | tail -2 | sed 's/^/    /'
    return 0
}

# --------------------------------------------------------------------------- #
# 1. the motion-gate arm (the shipped acceptance, 10 attempts)
# --------------------------------------------------------------------------- #
note "G-S10 start $(date +%H:%M:%S)"
RUN_LIMIT=1500 scripts/154_claim_run.sh logs/p80/S10.driver \
    SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p80/S10.log bash scripts/accept.sh
rc=$?
note "G-S10 exit=$rc $(date +%H:%M:%S)"
[ "$rc" -ne 0 ] && fail=1
python3 scripts/105_motion_regression.py logs/p80/S10.log \
    --fingerprint configs/motion_reference.json | tee logs/p80/S10.gate
note "G-S10 gate exit=${PIPESTATUS[0]} (fingerprint must read matches; the rate"
note "     floor is the standing 6/9 branch and fails rate-only - P71/P72 record)"

# --------------------------------------------------------------------------- #
# 2. the 20-attempt throughput arms
# --------------------------------------------------------------------------- #
claim_run S20 2400 "${BASE[@]}" || true
claim_run T20 2400 "${BASE[@]}" "${TWO[@]}" || true
claim_run U20 2400 "${BASE[@]}" "${SPEED[@]}" || true

# the union's licence (PREREG R2) - decides whether V is spent at all
if [ -s logs/p80/S20.log ] && [ -s logs/p80/U20.log ]; then
    note "R2 licence:"
    python3 logs/p80/licence.py > logs/p80/licence.out 2>&1
    licensed=$?
    cat logs/p80/licence.out | sed 's/^/    /'
    note "licence exit=$licensed"
else
    licensed=1
    note "licence: S20 or U20 missing -> V not spent"
fi
if [ "$licensed" -eq 0 ]; then
    claim_run V20 2400 "${BASE[@]}" "${TWO[@]}" "${SPEED[@]}" || true
else
    note "V20 not spent (PREREG R2)"
fi

# --------------------------------------------------------------------------- #
# 3. the two-line motion-gate arm (10 attempts, the shipped instrumentation)
# --------------------------------------------------------------------------- #
note "G-T10 start $(date +%H:%M:%S)"
RUN_LIMIT=1500 scripts/154_claim_run.sh logs/p80/T10.driver \
    HEADLESS=1 ATTEMPTS=10 SEED=5 FRUIT_MOTION_REPORT=1 "${TWO[@]}" \
    bash logs/p80/one_run.sh logs/p80/T10.log logs/p80/T10.stamps
rc=$?
note "G-T10 exit=$rc $(date +%H:%M:%S)"
[ "$rc" -ne 0 ] && fail=1
if [ -s logs/p80/T10.log ]; then
    scripts/190_twoline_gate.sh logs/p80/T10.log 2>&1 | tee logs/p80/T10.gate
    note "G-T10 gate exit=${PIPESTATUS[0]} (recorded, not forced)"
    # the 20-attempt two-line arm's OWN reference (20 != 10 descents, so the
    # shipped 10-attempt file cannot match) - written to logs/p80/, never to configs/
    python3 scripts/105_motion_regression.py logs/p80/T20.log \
        --min-success-rate 0.5 \
        --write-fingerprint logs/p80/motion_reference_twoline_p80_20.json \
        2>&1 | tee logs/p80/T20.reference
    note "T20 own reference: logs/p80/motion_reference_twoline_p80_20.json"
fi

# --------------------------------------------------------------------------- #
# 4. the seed-6 pair for the arm whose interval moved most (PREREG R3)
# --------------------------------------------------------------------------- #
if [ -s logs/p80/S20.log ]; then
    note "R3 mover:"
    python3 logs/p80/pick_mover.py | tee logs/p80/mover.txt
    mover=$(sed -n 's/.*-> seed-6 pair: S6 + \([A-Z]\)6.*/\1/p' logs/p80/mover.txt | tail -1)
    note "mover=$mover"
    if [ -n "${mover:-}" ]; then
        claim_run S6 2400 "${BASE[@]/SEED=5/SEED=6}" || true
        case "$mover" in
            T) claim_run T6 2400 "${BASE[@]/SEED=5/SEED=6}" "${TWO[@]}" || true ;;
            U) claim_run U6 2400 "${BASE[@]/SEED=5/SEED=6}" "${SPEED[@]}" || true ;;
            V) claim_run V6 2400 "${BASE[@]/SEED=5/SEED=6}" "${TWO[@]}" "${SPEED[@]}" || true ;;
            *) note "unknown mover '$mover' -> no seed-6 arm" ;;
        esac
    fi
else
    note "R3: S20 missing -> no seed-6 pair"
fi

# --------------------------------------------------------------------------- #
# 5. the report
# --------------------------------------------------------------------------- #
note "report"
python3 logs/p80/p80_report.py 2>&1 | tee logs/p80/p80_report.txt
note "report exit=${PIPESTATUS[0]}"
note "battery done $(date +%H:%M:%S) fail=$fail"
exit "$fail"
