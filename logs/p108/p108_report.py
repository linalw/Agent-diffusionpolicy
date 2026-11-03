#!/usr/bin/env python3
"""P108 report - the enclosure / no-contact / placed / density table.

One row per cell, parsed from the scripted single-arm cells' own lines:

* `[stats]`                      -> attempts, placed, s/attempt, sim
* `[run] attempt N: ... placed=` -> per-attempt outcomes and the failure notes
* `[cage] ... pads=k/4 ... `     -> **the enclosure rate** (P107's real endpoint),
                                    the no-contact class and the batting
* `[carry] ... force_min= .. `   -> the loaded-slide guard on the carried legs
* `[task] place trace ... on_belt=` -> the landing guard (payload-present rows)
* `[motion] approach ... end=`   -> the descent budgets (the motion gate's input)
* `[task] ... no eligible fruit` / attempts < ATTEMPTS -> the starved slots

`--same` compares two cells' `[fruit]` streams with a phase's rows dropped.
"""

from __future__ import annotations

import argparse
import collections
import os
import re
import sys

CAGE = re.compile(
    r"\[cage\] idx=(?P<idx>\d+) arm=(?P<arm>\w+) .*?dia=(?P<dia>\d+)mm "
    r"approach=(?P<appr>\d+)t clr=(?P<clr>[-+0-9.]+)mm .*?close=(?P<close>\d+)t "
    r"bat=(?P<bat>[-+0-9.]+)mm bat_rel=(?P<batrel>[-+0-9.]+)mm "
    r"pads=(?P<pads>\d)/4 .*?F=(?P<F>[-+0-9.]+)N .*?no_contact=(?P<nc>\d)"
)
RUN = re.compile(r"\[run\] attempt (?P<i>\d+): (?P<body>.*)")
STATS = re.compile(
    r"\[stats\] attempts=(?P<att>\d+) successes=(?P<succ>\d+) diverted=(?P<div>\d+) "
    r"success_rate=(?P<rate>\d+)% sim=(?P<sim>[0-9.]+)s total, (?P<sa>[0-9.]+)s/attempt"
)
CARRY = re.compile(r"\[carry\] (?P<leg>\w+) .*?force_min=(?P<fmin>[-+0-9.]+)N")
LAND = re.compile(r"\[task\]\s+place trace (?P<arm>\w+):.*release_bottom=(?P<rb>[-+0-9.]+)mm.*on_belt=(?P<ob>\w+)")
DESC = re.compile(r"\[motion\] approach\(cartesian\): (?P<len>[0-9.]+) cm.*end=(?P<end>[0-9.]+) mm")


def read(path: str) -> dict:
    with open(path, errors="replace") as fh:
        lines = fh.readlines()
    out = {"path": path, "tries": 0, "placed": 0, "notes": collections.Counter(),
           "cage": [], "carry_n": 0, "fmin0": 0, "land": [0, 0], "desc": [],
           "sa": float("nan"), "sim": float("nan"), "att": 0, "succ": 0, "div": 0,
           "cycle": []}
    for line in lines:
        m = STATS.search(line)
        if m:
            out.update(att=int(m["att"]), succ=int(m["succ"]), div=int(m["div"]),
                       sa=float(m["sa"]), sim=float(m["sim"]))
            continue
        m = RUN.search(line)
        if m:
            body = m["body"]
            if "picking" in body:
                out["tries"] += 1
                continue
            if "placed=True" in body:
                out["placed"] += 1
            for note in re.findall(r"notes=\[(.*?)\]", body):
                if note.strip():
                    # digit-normalise (the tree's own rule: any new note is a new key)
                    out["notes"][re.sub(r"\d+", "N", note.strip())] += 1
            continue
        m = CAGE.search(line)
        if m:
            out["cage"].append({k: (int(v) if v.isdigit() else v) for k, v in m.groupdict().items()})
            continue
        m = CARRY.search(line)
        if m:
            out["carry_n"] += 1
            if float(m["fmin"]) == 0.0:
                out["fmin0"] += 1
            continue
        m = LAND.search(line)
        if m:
            out["land"][0] += 1
            out["land"][1] += int(m["ob"] == "True")
            continue
        m = DESC.search(line)
        if m:
            out["desc"].append((float(m["len"]), float(m["end"])))
            continue
        if "[cycle] attempt" in line:
            out["cycle"].append(line.strip())
    return out


