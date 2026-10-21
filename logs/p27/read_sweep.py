#!/usr/bin/env python3
"""P27-C read: the belt-speed sweep (the direct/policy interface + the scripted two-line).

Per speed: the direct rate + the per-episode classes (success / grasped-not-placed / no-grasp)
and the acquisition mechanism (the close-start |y| median, the catch-up chases) from the
`[acq]` rows; the scripted two-line placed/nc/carried from the `[run] attempt` rows.
Read-only. Usage: python3 logs/p27/read_sweep.py
"""
import glob
import re
import statistics as st

EP = re.compile(r"\[rl\] episode \d+: .*?success=(\w+) grasped=(\w+) placed=(\w+)")
ACQ = re.compile(
    r"\[acq\] (left|right) idx=\d+: .*?close_start=\(([-+0-9.]+),([-+0-9.]+),([-+0-9.]+)\)mm"
)
ATT = re.compile(r"\[run\] attempt (\d+) \((\w+)\): grasped=(\w+) placed=(\w+)")


def direct(path):
    txt = open(path, errors="replace").read()
    eps = [(m.group(1) == "True", m.group(2) == "True", m.group(3) == "True")
           for m in EP.finditer(txt)]
    ok = sum(1 for s, _, _ in eps if s)
    carried = sum(1 for s, g, p in eps if g and not p)
    nc = sum(1 for s, g, p in eps if not g)
    cs = [abs(float(m.group(3))) for m in ACQ.finditer(txt)]
    ch = [int(x) for x in re.findall(r"catchup=(\d+)t", txt)]
    return dict(n=len(eps), ok=ok, nc=nc, carried=carried, cs=st.median(cs) if cs else float("nan"),
                chases=sum(1 for c in ch if c >= 195))


def scripted(path):
    txt = open(path, errors="replace").read()
    rows = {(int(m.group(1)), m.group(2)): (m.group(4) == "True")
            for m in ATT.finditer(txt)}
    ok = sum(1 for v in rows.values() if v)
    n = len(rows)
    nc = sum(1 for m in ATT.finditer(txt) if m.group(3) == "False")
    return dict(n=n, ok=ok, nc=nc, carried=n - ok - nc)


print("| interface | speed | n | placed | nc | carried | close-start |y| p50 | chases |")
print("| --- | --- | --- | --- | --- | --- | --- | --- |")
for sp in ("008", "010", "012", "015"):
    fs = sorted(glob.glob(f"logs/p27/2*_direct_{sp}.log"))
    if not fs:
        print(f"| direct | 0.{sp[1:]} | pending | | | | | |")
        continue
    d = direct(fs[0])
    print(f"| direct | 0.{sp[1:]} | {d['n']} | {d['ok']} | {d['nc']} | {d['carried']} | "
          f"{d['cs']:.1f} | {d['chases']} |")
for sp in ("008", "010"):
    fs = sorted(glob.glob(f"logs/p27/3*_twoline_{sp}.log"))
    if not fs:
        print(f"| two-line | 0.{sp[1:]} | pending | | | | | |")
        continue
    d = scripted(fs[0])
    print(f"| two-line | 0.{sp[1:]} | {d['n']} | {d['ok']} | {d['nc']} | {d['carried']} | - | - |")
print()
print("references: direct @0.12 seed 77 historical = 4-10/15 (the L3/P13 A runs); two-line @0.12")
print("mass base = 45/60 (s11 11, s5 17, s23 17); the acceptance 0.12/0.15 x flip/no-flip = 9/7/5/3.")
