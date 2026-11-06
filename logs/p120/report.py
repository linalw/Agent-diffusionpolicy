#!/usr/bin/env python3
"""P120 report - the 60 N jaw on the shipped two-line, four seeds.

Reads `logs/p120/mf60_s{5,6,101,202}.log` and the same-seed controls
(`logs/p92/C5.log`, `C6.log`, `logs/p93/C101.log`, `C202.log`), and prints:
the placed count per seed and pooled (with Fisher), the failure classes, the
crush guard (`sep@loss - dia`), the landing (`on_belt`), and the interval
(mean/p50/p90 from each attempt's `t1`).

  python3 logs/p120/report.py
"""

from __future__ import annotations

import math
import re
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WIN = re.compile(r"\[run\] attempt (\d+) \((\w+)\): picking .*? sim=([\d.]+)-([\d.]+)s")
OUT = re.compile(r"\[run\] attempt (\d+) \((\w+)\): grasped=(\w+) placed=(\w+)")
CARRY = re.compile(
    r"\[carry\] (\w+) (\w+): ticks=(\d+)/(\d+) clean_slip_max=([\d.]+)mm"
)
CRUSH = re.compile(r"sep@loss=([-\d.]+)mm dia=([\d.]+)mm")

SEEDS = (5, 6, 101, 202)
TREAT = {s: ROOT / f"logs/p120/mf60_s{s}.log" for s in SEEDS}
CTRL = {
    5: ROOT / "logs/p92/C5.log",
    6: ROOT / "logs/p92/C6.log",
    101: ROOT / "logs/p93/C101.log",
    202: ROOT / "logs/p93/C202.log",
}


def read(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    windows, outcomes = {}, {}
    for line in text.splitlines():
        m = WIN.search(line)
        if m:
            windows[(int(m.group(1)), m.group(2))] = (float(m.group(3)), float(m.group(4)))
        m = OUT.search(line)
        if m:
            outcomes[(int(m.group(1)), m.group(2))] = (
                m.group(3) == "True",
                m.group(4) == "True",
            )
    placed = sorted(
        windows[k][1] for k in windows if outcomes.get(k, (False, False))[1]
    )
    intervals = [b - a for a, b in zip(placed, placed[1:])]
    failures = [k for k, v in outcomes.items() if not v[1]]
    carries = [tuple(m.groups()) for m in CARRY.finditer(text)]
    crush = [tuple(float(x) for x in m.groups()) for m in CRUSH.finditer(text)]
    return {
        "attempts": len(windows),
        "placed": len(placed),
        "intervals": intervals,
        "failures": failures,
        "carries": carries,
        "crush": crush,
        "text": text,
    }


def fisher(a, b, c, d):
    """Two-sided Fisher exact for [[a,b],[c,d]]."""
    n = a + b + c + d
    def p(a, b, c, d):
        return (
            math.comb(a + b, a)
            * math.comb(c + d, c)
        ) / math.comb(n, a + c)
    p0 = p(a, b, c, d)
    total = 0.0
    for i in range(0, min(a + b, a + c) + 1):
        j = a + c - i
        if 0 <= j <= c + d and 0 <= (a + b - i) <= a + b:
            pi = p(i, a + b - i, j, c + d - j)
            if pi <= p0 + 1e-12:
                total += pi
    return min(1.0, total)


def main() -> int:
    rows = []
    print("P120 - the 60 N jaw vs the shipped 10 N cap (two-line, 20 attempts/seed)")
    print(f"{'seed':>5} {'ctrl':>10} {'60N':>10}")
    tp = cp = 0
    for s in SEEDS:
        t = read(TREAT[s])
        c = read(CTRL[s])
        tp += t["placed"]
        cp += c["placed"]
        rows.append((s, c, t))
        print(f"{s:>5} {c['placed']:>4}/20 {t['placed']:>7}/20")
    print(f"{'pooled':>5} {cp:>4}/80 {tp:>7}/80   Fisher p = {fisher(tp, 80-tp, cp, 80-cp):.4f}")
    print()
    print(f"{'seed':>5} {'dnf':>5} {'noElig':>7} {'cnp':>5} | interval mean/p50/p90 (60N) | ctrl")
    for s, c, t in rows:
        dnf = t["text"].count("did not follow")
        noe = t["text"].count("no eligible")
        iv = t["intervals"]
        ci = c["intervals"]
        def f(v):
            if not v:
                return "n/a"
            return (f"{st.mean(v):.2f}/{st.median(v):.2f}/"
                    f"{sorted(v)[int(0.9*(len(v)-1))]:.2f}")
        print(f"{s:>5} {dnf:>5} {noe:>7} {len(t['failures']):>5} | "
              f"{f(iv)} | {f(ci)}")
    print()
    print("failure classes (60 N):")
    for s, c, t in rows:
        notes = {}
        for line in t["text"].splitlines():
            if "notes=[" in line and "placed=False" in line:
                for key in ("fruit did not follow the gripper", "fell off the line",
                            "no firable", "timeout", "did not land"):
                    if key in line:
                        notes[key] = notes.get(key, 0) + 1
        print(f"  seed {s}: {notes or 'none'}")
    print()
    print("crush guard (sep@loss - dia, must be >= -15 mm):")
    worst = []
    for s, c, t in rows:
        for sep, dia in t["crush"]:
            worst.append((sep - dia, s, sep, dia))
    if worst:
        worst.sort()
        print(f"  {len(worst)} rows; worst = {worst[0][0]:+.1f} mm "
              f"(seed {worst[0][1]}, sep {worst[0][2]} mm, dia {worst[0][3]} mm)")
        bad = [w for w in worst if w[0] < -15.0]
        print(f"  legs below -15 mm: {len(bad)}")
    else:
        print("  no sep@loss rows (FRUIT_CARRY_DIAG?)")
    print()
    print("escape census (clean_slip_max > 100 mm on a carry leg):")
    for s, c, t in rows:
        esc = [c for c in t["carries"] if float(c[4]) > 100.0]
        print(f"  seed {s}: {len(esc)}/{len(t['carries'])} legs, "
              f"max {max((float(c[4]) for c in t['carries']), default=0):.0f} mm")
    print()
    print("landing (place trace):")
    for s, c, t in rows:
        on = len(re.findall(r"on_belt=1", t["text"]))
        off = len(re.findall(r"on_belt=0", t["text"]))
        print(f"  seed {s}: on_belt 1 = {on}, 0 = {off}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