def cage_stats(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:
        return {"n": 0}
    enc = collections.Counter(int(r["pads"]) for r in rows)
    return {
        "n": n,
        "ge3": sum(1 for r in rows if int(r["pads"]) >= 3),
        "nopad": sum(1 for r in rows if int(r["pads"]) == 0),
        "nc": sum(1 for r in rows if int(r["nc"]) == 1),
        "clr_neg": sum(1 for r in rows if float(r["clr"]) < 0),
        "batrel_p50": sorted(float(r["batrel"]) for r in rows)[n // 2],
        "batrel_p90": sorted(float(r["batrel"]) for r in rows)[int(0.9 * (n - 1))],
        "enc": enc,
    }


def table(paths: list[str], names: list[str]) -> None:
    print(f"{'cell':10s} {'att':>4} {'placed':>6} {'s/att':>6} {'cage':>4} "
          f"{'encl>=3':>8} {'no-ct':>6} {'clr<0':>6} {'fmin0':>6} {'land':>7}  notes")
    for name, p in zip(names, paths):
        d = read(p)
        c = cage_stats(d["cage"])
        land = f"{d['land'][1]}/{d['land'][0]}" if d["land"][0] else "-"
        nt = ", ".join(f"{k}x{v}" for k, v in d["notes"].most_common(3))
        print(
            f"{name:10s} {d['tries']:>4} {d['placed']:>6} {d['sa']:>6.2f} "
            f"{c.get('n', 0):>4} {c.get('ge3', 0):>4}/{c.get('n', 0):<3} "
            f"{c.get('nc', 0):>6} {c.get('clr_neg', 0):>6} "
            f"{d['fmin0']:>2}/{d['carry_n']:<3} {land:>7}  {nt}"
        )


def same(a: str, b: str, drop: list[str]) -> int:
    def keep(line: str) -> bool:
        if "[fruit]" not in line:
            return False
        return not any(tok in line for tok in drop)

    la = [l for l in open(a, errors="replace") if keep(l)]
    lb = [l for l in open(b, errors="replace") if keep(l)]
    ok = sum(1 for x, y in zip(la, lb) if x == y)
    print(f"{len(la)} vs {len(lb)} lines: {ok} identical")
    for i, (x, y) in enumerate(zip(la, lb)):
        if x != y:
            print(f"first difference at {i}:")
            print(f"  A {x.strip()[:150]}")
            print(f"  B {y.strip()[:150]}")
            break
    return 0 if ok == min(len(la), len(lb)) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cells", nargs="*")
    ap.add_argument("--same", nargs=2, metavar=("A", "B"))
    ap.add_argument("--drop", default="[cage],[ftrace],[cycle],[release] trace,place trace,[carry]")
    args = ap.parse_args()
    if args.same:
        return same(args.same[0], args.same[1], [t for t in args.drop.split(",") if t])
    names = [os.path.basename(p).replace(".log", "") for p in args.cells]
    table(args.cells, names)
    print()
    for name, p in zip(names, args.cells):
        d = read(p)
        c = cage_stats(d["cage"])
        if c.get("n"):
            print(f"{name}: enclosure histogram {dict(sorted(c['enc'].items()))}; "
                  f"clr<0 {c['clr_neg']}/{c['n']}; no-contact {c['nc']}/{c['n']}; "
                  f"bat_rel p50={c['batrel_p50']:+.1f} p90={c['batrel_p90']:+.1f} mm")
        if d["desc"]:
            worst = max(e / max(L * 10.0, 1e-9) for L, e in d["desc"])
            print(f"{name}: descents {len(d['desc'])}, end= p50="
                  f"{sorted(e for _, e in d['desc'])[len(d['desc']) // 2]:.1f} mm, "
                  f"worst end/len {worst:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
