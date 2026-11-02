#!/usr/bin/env bash
# P97 gates: the three identities, the shipped default's census and the re-record.
#
#   bash logs/p97/gates.sh
#
# G1 = the `=0` arm reproduces the pre-P97 record; G2 = the single arm is
# untouched; G3 = the shipped default IS P96's measured arm (the same `[fruit]`
# stream as `logs/p96/T5.log`, same seed, same instrumentation - only the
# pre-pose row's origin label differs, and that row is not in the stream).
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
rc=0

echo "== G1: the =0 arm vs the P94 record (419/419) =="
if python3 logs/p96/p96_report.py --same logs/p94/accept_final.log \
        logs/p97/accept_pre97.log > logs/p97/G1.same 2>&1; then
    echo "[p97gates] G1 IDENTICAL"; tail -2 logs/p97/G1.same
else
    echo "[p97gates] G1 DIFFERS"; rc=1; sed -n 1,6p logs/p97/G1.same
fi
grep -q "fingerprint: matches" logs/p97/accept_pre97.out \
    && echo "[p97gates] G1 fingerprint matches 30fb99f8" \
    || { echo "[p97gates] G1 fingerprint NOT matched"; rc=1; }
echo

echo "== G2: the single arm vs the P71 record (346/346) =="
if python3 logs/p96/p96_report.py --same logs/p71/accept_rails_none.log \
        logs/p97/accept_single.log > logs/p97/G2.same 2>&1; then
    echo "[p97gates] G2 IDENTICAL"; tail -2 logs/p97/G2.same
else
    echo "[p97gates] G2 DIFFERS"; rc=1; sed -n 1,6p logs/p97/G2.same
fi
grep -q "fingerprint: matches configs/motion_reference_single.json" \
    logs/p97/accept_single.out \
    && echo "[p97gates] G2 single fingerprint matches" \
    || { echo "[p97gates] G2 single fingerprint NOT matched"; rc=1; }
echo

echo "== G3: the shipped default is P96's measured arm (S5 vs T5) =="
if [ -s logs/p97/S5.log ]; then
    # PREREG §2 G3: the pre-pose row's origin label is the one registered
    # difference (`1(explicit)` -> `1(default)`), so that one row is dropped.
    if python3 logs/p97/p97_report.py --same-g3 logs/p96/T5.log logs/p97/S5.log \
            > logs/p97/G3.same 2>&1; then
        echo "[p97gates] G3 IDENTICAL - the default IS the measured arm"
        tail -2 logs/p97/G3.same
    else
        echo "[p97gates] G3 DIFFERS"; rc=1; sed -n 1,6p logs/p97/G3.same
    fi
else
    echo "[p97gates] G3 no S5.log"; rc=1
fi
echo

echo "== the census: the shipped default's own contact count =="
if [ -s logs/p97/census.txt ]; then
    grep -E "n=|CONTACTS|left |right " logs/p97/census.txt | tail -5
    contacts=$(grep -oE "CONTACTS [0-9]+/[0-9]+" logs/p97/census.txt | tail -1 | awk '{print $2}' | cut -d/ -f1)
    if [ "${contacts:-1}" -eq 0 ]; then
        echo "[p97gates] census 0 contacts"
    else
        echo "[p97gates] census FAIL - ${contacts} contact(s)"; rc=1
    fi
else
    echo "[p97gates] no census.txt"; rc=1
fi
echo

echo "== the re-record: both two-line references match their own run =="
md5sum configs/motion_reference.json configs/motion_reference_twoline.json \
       configs/motion_reference_single.json
grep -q "190: PASS" logs/p97/gate_accept_default.txt \
    && echo "[p97gates] 190 PASS on accept_default" \
    || { echo "[p97gates] 190 not PASS on accept_default"; rc=1; }
grep -q "190: PASS" logs/p97/gate_twoline_ref.txt \
    && echo "[p97gates] 190 PASS on twoline_ref" \
    || { echo "[p97gates] 190 not PASS on twoline_ref"; rc=1; }
echo

echo "== the fresh-shard provenance (P96 keys + P72/P87/P93 blocks) =="
if [ -s logs/p97/shard_manifest.json ]; then
    python3 - <<'PY'
import json
m = json.load(open("logs/p97/shard_manifest.json"))
c = m.get("collection") or {}
print(f"[p97gates] prepose_clear={c.get('prepose_clear')} "
      f"defaulted={c.get('prepose_clear_defaulted')} z={c.get('prepose_clear_z')}")
print(f"[p97gates] mode={c.get('mode')} twoline={c.get('biarm_twoline_resolved')} "
      f"scene={'scene' in m} supply.band={'band' in (m.get('supply') or {})} "
      f"physics.release={'release' in (m.get('physics') or {})}")
assert c.get("prepose_clear") == 1, "fresh shard did not run the clearance pre-pose"
assert c.get("prepose_clear_defaulted") is True, "the fresh shard is not the default"
assert abs(float(c.get("prepose_clear_z")) - 0.165) < 1e-9, "unexpected pre-pose z"
PY
    [ $? -eq 0 ] || { echo "[p97gates] manifest FAIL"; rc=1; }
else
    echo "[p97gates] no shard_manifest.json"; rc=1
fi

echo "[p97gates] done rc=$rc"
exit "$rc"
