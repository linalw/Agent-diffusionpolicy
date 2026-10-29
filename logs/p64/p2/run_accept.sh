#!/usr/bin/env bash
# P64 E4: the knob-off acceptance (scope proof) - every P64/P62/P43/P54/P58 knob
# left unset, so the scripted line must be byte-identical to its record.
#
#   bash logs/p64/p2/run_accept.sh
#
# P62's A1 procedure (`logs/p62/p2/accept_wall.log` + `motion_gate.txt`): the
# scripted entry never constructs `SortingRLEnv`, the kwarg defaults to `None`
# and `234` executes the real resolver to prove `None` writes no hold - so this
# is the P38-M4/P43-style **import guard**, stated as such.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
mkdir -p logs/p64/p2

n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
if [ "${n:-0}" -gt 0 ]; then
    echo "[accept] simulator busy (${n} python.sh); refusing to start" >&2
    exit 1
fi
t0=$(date +%s)
env -u FRUIT_GRASP_LEFT_PRECOMP -u FRUIT_GRASP_LEFT_TOPDOWN -u FRUIT_ARM_PARK \
    -u FRUIT_POLICY_TRIGGER_ACQ -u FRUIT_CARRY_DIAG -u FRUIT_CARRY_ATTITUDE \
    -u FRUIT_ACQ_DIAG -u FRUIT_CARRY_HOLD_QUAT -u FRUIT_MOTION_REPORT \
    SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p64/p2/accept_wall.log scripts/accept.sh \
    > logs/p64/p2/accept_outer.log 2>&1
rc=$?
echo "[accept] exit=$rc in $(( $(date +%s) - t0 )) s"
python3 scripts/105_motion_regression.py logs/p64/p2/accept_wall.log \
    --fingerprint configs/motion_reference.json > logs/p64/p2/motion_gate.txt 2>&1
echo "[accept] motion gate:"
grep -E "fingerprint|success:|FAIL|PASS" logs/p64/p2/motion_gate.txt | head -10
python3 - <<'EOF'
import re
ref = "logs/p41/p2/accept_profile.log"
new = "logs/p64/p2/accept_wall.log"
def rows(path, drop_instrument):
    out = []
    for ln in open(path, errors="replace"):
        if "[fruit]" not in ln:
            continue
        if drop_instrument and ("[diag]" in ln or "[carry]" in ln):
            continue
        out.append(ln.rstrip())
    return out
a, b = rows(ref, True), rows(new, True)
same = sum(1 for x, y in zip(a, b) if x == y)
print(f"[accept] [fruit] rows: reference {len(a)} (instrument removed), this run {len(b)}, identical {same}")
print(f"[accept] identity: {'377/377 IDENTICAL' if len(a) == len(b) == 377 and same == 377 else 'DIFFERS'}")
EOF
exit $rc
