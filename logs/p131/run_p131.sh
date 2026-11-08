#!/usr/bin/env bash
# P131 - the registered battery: U5/U6 (the shipped law, same-tree controls),
# P5/P6 (pad_axes, the candidate) and M5 (max_extent, the screen).  Two Isaac
# streams with disjoint files (the P108 `cells.sh` split).
#
#   bash logs/p131/run_p131.sh
#   ATTEMPTS=1 bash logs/p131/run_p131.sh   # a smoke
set -euo pipefail
cd "$(dirname "$0")/../.."
OUT=logs/p131
mkdir -p "$OUT"

bash logs/p131/cells.sh U:6 P:5 > "$OUT/streamA.log" 2>&1 &
a=$!
bash logs/p131/cells.sh P:6 M:5 > "$OUT/streamB.log" 2>&1 &
b=$!
wait "$a" || true
wait "$b" || true
echo "=== streams"
tail -3 "$OUT/streamA.log" || true
tail -3 "$OUT/streamB.log" || true
for f in U_s5 U_s6 P_s5 P_s6 M_s5; do
    grep -H -E '^\[fruit\] \[stats\]' "$OUT/$f.log" || echo "  $f: no stats"
done
