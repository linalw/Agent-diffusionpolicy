#!/usr/bin/env python3
"""P111 report - the compliant closure: centring, clean enclosure, class, count.

One row per cell, parsed from the scripted single-arm cells' own lines:

* `[stats]`                 -> attempts, placed, s/attempt, sim
* `[run] attempt N: ...`    -> per-attempt outcomes and the failure notes
* `[cage] ... off0=.. off=.. pads=k/4 ..` -> **the centring instrument** (the
                               payload's distance from the ring's axis at the
                               close's start and end), the pad count, the bat
* `[carry] ... force_min=..` -> the loaded-slide guard on the carried legs
* `[task] place trace`       -> the landing guard (`on_belt` on payload-present rows)
* `[motion] approach ... end` -> the descent's shortfall, joined to each `[cage]`
                               row by index for P110's jam split
* `[cage] hold`              -> the hard stop's own row (a field of the arm)

P110's enclosure split is applied verbatim (`clean` / `jam` / `over-closure`), so
the phase's primary endpoint is the same statistic as the record's.

Usage:
    python3 logs/p111/p111_report.py logs/p111/{C,R,T1,T2}_s{5,6,101,202}.log
    python3 logs/p111/p111_report.py --same a.log b.log [--drop '[cage],[cycle]']
"""

from __future__ import annotations

import argparse
import collections
import os
import re
import sys

CAP = 4.90
CAGE = re.compile(
    r"\[cage\] idx=(?P<idx>\d+) arm=(?P<arm>\w+) species=(?P<sp>\w+) "
    r"dia=(?P<dia>\d+)mm approach=(?P<appr>\d+)t clr=(?P<clr>[-+0-9.]+)mm "
    r"aper_min=(?P<apermin>[0-9.]+)mm close=(?P<close>\d+)t "
    r"bat=(?P<bat>[-+0-9.]+)mm bat_rel=(?P<batrel>[-+0-9.]+)mm "
    r"(?:off0=(?P<off0>[-+0-9.]+)mm off=(?P<off>[-+0-9.]+)mm )?"
    r"pads=(?P<pads>\d)/4 .*?F=(?P<F>[-+0-9.]+)N aper=(?P<aper>[0-9.]+)mm"
)
HOLD = re.compile(r"\[cage\] (?P<side>\w+): hard stop at the close \(k (?P<k0>\d+) -> (?P<k1>\d+)")
RUN = re.compile(r"\[run\] attempt (?P<i>\d+): (?P<body>.*)")
STATS = re.compile(
    r"\[stats\] attempts=(?P<att>\d+) successes=(?P<succ>\d+) diverted=(?P<div>\d+) "
    r"success_rate=(?P<rate>\d+)% sim=(?P<sim>[0-9.]+)s total, (?P<sa>[0-9.]+)s/attempt"
)
CARRY = re.compile(
    r"\[carry\] (?P<leg>\w+) .*?force_min=(?P<fmin>[-+0-9.]+)N"
)
LAND = re.compile(
    r"\[task\]\s+place trace (?P<arm>\w+):.*release_bottom=(?P<rb>[-+0-9.]+)mm"
    r".*on_belt=(?P<ob>\w+)"
)
DESC = re.compile(r"\[motion\] approach\(cartesian\): (?P<len>[0-9.]+) cm.*end=(?P<end>[0-9.]+) mm")
SEP = re.compile(r"\[carry\] place\d* .*?sep@loss=(?P<sep>[-+0-9.]+)mm")


def read(path: str) -> dict:
    text = open(path, errors="replace").read()
    out = {
        "path": path, "tries": 0, "placed": 0, "notes": collections.Counter(),
        "cage": [], "carry": 0, "fmin0": 0, "land": [0, 0], "desc": [],
        "sa": float("nan"), "sim": float("nan"), "att": 0, "hold": 0,
        "crush": 0,
    }
    for line in text.splitlines():
        m = STATS.search(line)
        if m:
            out.update(att=int(m["att"]), sa=float(m["sa"]), sim=float(m["sim"]))
            continue
        m = HOLD.search(line)
        if m:
            out["hold"] += 1
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
                    out["notes"][re.sub(r"\d+", "N", note.strip())] += 1
            continue
        m = CAGE.search(line)
        if m:
            out["cage"].append({k: (v if v is None else v) for k, v in m.groupdict().items()})
            continue
        m = CARRY.search(line)
        if m:
            out["carry"] += 1
            if float(m["fmin"]) == 0.0:
                out["fmin0"] += 1
            continue
        m = SEP.search(line)
        if m:
            # P76's crush rule needs `sep@loss - dia`; `dia` comes from the cage row
            out.setdefault("sep_loss", []).append(float(m["sep"]))
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
    return out


