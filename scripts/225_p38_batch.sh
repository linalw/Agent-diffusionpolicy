#!/usr/bin/env bash
# P38 phase 2 steps 2-3: the batches. `m12` = M1 + M2, `m3` = M3, `g2` = the
# Gate-2 DIAG=0/1 pair (see below).
#
#   bash scripts/225_p38_batch.sh m12      # one claim, ~70-90 min
#   bash scripts/225_p38_batch.sh m3       # one claim, ~70-90 min
#   bash scripts/225_p38_batch.sh g2       # one claim, ~10-12 min (two 15-episode runs)
#
# The pre-registration is `logs/p38/PREREG.md` + `PREREG_A1.md` (the Gate-1
# amendment; where they disagree the amendment governs). Scenario = the
# P36/P37 block verbatim + the four default-off refuse knobs per arm:
#
#   A = DIAG only                       (the control: attribution, no behaviour)
#   B = DIAG + END                      (M1 only: the terminal class)
#   C = DIAG + END + RESEED + MAX=2      (the lever)
#
# **A2b (the measured amendment): the forced-refusal instrument is the *gate*,
# not a supply band.** The A2 probes measured that a 4 cm supply lane is not a
# supply band at all: at 0.13-0.17 the delivered x spans 0.117-0.191 (12 % of
# 65 transits land ABOVE the right arm's 0.173 floor, so the band is not
# forced) and the free-cadence supply probe reads 0.080/0.529 m - depenetration
# kicks push fruit off the **low** belt edge (0.080 against the 0.110 edge; the
# 0.529 maximum is still **inside** the 0.570 high edge), `logs/p38/z1_supply_m1.log`,
# `z2_drift_m1.log`. So M1 forces the refusal with `TRIGGER_LATERAL=0` (every
# would-fire tick is refused, by construction, on the *shipped* supply) and M2
# with `TRIGGER_LATERAL=0.06` (~35-50 % of the shipped delivered band refused:
# `x < station_x - 0.06`; the shipped direct |dx| p50 is ~6 cm). Both
# probes therefore run the shipped scenario's own delivered-x distribution and
# exercise the *learned close* as a live second fire path at |dx| < 0.16 -
# which is exactly the H1/A1 question a below-floor band could not ask (at
# |dx| > 0.16 the close is geometrically impossible).
#
# M1: the forced refusal (lateral 0), SEED=5, 15 episodes per arm, arms A/B/C.
# M2: the mixed refusal (lateral 0.06 - the P2b-era gate), seeds 5/101/202, 15
#     episodes, A then C.
# M3: the shipped patch band (lateral 0.16, the shipped gate), seeds
#     77/101/202/303/404, 15 episodes, A then C.
# G2 (the Gate-2 additions, after the batch):
#   * the **DIAG=0 / DIAG=1 pair** on the M1 band, SEED=5, 15 episodes each, in
#     one claim - the `FRUIT_POLICY_REFUSE_DIAG` neutrality read the batch did
#     not have (it ran DIAG=1 in *both* arms, so it could not compare). The
#     direct loop is not reproducible (rendered frames), so the pair is a
#     same-batch repeat, not a bit-identity claim: compare the outcome classes.
#     `G2_diag1` also carries the `[refuse] close: tick=... dy=...` rows the
#     END's H1 scoping needs (the close tick's own `dy`, i.e. whether the
#     second fire path latched before or after the fruit's departure).
#   * the scripted no-harm is `226_p38_m4.sh` (it also records that
#     `accept_policy.sh` was not run - the four knobs raise on any presentation
#     other than `direct`, so the hybrid canary cannot read them).
#
# One simulator at a time: every run is wrapped in `scripts/154_claim_run.sh`
# by the caller (a single claim for the whole batch, one sim process at a
# time), and the driver never kills another lane's run.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

mode=${1:-m12}
CKPT=checkpoints/moe_v13s/policy_best.pt
SCEN="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 "
SCEN+="FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_DYNAMIC_PICK=1 FRUIT_RESET_ALIGN_DIAG=1"
COMMON="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1 "
COMMON+="FRUIT_SIZE_FILTER= FRUIT_SUPPLY_SCATTER=1 FRUIT_POLICY_SEED=11"

A_ENV="FRUIT_POLICY_REFUSE_DIAG=1"
B_ENV="FRUIT_POLICY_REFUSE_DIAG=1 FRUIT_POLICY_REFUSE_END=1"
C_ENV="FRUIT_POLICY_REFUSE_DIAG=1 FRUIT_POLICY_REFUSE_END=1 "
C_ENV+="FRUIT_POLICY_RESEED=1 FRUIT_POLICY_RESEED_MAX=2"

PATCH_ENV="FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25"

run() {  # run <out-dir> <label> <seed> <env-string>
    local out=$1 label=$2 seed=$3 extra=$4
    if [ ! -f "$CKPT" ]; then
        echo "[p38batch] FAIL: missing $CKPT"
        return 1
    fi
    # shellcheck disable=SC2086
    env $COMMON $SCEN $extra scripts/run.sh scripts/110_rl_rollout.py \
        --ckpt "$CKPT" --presentation direct --episodes 15 --seeds "$seed" \
        --out "$out/raw/${label}" > "$out/${label}.log" 2>&1
    local code=$?
    echo "[p38batch] ${label} (seed ${seed}) exit=${code} $(date +%H:%M:%S)"
    echo "  $(grep -oE '\[rl\] rollout success [0-9]+/[0-9]+' "$out/${label}.log" | tail -1)"
    echo "  $(grep -oE 'no firable fruit|lateral refuse:|reseed: [a-z ]+' \
        "$out/${label}.log" | sort | uniq -c | tr '\n' ' ')"
}

