#!/usr/bin/env bash
# P84 battery: the fail-fast A/B on the two-line (P83's registered re-entry).
#
#   bash logs/p84/run_p84.sh            # all four registered arms + the gates
#   bash logs/p84/run_p84.sh D5 F5      # named arms only
#
# Registered in `logs/p84/PREREG.md` (md5 in `logs/p84/PREREG.md5`, frozen before
# the first run). Every arm: HEADLESS=1, ATTEMPTS=20, the shipped two-line
# scenario (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`, its own supply package and
# pure routing left alone), the P80 instrumentation set
# (`FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1`) **plus** the tracker and the
# park trace on BOTH arms (`FRUIT_CARRY_DIAG=1 FRUIT_BIARM_PARK_TRACE=1`), one
# claim per run, wall stamped per line.
#
#   D5  seed 5  (set only)                    control, scheduler only  (= P80 T20)
#   F5  seed 5  FRUIT_FAIL_FAST=150            the lever
#   D6  seed 6  (set only)                    control, second seed     (= P80 T6)
#   F6  seed 6  FRUIT_FAIL_FAST=150            the lever, second seed
#
# The controls are re-run (the tree has moved since P80: P82's
# `bimanual.py` wake-on-request is the two-line's own path); G1 is the byte
# identity of their `[fruit]` streams against P80's T20/T6 modulo the
# `[fruit] [carry]` diag rows. Nothing here writes src/, configs/, datasets/ or
# a checkpoint, and no motion reference is written.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p84

OUT=logs/p84
BASE=(HEADLESS=1 ATTEMPTS=20)
INST=(FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1)
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1)
DIAG=(FRUIT_CARRY_DIAG=1 FRUIT_BIARM_PARK_TRACE=1)
REF20="logs/p80/motion_reference_twoline_p80_20.json"
FLOOR=0.5   # 20 attempts; P80's seed-6 branch is 10/20 = 50 % at its own reference

arms=${*:-D5 F5 D6 F6}

{
    echo "# P84 header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)  dirty=$(git status --porcelain | wc -l)"
    md5sum src/fruit_sorting/tasks.py src/fruit_sorting/bimanual.py \
        src/fruit_sorting/assets.py src/fruit_sorting/conveyor.py \
        src/fruit_sorting/scene.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/fruits.py src/fruit_sorting/control.py \
        configs/motion_reference.json configs/motion_reference_twoline.json \
        scripts/190_twoline_gate.sh scripts/105_motion_regression.py \
        scripts/186_w6_report.py scripts/175_twoline_report.py \
        scripts/accept.sh scripts/154_claim_run.sh scripts/selfcheck.sh \
        logs/p80/T20.log logs/p80/T6.log \
        logs/p80/motion_reference_twoline_p80_20.json \
        logs/p80/p80lib.py logs/p80/stamp.py \
        logs/p84/PREREG.md logs/p84/p84_report.py logs/p84/one_run.sh logs/p84/stamp.py
    echo "# arms: D5/D6 = ${TWO[*]} ${DIAG[*]}; F5/F6 = the same + FRUIT_FAIL_FAST=150"
    echo "# controls re-run: D=the scheduler only; G1 compares them to"
    echo "#   logs/p80/{T20,T6}.log modulo [fruit] [carry] rows"
    echo "# instrumentation: ${BASE[*]} ${INST[*]}"
    echo "# rails: shipped (FRUIT_OUTPUT_RAILS unset = none, P71); no supply/grade/"
    echo "# speed env - the two-line's own package is its shipped default"
} | tee "$OUT/header.txt"

fail=0
note() { echo "[p84] $*"; }

run_arm() {
    local name=$1 seed=$2 extra=$3
    note "START $(date +%H:%M:%S) $name (seed $seed) extra=[$extra]"
    # shellcheck disable=SC2086
    RUN_LIMIT=2400 scripts/154_claim_run.sh "$OUT/$name.driver" \
        "${BASE[@]}" SEED="$seed" "${INST[@]}" "${TWO[@]}" "${DIAG[@]}" $extra \
        bash "$OUT/one_run.sh" "$OUT/$name.log" "$OUT/$name.stamps" \
        > "$OUT/$name.driver.log" 2>&1
    local rc=$?
    note "exit=$rc $(date +%H:%M:%S) $name"
    if [ "$rc" -ne 0 ] || [ ! -s "$OUT/$name.log" ]; then
        note "FAIL $name rc=$rc (see $OUT/$name.driver.log)"
        fail=1
        return 1
    fi
    grep -E '\[biarm\] [0-9]+ pipelined|\[stats\]' "$OUT/$name.log" | tail -2 | sed 's/^/    /'
    note "$name trips: $(grep -c '\[fail-fast\]' "$OUT/$name.log")"
    return 0
}

for arm in $arms; do
    case "$arm" in
        D5) run_arm D5 5 "" || true ;;
        F5) run_arm F5 5 "FRUIT_FAIL_FAST=150" || true ;;
        D6) run_arm D6 6 "" || true ;;
        F6) run_arm F6 6 "FRUIT_FAIL_FAST=150" || true ;;
        *)  note "unknown arm $arm"; exit 2 ;;
    esac
done

# --------------------------------------------------------------------------- #
# The gates (only for the arms that exist)
# --------------------------------------------------------------------------- #
for tag in $arms; do
    [ -s "$OUT/$tag.log" ] || continue
    case "$tag" in
        D5|D6)
            note "190 (control: must PASS) $tag"
            TWOLINE_REF="$REF20" scripts/190_twoline_gate.sh -m "$FLOOR" "$OUT/$tag.log" \
                2>&1 | tee "$OUT/$tag.gate"
            rc=${PIPESTATUS[0]}
            note "190 $tag exit=$rc"
            [ "$rc" -ne 0 ] && fail=1
            ;;
        F5|F6)
            # The treatment is its OWN attractor (the abort re-times the
            # presentation, PREREG R0): record the fingerprint comparison, and
            # gate on the motion BUDGETS only.
            note "190 (recorded; DIFFERS is expected) $tag"
            TWOLINE_REF="$REF20" scripts/190_twoline_gate.sh -m "$FLOOR" "$OUT/$tag.log" \
                2>&1 | tee "$OUT/$tag.gate"
            note "190 $tag exit=${PIPESTATUS[0]} (recorded, not a gate)"
            note "105 budgets $tag"
            python3 scripts/105_motion_regression.py "$OUT/$tag.log" \
                --min-success-rate 0.0 2>&1 | tee "$OUT/$tag.budgets"
            note "105 $tag exit=${PIPESTATUS[0]} (budgets only)"
            ;;
    esac
done
# the controls' budgets too (a control that fails its budgets is not a control)
for tag in D5 D6; do
    [ -s "$OUT/$tag.log" ] || continue
    python3 scripts/105_motion_regression.py "$OUT/$tag.log" \
        --min-success-rate 0.0 --fingerprint "$REF20" 2>&1 | tail -6 | tee "$OUT/$tag.budgets"
done

# --------------------------------------------------------------------------- #
# The report, the offline self-check
# --------------------------------------------------------------------------- #
note "report"
python3 "$OUT/p84_report.py" 2>&1 | tee "$OUT/p84_report.txt"
note "report exit=${PIPESTATUS[0]}"
note "selfcheck"
scripts/selfcheck.sh 2>&1 | tee "$OUT/selfcheck.log"
note "selfcheck exit=${PIPESTATUS[0]}"
note "battery done $(date +%H:%M:%S) fail=$fail"
exit "$fail"
