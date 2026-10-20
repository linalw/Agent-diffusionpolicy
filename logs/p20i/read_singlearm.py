#!/usr/bin/env python3
"""P22-A read: the B1c corrected single-arm battery (logs/p20/B1C_DESIGN.md endpoints).

Per arm (A shipped / B skip+DG+RESYNC / P placebo): the pooled census (placed/nc/carried), the
clean gap p50, the skip=1 rows, the credit values, and the empty-poll ("no eligible fruit")
count. Read-only.

Usage: python3 logs/p20i/read_singlearm.py
"""
import glob
import re
import statistics as st

SIM = re.compile(r"\[run\] attempt (\d+): .*sim=([0-9.]+)-([0-9.]+)s")
ATT = re.compile(r"attempt (\d+): grasped=(\w+) placed=(\w+)")
SKIP = re.compile(r"\[ready\] \w+ skip=1 ")
CREDIT = re.compile(r"credit=(\d+)")


def read(arm):
    placed = nc = carried = empty = skips = 0
    gaps, credits = [], []
    runs = sorted(glob.glob(f"logs/p20i/*_sa_{arm}.log"))
    for p in runs:
        txt = open(p, errors="replace").read()
        rows = {}
        for m in ATT.finditer(txt):
            rows[int(m.group(1))] = (m.group(2) == "True", m.group(3) == "True")
        placed += sum(1 for g, pl in rows.values() if pl)
        carried += sum(1 for g, pl in rows.values() if g and not pl)
        nc += sum(1 for g, pl in rows.values() if not g)
        empty += len(re.findall(r"no eligible fruit", txt))
        skips += len(SKIP.findall(txt))
        credits += CREDIT.findall(txt)
        sims = sorted({(int(m.group(1)), float(m.group(2)), float(m.group(3))) for m in SIM.finditer(txt)})
        gaps += [sims[i+1][1] - sims[i][2] for i in range(len(sims)-1)]
    clean = [g for g in gaps if 0 < g < 7]
    return dict(runs=len(runs), placed=placed, nc=nc, carried=carried, empty=empty,
                skips=skips, credits=sorted(set(credits)), gap=st.median(clean) if clean else float("nan"))


print("| arm | runs | placed | nc | carried | total fail | empty polls | skip rows | credits | gap p50 s |")
print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
for arm in ("A", "B", "P"):
    d = read(arm)
    print(f"| {arm} | {d['runs']} | {d['placed']} | {d['nc']} | {d['carried']} | "
          f"{d['nc']+d['carried']} | {d['empty']} | {d['skips']} | {d['credits']} | {d['gap']:.2f} |")
print()
print("The design's reads: the mechanism = the skip fires + the credit keeps the branch (the")
print("census == A's); the empty-poll class closed; the pooled census not worse; the gap -1.9 s.")