if [ "$mode" = "m12" ]; then
    OUT=logs/p38/P2
    mkdir -p "$OUT"
    {
        echo "# P38 phase 2 M1+M2 batch header ($(date '+%F %T'))"
        echo "# M1 forced refusal (TRIGGER_LATERAL=0) SEED=5 arms A/B/C; M2 mixed refusal (LATERAL=0.06) seeds 5/101/202 arms A/C"
        echo "# (A2b: the supply-band form was measured unusable; the header's first line above is the shipped text)"
        echo "# scenario: $SCEN $COMMON"
        echo "# arms: A='$A_ENV' B='$B_ENV' C='$C_ENV'"
        md5sum "$CKPT" scripts/225_p38_batch.sh scripts/110_rl_rollout.py \
            src/fruit_sorting/rl_env.py src/fruit_sorting/policy/trigger.py \
            src/fruit_sorting/tasks.py src/fruit_sorting/fruits.py \
            configs/motion_reference.json 2>/dev/null
        git rev-parse HEAD
    } > "$OUT/M12_header.txt"
    cat "$OUT/M12_header.txt"

    M1="FRUIT_POLICY_TRIGGER_LATERAL=0"
    for arm in A B C; do
        case $arm in
            A) extra="$A_ENV";; B) extra="$B_ENV";; C) extra="$C_ENV";;
        esac
        run "$OUT" "M1_$arm" 5 "$M1 $extra"
    done

    M2="FRUIT_POLICY_TRIGGER_LATERAL=0.06"
    i=0
    for seed in 5 101 202; do
        i=$((i + 1))
        run "$OUT" "M2_A_$i" "$seed" "$M2 $A_ENV"
        run "$OUT" "M2_C_$i" "$seed" "$M2 $C_ENV"
    done
elif [ "$mode" = "m3" ]; then
    OUT=logs/p38/P3
    mkdir -p "$OUT"
    {
        echo "# P38 phase 2 M3 batch header ($(date '+%F %T'))"
        echo "# the shipped patch band, seeds 77/101/202/303/404, arms A then C"
        echo "# scenario: $SCEN $COMMON $PATCH_ENV"
        echo "# arms: A='$A_ENV' C='$C_ENV'"
        md5sum "$CKPT" scripts/225_p38_batch.sh scripts/110_rl_rollout.py \
            src/fruit_sorting/rl_env.py src/fruit_sorting/policy/trigger.py \
            src/fruit_sorting/tasks.py src/fruit_sorting/fruits.py \
            configs/motion_reference.json 2>/dev/null
        git rev-parse HEAD
    } > "$OUT/M3_header.txt"
    cat "$OUT/M3_header.txt"
    i=0
    for seed in 77 101 202 303 404; do
        i=$((i + 1))
        run "$OUT" "M3_A_$i" "$seed" "$PATCH_ENV $A_ENV"
        run "$OUT" "M3_C_$i" "$seed" "$PATCH_ENV $C_ENV"
    done
elif [ "$mode" = "g2" ]; then
    # The Gate-2 pair (`logs/p38/P2_RESULTS.md` section 3c/6): the DIAG's
    # neutrality, one seed, 15 episodes per arm, in one claim. G2_diag0 runs the
    # M1 band with *no* refuse knob at all; G2_diag1 turns only DIAG on. Control
    # first (the order is confounded with wall-clock drift, as every run here is;
    # the recorded M1_A is a third DIAG=1 sample on the same band).
    OUT=logs/p38/G2
    mkdir -p "$OUT"
    {
        echo "# P38 phase 2 Gate-2 header ($(date '+%F %T'))"
        echo "# the DIAG=0/1 pair on the M1 band (TRIGGER_LATERAL=0), SEED=5, 15 episodes each"
        echo "# scenario: $SCEN $COMMON"
        echo "# arms: diag0='(no refuse knob)' diag1='$A_ENV'"
        md5sum "$CKPT" scripts/225_p38_batch.sh scripts/110_rl_rollout.py \
            src/fruit_sorting/rl_env.py src/fruit_sorting/policy/trigger.py \
            src/fruit_sorting/tasks.py src/fruit_sorting/fruits.py \
            configs/motion_reference.json 2>/dev/null
        git rev-parse HEAD
    } > "$OUT/G2_header.txt"
    cat "$OUT/G2_header.txt"
    M1="FRUIT_POLICY_TRIGGER_LATERAL=0"
    run "$OUT" "G2_diag0" 5 "$M1"
    run "$OUT" "G2_diag1" 5 "$M1 $A_ENV"
    grep -oE '\[refuse\] close: tick=[0-9]+ dy=[-+0-9.]+ m' "$OUT/G2_diag1.log" \
        > "$OUT/G2_close_dy.txt"
    echo "[p38batch] G2 close rows: $(wc -l < "$OUT/G2_close_dy.txt")"
else
    echo "usage: bash scripts/225_p38_batch.sh {m12|m3|g2}"
    exit 2
fi
echo "[p38batch] mode=$mode done $(date +%H:%M:%S)"