def cage_split(d: dict) -> dict:
    """P110's split: jam / over-closure / clean, plus the centring medians."""
    rows = d["cage"]
    # the descent's `end=` is printed once per attempt, the `[cage]` row once per
    # cage attempt: index-join them (a cage attempt IS an attempt)
    ends = [e for _, e in d["desc"]]
    for i, r in enumerate(rows):
        r["end"] = ends[i] if i < len(ends) else float("nan")
        r["dia"] = int(r["dia"])
        r["pads"] = int(r["pads"])
        r["F"] = float(r["F"])
        r["aper"] = float(r["aper"])
        r["clr"] = float(r["clr"])
        r["bat"] = float(r["bat"])
        r["batrel"] = float(r["batrel"])
        for key in ("off0", "off"):
            r[key] = float(r[key]) if r[key] is not None else float("nan")
    clean = [r for r in rows
             if r["pads"] >= 3 and (r["end"] or 0) <= 15.0
             and r["aper"] >= r["dia"] - 4.0 and r["F"] <= 4 * CAP * 1.5]
    jam = [r for r in rows if r["pads"] >= 3 and (r["end"] or 0) > 15.0]
    crush = [r for r in rows if r["pads"] >= 3 and r not in clean and r not in jam]
    offs = [r["off"] for r in rows if r["off"] == r["off"]]
    off0 = [r["off0"] for r in rows if r["off0"] == r["off0"]]
    return {
        "n": len(rows), "clean": len(clean), "jam": len(jam), "crush": len(crush),
        "ge3": sum(1 for r in rows if r["pads"] >= 3),
        "two": sum(1 for r in rows if r["pads"] == 2),
        "nc": sum(1 for r in rows if int(r.get("nc", 0) or 0) == 1)
        + sum(1 for r in rows if r["pads"] == 0),
        "off_p50": _pctl(offs, 50), "off_p90": _pctl(offs, 90),
        "doff_p50": _pctl(
            [r["off"] - r["off0"] for r in rows
             if r["off"] == r["off"] and r["off0"] == r["off0"]
             and abs(r["off"] - r["off0"]) < 0.05], 50),
        "off0_p50": _pctl(off0, 50),
        "off_min": min(offs) if offs else float("nan"),
        "bat_p50": _pctl([r["bat"] for r in rows], 50),
        "batrel_p90": _pctl([r["batrel"] for r in rows], 90),
    }


def _pctl(v, q):
    v = sorted(v)
    if not v:
        return float("nan")
    k = min(len(v) - 1, max(0, int(round((q / 100.0) * (len(v) - 1)))))
    return v[k]


