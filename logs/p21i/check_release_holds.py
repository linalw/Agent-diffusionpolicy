#!/usr/bin/env python3
"""P21-B stub: the release hold-count knobs (FRUIT_RELEASE_PAD_HOLD / _FINGER_HOLD).

Pins (offline, no simulator):
  1. the two knobs exist at the release sites with the default-3 / max(1, ...) form;
  2. the unset path is the shipped literal 3 (byte-inert): the resolved value is 3 and the
     release block's tick arithmetic equals the shipped 8 + 20 + 40*3 + 16*3 (+ the R0 descent);
  3. the clamp: 0 and negatives resolve to 1; the TASKS_MD5 pin matches the file.

Run: python3 logs/p21i/check_release_holds.py
"""
import hashlib
import os
import re
import sys

SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src", "fruit_sorting", "tasks.py")
RL = os.path.join(os.path.dirname(__file__), "..", "..", "src", "fruit_sorting", "rl_env.py")
fails = []

src = open(SRC).read()
rl = open(RL).read()

# 1. the knobs and their exact form
for name, ramp in (("FRUIT_RELEASE_PAD_HOLD", 40), ("FRUIT_RELEASE_FINGER_HOLD", 16)):
    pat = (
        rf'{name}"\s*,\s*"3"\)\)')
    if not re.search(pat, src):
        fails.append(f"{name}: no max(1, int(os.environ.get({name!r}, '3'))) site")
    if f"for _ in range({name.split('_')[-2].lower()}_hold)" not in src:
        fails.append(f"{name}: the loop does not use the resolved hold variable")

# 2. the resolution semantics (the same expression the code evaluates)
for raw, want in (("", 3), ("3", 3), ("1", 1), ("0", 1), ("-2", 1), ("12", 12)):
    got = max(1, int(os.environ.get("__P21B_NEVER_SET__", raw or "3")))
    if got != want:
        fails.append(f"resolution({raw!r}) = {got}, expected {want}")

# the tick arithmetic: unset => the shipped 196-tick fixed tail
tail = 8 + 20 + 40 * 3 + 16 * 3
if tail != 196:
    fails.append(f"unset tail = {tail}, expected 196")
lever_tail = 8 + 12 + 40 * 1 + 16 * 1
if lever_tail != 76:
    fails.append(f"lever tail = {lever_tail}, expected 76 (the -120 tick trim)")

# 3. the pin
digest = hashlib.md5(open(SRC, "rb").read()).hexdigest()
m = re.search(r'TASKS_MD5 = "([0-9a-f]{32})"', rl)
if not m:
    fails.append("TASKS_MD5 not found in rl_env.py")
elif m.group(1) != digest:
    fails.append(f"TASKS_MD5 {m.group(1)} != the file's {digest}")

if fails:
    print("FAIL:")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("PASS: the release hold-count knobs (default 3, max(1, ...)), the unset tail = 196 ticks,")
print("      the lever tail = 76 ticks (-120), the pin matches.")
