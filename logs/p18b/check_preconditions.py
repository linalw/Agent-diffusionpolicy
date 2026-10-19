#!/usr/bin/env python3
"""P18-B precondition check: after A run 1, verify the stage-N env actually took effect.

Checks (the Oracle Gate-2 item 8): the manifest's trigger.mode == 'arrival' and acq is True;
the log carries >=1 '[carry]' row; >=1 'intercept trigger' note; and the rate is in the band
(the old R11-B A_1 read 6/15; floor 4/15). Exits 0 on pass, 3 on fail.

Usage: python3 logs/p18b/check_preconditions.py logs/p18b/N5_fix/A_1.log
"""
import glob
import json
import os
import re
import sys

log = sys.argv[1] if len(sys.argv) > 1 else "logs/p18b/N5_fix/A_1.log"
fails = []

man = sorted(
    glob.glob(os.path.join(os.path.dirname(log), "raw", "A_1", "*", "manifest.json"))
)
if not man:
    fails.append("no manifest found for A_1")
else:
    d = json.load(open(man[-1]))
    trg = d.get("trigger")
    if not isinstance(trg, dict):
        fails.append(f"trigger is {trg!r} (expected the arrival dict)")
    else:
        if trg.get("mode") != "arrival":
            fails.append(f"trigger.mode = {trg.get('mode')!r} (expected 'arrival')")
        if not trg.get("acq"):
            fails.append("trigger.acq is not True (ACQ did not take)")
    print(f"manifest: {man[-1]}")
    print(f"  trigger = {str(trg)[:120]}")
    print(f"  tasks_md5 = {d.get('tasks_md5')}")

txt = open(log, errors="replace").read()
ncarry = len(re.findall(r"\[carry\]", txt))
if ncarry == 0:
    fails.append("0 [carry] rows (the dynamic handover never ran)")
ninter = len(re.findall(r"intercept trigger", txt))
if ninter == 0:
    fails.append("0 'intercept trigger' notes (the trigger never fired)")
m = re.search(r"rollout success (\d+)/(\d+)", txt)
if not m:
    fails.append("no rollout success line (run incomplete?)")
else:
    ok, n = int(m.group(1)), int(m.group(2))
    if ok < 4:
        fails.append(f"rate {ok}/{n} below the band floor 4/15")
    print(f"  rate = {ok}/{n}; [carry] rows = {ncarry}; intercept-trigger notes = {ninter}")

if fails:
    print("PRECONDITION FAIL:")
    for f in fails:
        print(f"  - {f}")
    sys.exit(3)
print("PRECONDITIONS OK")
sys.exit(0)
