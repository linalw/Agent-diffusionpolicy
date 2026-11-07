#!/usr/bin/env bash
# P125 step 4 (only if the canary bar passes): the three-lane flip's scripted
# no-harm + reference re-record.
#
# PRECONDITION: `src/fruit_sorting/assets.py` already defaults
# `output_lanes` to 3 (`OUTPUT_LANES_DEFAULT`) and `scripts/264` /
# `scripts/234` are re-pinned. `FRUIT_OUTPUT_LANES=2` restores the old scene.
#
# Runs, in order:
#   1. archive the pre-flip references into logs/p125/;
#   2. the shipped acceptance (two-line, 10 attempts) -> the source log;
#      write BOTH two-line-side references from it (the P87/P124 arrangement:
#      `configs/motion_reference.json` IS the two-line record);
#   3. the single-arm restore acceptance (`FRUIT_BIARM=0`) -> write
#      `configs/motion_reference_single.json`;
#   4. a repeat acceptance -> require bit-identity on the `[fruit]` stream and
#      `fingerprint: matches` + `190: PASS`;
#   5. a final acceptance on the settled tree.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p125

for f in configs/motion_reference.json configs/motion_reference_twoline.json \
         configs/motion_reference_single.json; do
    cp "$f" "logs/p125/$(basename "$f" .json)_pre_p125.json"
done
md5sum logs/p125/*_pre_p125.json | tee logs/p125/references_pre_p125.txt

echo "=== 1. acceptance source (two-line, 10 attempts) $(date +%H:%M:%S) ==="
SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p125/accept_source.log scripts/accept.sh \
    > logs/p125/accept_source.driver 2>&1
echo "[flip] accept source exit=$?"
grep -E "rate:|\[stats\]" logs/p125/accept_source.log | tail -2

python3 scripts/105_motion_regression.py logs/p125/accept_source.log \
    --write-fingerprint configs/motion_reference.json \
    > logs/p125/write_twoline.log 2>&1
echo "[flip] write configs/motion_reference.json exit=$?"
cp configs/motion_reference.json configs/motion_reference_twoline.json
md5sum configs/motion_reference.json configs/motion_reference_twoline.json \
    | tee logs/p125/references_twoline_p125.txt

echo "=== 2. single-arm restore acceptance (three-lane scene) $(date +%H:%M:%S) ==="
SKIP_SELFCHECK=1 FRUIT_BIARM=0 ACCEPT_LOG=logs/p125/accept_single.log scripts/accept.sh \
    > logs/p125/accept_single.driver 2>&1
echo "[flip] accept single exit=$?"
python3 scripts/105_motion_regression.py logs/p125/accept_single.log \
    --write-fingerprint configs/motion_reference_single.json \
    > logs/p125/write_single.log 2>&1
echo "[flip] write configs/motion_reference_single.json exit=$?"
md5sum configs/motion_reference_single.json | tee logs/p125/references_single_p125.txt

echo "=== 3. repeat acceptance (bit-identity + gate) $(date +%H:%M:%S) ==="
SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p125/accept_repeat.log scripts/accept.sh \
    > logs/p125/accept_repeat.driver 2>&1
echo "[flip] accept repeat exit=$?"

echo "=== 4. final acceptance $(date +%H:%M:%S) ==="
SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p125/accept_final.log scripts/accept.sh \
    > logs/p125/accept_final.driver 2>&1
echo "[flip] accept final exit=$?"

echo "=== 5. compares ==="
python3 - logs/p125/accept_source.log logs/p125/accept_repeat.log \
    logs/p125/accept_final.log <<'PY' | tee logs/p125/accept_identity.txt
import sys

def fruit_lines(path):
    return [line for line in open(path, encoding="utf-8", errors="ignore")
            if "[fruit]" in line]

a, b, c = (fruit_lines(p) for p in sys.argv[1:4])
print(f"source={len(a)} repeat={len(b)} final={len(c)}")
print(f"source==repeat: {a == b} ({sum(x == y for x, y in zip(a, b))}/{max(len(a), len(b))})")
print(f"source==final:  {a == c} ({sum(x == y for x, y in zip(a, c))}/{max(len(a), len(c))})")
PY
grep -E "fingerprint:|190:|rate:" logs/p125/accept_final.driver | tail -6
echo "[flip] done $(date +%H:%M:%S)"
