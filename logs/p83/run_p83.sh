#!/usr/bin/env bash
# P83 battery: the fail-fast A/B on the shipped scripted scenario.
#
#   bash logs/p83/run_p83.sh            # all five registered arms
#   bash logs/p83/run_p83.sh F5 F6      # named arms only
#
# Registered in `logs/p83/PREREG.md` §2 (md5 `1e1e6345…`, frozen before the first
# run). Every arm: HEADLESS=1, ATTEMPTS=20, the shipped scenario (no
# supply/grade/speed knob, rails at the shipped `none`), the P80 instrumentation
# set (`FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1`), one claim per run.
#
#   C5  seed 5  (nothing)                                  control replay of P80 S20
#   D5  seed 5  FRUIT_CARRY_DIAG=1                          tracker-only neutrality
#   F5  seed 5  FRUIT_FAIL_FAST=150 FRUIT_CARRY_DIAG=1       the lever
#   D6  seed 6  FRUIT_CARRY_DIAG=1                          tracker-only, seed 6
#   F6  seed 6  FRUIT_FAIL_FAST=150 FRUIT_CARRY_DIAG=1       the lever, seed 6
#
# The seed-6 **control** is P80's own `logs/p80/S6.log` (same tree, no re-run:
# the only change since P80 is `bimanual.py`'s P82 wake-on-request, which the
# single-arm path never reaches - and `C5` proves the single arm is unmoved).
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
OUT=logs/p83
BASE="HEADLESS=1 ATTEMPTS=20"
INST="FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1"

arms=${*:-C5 D5 F5 D6 F6}

run_arm() {
    local name=$1 seed=$2 extra=$3
    echo "[p83] === $name (seed $seed) extra=[$extra] $(date +%H:%M:%S)"
    # shellcheck disable=SC2086
    scripts/154_claim_run.sh "$OUT/$name.driver" \
        $BASE SEED="$seed" $INST $extra \
        bash "$OUT/one_run.sh" "$OUT/$name.log" "$OUT/$name.stamps" \
        > "$OUT/$name.driver.log" 2>&1
    local rc=$?
    echo "[p83] === $name done rc=$rc $(date +%H:%M:%S)"
    grep -c '\[fail-fast\]' "$OUT/$name.log" 2>/dev/null | sed "s/^/[p83] $name fail-fast rows: /"
}

for arm in $arms; do
    case "$arm" in
        C5) run_arm C5 5 "" ;;
        D5) run_arm D5 5 "FRUIT_CARRY_DIAG=1" ;;
        F5) run_arm F5 5 "FRUIT_FAIL_FAST=150 FRUIT_CARRY_DIAG=1" ;;
        D6) run_arm D6 6 "FRUIT_CARRY_DIAG=1" ;;
        F6) run_arm F6 6 "FRUIT_FAIL_FAST=150 FRUIT_CARRY_DIAG=1" ;;
        *)  echo "[p83] unknown arm $arm"; exit 2 ;;
    esac
done
echo "[p83] battery complete $(date +%H:%M:%S)"
