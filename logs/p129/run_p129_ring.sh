#!/usr/bin/env bash
# P129 bench B - the ring across the pad-material ladder.
#
#   bash logs/p129/run_p129_ring.sh          # cage4 + cage3 (~6 min)
#   P129_KINDS=cage4 bash logs/p129/run_p129_ring.sh
#
# One app session per hand kind: `cage_hand.author_cage` reads the ring's pad
# count and plate width from the environment at import.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$ROOT"

kinds=$(echo "${P129_KINDS:-cage4,cage3}" | tr "," " ")
for kind in ${kinds}; do
    OUT="logs/p129/fixture_ring_${kind}.log"
    echo "[p129] bench B - ${kind} -> ${OUT}"
    P129_KIND="${kind}" scripts/run.sh logs/p129/fixture_ring.py > "${OUT}" 2>&1 || true
    grep -E "\[p129r\] (ring|support|A1)" "${OUT}" | tail -12
    echo "[p129] ${kind} table"
    sed -n '/^kind /,$p' "${OUT}" | tail -40
done
