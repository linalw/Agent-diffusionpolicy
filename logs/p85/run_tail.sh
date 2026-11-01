#!/usr/bin/env bash
# P85 tail: the shipped acceptance command end to end, then a two-episode
# defaulted collection (the collector's manifest, end to end).
#
#   RUN_LIMIT=2400 scripts/154_claim_run.sh logs/p85/tail.driver \
#       bash logs/p85/run_tail.sh
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

echo "=== accept.sh (the shipped command) ==="
ACCEPT_LOG=logs/p85/accept_final.log bash scripts/accept.sh
acc=$?
echo "[tail] accept.sh exit=$acc"

echo
echo "=== collector probe: 2 episodes, defaulted scheduler ==="
rm -rf logs/p85/collect_probe
HEADLESS=1 FRUIT_EPISODES=2 FRUIT_DEMO_DIR=logs/p85/collect_probe FRUIT_COLLECT_CHUNK=6 \
    scripts/run.sh scripts/40_collect_demos.py > logs/p85/collect_probe.log 2>&1
col=$?
echo "[tail] collector exit=$col"

echo
echo "=== collector manifest (the P85 provenance keys) ==="
python3 - <<'EOF'
import json
m = json.load(open("logs/p85/collect_probe/manifest.json"))
c = m["collection"]
for key in ("mode", "biarm", "biarm_twoline", "biarm_resolved",
            "biarm_twoline_resolved", "biarm_defaulted", "biarm_twoline_defaulted",
            "park_early", "grade_routing"):
    print(f"  collection.{key} = {c.get(key, '<missing>')}")
s = m["supply"]
print(f"  supply.wave = {s['wave']}  supply.patch = {s['patch']}  "
      f"grades = {s['grades']}")
print(f"  scene.output_rails = {m['scene']['output_rails']}")
print(f"  physics.profile = {m['physics']['profile']}")
EOF
echo "[tail] done"
exit $(( acc != 0 ? acc : col ))
