#!/usr/bin/env bash
# P36 phase 1 - the per-cell observation smoke (1 episode each, seed 77).
#
# Four cells of the 2x2 (`logs/p36/PREREG.md`) plus two no-op controls:
#   s1  ready/ready        (the shipped direct env)          - the control
#   s2  park/park          FRUIT_ARM_PARK=back               - the P35 lever
#   s3  park-image/ready-proprio                             - the image probe
#   s4  ready-image/park-proprio                             - the proprio probe
#   s1b ready/ready but *written* (FRUIT_PROPRIO_SPOOF=ready) - the ready vector
#   s2b park/park but *written* (spoof=back)                  - the back vector
#
# The last two are the source-vector controls: the spoof writes the pose the
# reset achieved, so in a cell where the arm already stands there the spoofed
# proprio must equal the live proprio to within the measured drift (`drift=`).
#
# Everything else is the P35 C batch's scenario verbatim, so the cells differ
# only in the two knobs. Run under `scripts/154_claim_run.sh` (one simulator).
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

out=logs/p36/smoke
ckpt=checkpoints/moe_v13s/policy_best.pt
common=(
  HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1
  FRUIT_POLICY_SEED=11 FRUIT_SIZE_FILTER=
  FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
  FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
  FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9
  FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_TRIGGER_ACQ=1
  FRUIT_ACQ_DIAG=1 FRUIT_RESET_ALIGN_DIAG=1 FRUIT_PARK_DIAG=1 FRUIT_SPOOF_DIAG=1
)

mkdir -p "$out/raw"
echo "P36 phase-1 smoke $(date -Iseconds)"
md5sum src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
       configs/arm_parks.json configs/proprio_spoof.json \
       "$ckpt" | tee "$out/smoke_tree_md5.txt"
echo

run_cell() {
  local label=$1; shift
  local log="$out/${label}.log"
  echo "--- $label: $*"
  env "${common[@]}" "$@" scripts/run.sh scripts/110_rl_rollout.py \
      --ckpt "$ckpt" --presentation direct --episodes 1 --seeds 77 \
      --out "$out/raw/$label" > "$log" 2>&1
  local code=$?
  echo "    exit=$code  $(grep -c '\[spoof\] episode' "$log") spoof row(s)  $(grep -c '\[park\] episode' "$log") park row(s)"
  grep -h '\[rl\] episode 0:' "$log" | sed 's/^/    /'
  grep -h '\[spoof\] episode' "$log" | sed 's/^/    /'
  grep -h '\[park\] episode' "$log" | sed 's/^/    /'
  return $code
}

fail=0
run_cell s1  || fail=1
run_cell s2  FRUIT_ARM_PARK=back || fail=1
run_cell s3  FRUIT_ARM_PARK=back FRUIT_PROPRIO_SPOOF=ready || fail=1
run_cell s4  FRUIT_PROPRIO_SPOOF=back || fail=1
run_cell s1b FRUIT_PROPRIO_SPOOF=ready || fail=1
run_cell s2b FRUIT_ARM_PARK=back FRUIT_PROPRIO_SPOOF=back || fail=1
echo
echo "P36 phase-1 smoke done $(date -Iseconds) fail=$fail"
exit $fail