def table(paths: list[str]) -> None:
    print(f"{'cell':10s} {'att':>4} {'plc':>4} {'s/att':>6} {'hold':>4} "
          f"{'cage':>4} {'cln':>4} {'jam':>4} {'ovc':>4} {'p2':>3} {'nc':>3} "
          f"{'off0':>6} {'off':>6} {'dOff':>6} {'bat':>7} {'fmin0':>5} {'land':>7}")
    print("-" * 118)
    agg: dict[str, dict] = {}
    for p in paths:
        d = read(p)
        c = cage_split(d)
        land = f"{d['land'][1]}/{d['land'][0]}" if d["land"][0] else "-"
        arm = os.path.basename(p).split("_s")[0]
        print(
            f"{os.path.basename(p)[:-4]:10s} {d['tries']:>4} {d['placed']:>4} "
            f"{d['sa']:>6.2f} {d['hold']:>4} {c['n']:>4} {c['clean']:>4} {c['jam']:>4} "
            f"{c['crush']:>4} {c['two']:>3} {c['nc']:>3} "
            f"{c['off0_p50']:>6.1f} {c['off_p50']:>6.1f} {c['doff_p50']:>+6.1f} "
            f"{c['bat_p50']:>7.1f} {d['fmin0']:>5} {land:>7}"
        )
        a = agg.setdefault(
            arm,
            {
                "att": 0, "plc": 0, "n": 0, "clean": 0, "jam": 0, "crush": 0,
                "two": 0, "nc": 0, "hold": 0, "fmin0": 0, "land_n": 0, "land_ok": 0,
                "notes": collections.Counter(), "off0s": [], "offs": [], "cells": 0,
            },
        )
        a["att"] += d["tries"]
        a["plc"] += d["placed"]
        a["n"] += c["n"]
        a["clean"] += c["clean"]
        a["jam"] += c["jam"]
        a["crush"] += c["crush"]
        a["two"] += c["two"]
        a["nc"] += c["nc"]
        a["hold"] += d["hold"]
        a["fmin0"] += d["fmin0"]
        a["land_n"] += d["land"][0]
        a["land_ok"] += d["land"][1]
        a["notes"].update(d["notes"])
        a["cells"] += 1
        if c["off_p50"] == c["off_p50"]:
            a["offs"].append(c["off_p50"])
            a["off0s"].append(c["off0_p50"])
    print("-" * 118)
    for arm, a in sorted(agg.items()):
        m = max(len(a["offs"]), 1)
        print(
            f"{arm:10s} {a['att']:>4} {a['plc']:>4} {'':>6} {a['hold']:>4} "
            f"{a['n']:>4} {a['clean']:>4} {a['jam']:>4} {a['crush']:>4} {a['two']:>3} "
            f"{a['nc']:>3} {sum(a['off0s']) / m:>6.1f} {sum(a['offs']) / m:>6.1f} "
            f"{'':>6} {'':>7} {a['fmin0']:>5} {a['land_ok']}/{a['land_n']}"
        )
        if a["notes"]:
            print(f"{'':10s}   notes: "
                  + ", ".join(f"{k}x{v}" for k, v in a["notes"].most_common(4)))
    print("\n  `off0`/`off` are the payload's distance from the ring's AXIS at the")
    print("  close's start and end [mm]; `dOff` is the median of `off - off0` over the")
    print("  rows that stayed in the ring (|change| < 50 mm) - the centring number;")
    print("  `bat` is the payload's displacement over the close [mm].  `cln`/`jam`/")
    print("  `ovc` are P110's split of `pads >= 3`; `p2` is the V-block mode; `nc` the")
    print("  no-contact class.  `fmin0` counts `[carry] force_min == 0` legs.")


# --------------------------------------------------------------------------- #
# `--same`: the replay guard on the [fruit] stream
# --------------------------------------------------------------------------- #
def _norm(line: str) -> str:
    line = line.rstrip("\n")
    if line.startswith("[fruit] "):
        line = line[len("[fruit] "):]
    return line


def same(a: str, b: str, drop: list[str]) -> int:
    def keep(line: str) -> bool:
        return not any(tok and tok in line for tok in drop)

    def stream(path):
        # the tree's convention: the `[fruit]` stream *is* the physics record (the
        # startup's timestamps/PIDs make a whole-file diff meaningless)
        return [
            _norm(ln)
            for ln in open(path, errors="replace")
            if ln.startswith("[fruit] ") and keep(ln)
        ]

    ha, hb = stream(a), stream(b)
    n = min(len(ha), len(hb))
    first = next((i for i in range(n) if ha[i] != hb[i]), None)
    print(f"{os.path.basename(a)} ({len(ha)} lines) vs {os.path.basename(b)} ({len(hb)})")
    print(f"  dropped: {drop}")
    if first is None and len(ha) == len(hb):
        print(f"  IDENTICAL: {len(ha)}/{len(hb)} lines")
        return 0
    print(f"  DIFFERS at line {first}:")
    if first is not None:
        print(f"    a: {ha[first][:150]}")
        print(f"    b: {hb[first][:150]}")
    print(f"  identical prefix: {first if first is not None else n}"
          f"/{max(len(ha), len(hb))}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="*")
    ap.add_argument("--same", nargs=2, metavar=("A", "B"))
    ap.add_argument("--drop", default="")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.same:
        return same(args.same[0], args.same[1],
                    [t for t in args.drop.replace(",", " ").split() if t])
    if not args.logs:
        ap.error("no logs given")
    missing = [p for p in args.logs if not os.path.exists(p)]
    if missing:
        print(f"missing: {missing}", file=sys.stderr)
        return 2
    table(args.logs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
