#!/usr/bin/env python3
"""P47 phase 1: the pre-contact acquisition census (offline, read-only).

Parses the existing scripted logs and tabulates, per battery:

  * the two `closing anyway` rows (the fingertip branch and the axis branch),
    their values, and the outcome of the attempt they belong to;
  * the *real* pre-close error on the never-stop line - the
    `dynamic catch-up: residual=...` row printed by the catch-up loop - and the
    same outcome split;
  * the `[carry]` onset fields (`contacts@onset`, `gap_start`) where the diag is
    on.

No simulator, no `src/` edit: this only reads logs that already exist.

Attribution rules
-----------------
single-arm (`[run] attempt N: picking` ... `[run] attempt N: grasped=`)
    exact: a row belongs to the open attempt.
two-line (`[biarm] result <side> ...`, no start row)
    ordinal: the k-th row of a kind is paired with the k-th result row. Each
    attempt prints exactly one of each, and the row order inside an attempt
    block is fingertip -> ... -> catch-up -> carry -> result, so the k-th
    pairing reproduces the block order. It is flagged `ordinal` in the output
    because the two arms' blocks interleave and the pairing is not provable
    from the log alone.

Usage: python3 logs/p47/census.py
"""
from __future__ import annotations

import glob
import os
import re
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RE_START = re.compile(r"\[run\] attempt (\d+): picking ")
RE_SKIP = re.compile(r"\[run\] attempt (\d+): no eligible fruit")
RE_RESULT = re.compile(
    r"\[run\] attempt (\d+): grasped=(\w+) placed=(\w+) lift=([-+\d.]+) m "
    r"force=([\d.]+) N notes=\[(.*?)\]"
)
RE_BIARM = re.compile(
    r"\[biarm\] result (left|right) index=(\d+) (\w+) grasped=(\w+) placed=(\w+) "
    r"lift=([-+\d.]+) force=([\d.]+) sim=[\d.]+s notes=\[(.*?)\]"
)
RE_TIP = re.compile(r"openarm fingertips (\d+) mm from the fruit; closing anyway")
RE_AXIS = re.compile(r"hand attitude not settled \(1-cos=([\d.]+)\); closing anyway")
RE_CATCH = re.compile(r"dynamic catch-up: residual=([\d.]+) mm \(tol (\d+) mm\)")
RE_CARRY = re.compile(
    r"\[carry\] (left|right) grasp_lift: .*?force@onset=(\S+?)N sep@onset=(\S+?)mm "
    r"contacts@onset=(\S+) .*?gap_start=(\S+?)mm"
)
RE_SETTLE = re.compile(r"kinematic grip closed to ([\d.]+)cm around a ([\d.]+)cm fruit")

BATTERIES = [
    ("shipped", [
        "logs/p41/p2/accept_profile.log",
        "logs/p39/p3/pear_C.log",
    ]),
    ("P44-speed", sorted(glob.glob("logs/p44/p2/accept_s*.log"))
     + sorted(glob.glob("logs/p44/p2/pear_s*.log"))
     + sorted(glob.glob("logs/p44/p2/twoline_s*.log"))
     + sorted(glob.glob("logs/p44/p2/amend_*.log"))),
    ("P45-mass", sorted(glob.glob("logs/p45/p2/accept_s*.log"))
     + sorted(glob.glob("logs/p45/p2/pear_s*.log"))),
    ("P46-twoline", sorted(glob.glob("logs/p46/p1/twoline_s*.log"))),
]


def pct(vals, q):
    if not vals:
        return float("nan")
    vals = sorted(vals)
    if len(vals) == 1:
        return vals[0]
    k = min(len(vals) - 1, max(0, int(round(q * (len(vals) - 1)))))
    return vals[k]


def parse(path):
    """Return (attempts, rows) for one log.

    attempts: list of dicts {idx, species, outcome, tip, axis, catch, carry, settle}
      outcome in {'placed', 'cnp', 'nograsp', 'skip', 'open'}
    rows: the raw rows in order, each {kind, value, arm}
    """
    attempts = []
    rows = []
    cur = None          # the open single-arm attempt dict
    by_idx = {}
    biarm_results = []
    biarm_rows = []
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            if "[fruit]" not in line:
                continue
            m = RE_START.search(line)
            if m:
                idx = int(m.group(1))
                sp = re.search(r"picking (\w+)", line)
                cur = {
                    "idx": idx, "species": sp.group(1) if sp else "?",
                    "outcome": "open", "tip": [], "axis": [], "catch": [],
                    "carry": [], "settle": [],
                }
                attempts.append(cur)
                by_idx[idx] = cur
                continue
            m = RE_SKIP.search(line)
            if m:
                idx = int(m.group(1))
                cur = {"idx": idx, "species": "-", "outcome": "skip",
                       "tip": [], "axis": [], "catch": [], "carry": [], "settle": []}
                attempts.append(cur)
                by_idx[idx] = cur
                continue
            m = RE_RESULT.search(line)
            if m:
                idx = int(m.group(1))
                a = by_idx.get(idx)
                if a is not None:
                    g = m.group(2) == "True"
                    p = m.group(3) == "True"
                    a["outcome"] = "placed" if p else ("cnp" if g else "nograsp")
                    a["notes"] = m.group(6)
                cur = None
                continue
            m = RE_TIP.search(line)
            if m:
                v = int(m.group(1))
                rows.append({"kind": "tip", "value": v, "arm": None})
                if cur is not None:
                    cur["tip"].append(v)
                continue
            m = RE_AXIS.search(line)
            if m:
                v = float(m.group(1))
                rows.append({"kind": "axis", "value": v, "arm": None})
                if cur is not None:
                    cur["axis"].append(v)
                continue
            m = RE_CATCH.search(line)
            if m:
                v = float(m.group(1))
                rows.append({"kind": "catch", "value": v, "arm": None})
                if cur is not None:
                    cur["catch"].append(v)
                continue
            m = RE_CARRY.search(line)
            if m:
                rec = {"arm": m.group(1), "force": m.group(2), "sep": m.group(3),
                       "contacts": m.group(4), "gap_start": m.group(5)}
                rows.append({"kind": "carry", "value": rec, "arm": m.group(1)})
                if cur is not None:
                    cur["carry"].append(rec)
                continue
            m = RE_SETTLE.search(line)
            if m:
                rec = (float(m.group(1)) * 10.0, float(m.group(2)) * 10.0)
                rows.append({"kind": "settle", "value": rec, "arm": None})
                if cur is not None:
                    cur["settle"].append(rec)
                continue
            m = RE_BIARM.search(line)
            if m:
                biarm_results.append({
                    "arm": m.group(1), "index": int(m.group(2)),
                    "species": m.group(3), "outcome": ("placed" if m.group(5) == "True"
                                                       else ("cnp" if m.group(4) == "True"
                                                             else "nograsp")),
                    "notes": m.group(8),
                })
                continue
    return attempts, rows, biarm_results


def ordinal_pair(rows, results, kind):
    """Pair the k-th row of `kind` with the k-th result (two-line ordinal rule)."""
    vals = [r for r in rows if r["kind"] == kind]
    pairs = []
    for k, r in enumerate(vals):
        if k < len(results):
            pairs.append((r, results[k]))
        else:
            pairs.append((r, None))
    return pairs


def summarise(name, paths):
    out = {
        "name": name, "paths": [], "n_attempts": 0, "placed": 0, "cnp": 0,
        "nograsp": 0, "skip": 0, "open": 0,
        "tip": [], "axis": [], "catch": [], "catch_pairs": [],
        "carry": [], "settle": [], "tippairs": [], "bad": [],
    }
    for rel in paths:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            print(f"  MISSING {rel}", file=sys.stderr)
            continue
        attempts, rows, biarm = parse(p)
        if not attempts and not biarm:
            continue  # a driver stub, not a measured arm
        out["paths"].append(rel)
        is_biarm = bool(biarm)
        if is_biarm:
            # ordinal pairing: use the catch-up rows and the tip rows
            out["tippairs"] += ordinal_pair(rows, biarm, "tip")
            out["catch_pairs"] += ordinal_pair(rows, biarm, "catch")
            out["tip"] += [r["value"] for r in rows if r["kind"] == "tip"]
            out["axis"] += [r["value"] for r in rows if r["kind"] == "axis"]
            out["catch"] += [r["value"] for r in rows if r["kind"] == "catch"]
            for r in rows:
                if r["kind"] == "carry":
                    out["carry"].append(r["value"])
            for k, r in enumerate([r for r in rows if r["kind"] == "catch"]):
                if r["value"] > 6.0:
                    res = biarm[k] if k < len(biarm) else None
                    out["bad"].append((rel, r["value"], res["outcome"] if res else "?",
                                       res["species"] if res else "?",
                                       res["arm"] if res else "?"))
            for res in biarm:
                out["n_attempts"] += 1
                key = {"placed": "placed", "cnp": "cnp", "nograsp": "nograsp"}[res["outcome"]]
                out[key] += 1
        else:
            for a in attempts:
                out["n_attempts"] += 1
                if a["outcome"] in ("placed", "cnp", "nograsp", "skip"):
                    out[a["outcome"]] += 1
                else:
                    out["open"] += 1
                for v in a["tip"]:
                    out["tip"].append(v)
                    out["tippairs"].append(({"value": v}, a))
                for v in a["axis"]:
                    out["axis"].append(v)
                for v in a["catch"]:
                    out["catch"].append(v)
                    out["catch_pairs"].append(({"value": v}, a))
                    if v > 6.0:
                        out["bad"].append((rel, v, a["outcome"], a["species"], "-"))
                out["carry"] += a["carry"]
                out["settle"] += a["settle"]
    return out


def fmt(vals):
    if not vals:
        return "     -      "
    return (f"n={len(vals):<3d} min={min(vals):6.1f} p50={pct(vals, .5):6.1f} "
            f"p90={pct(vals, .9):6.1f} max={max(vals):6.1f}")


def outcome_counts(pairs, pred):
    """(hits, placed, cnp, nograsp, skip) over pairs where pred(value) is true."""
    hit = [p for p in pairs if p[0] is not None and pred(p[0]["value"])]
    c = {"placed": 0, "cnp": 0, "nograsp": 0, "skip": 0, "open": 0, "other": 0}
    for _, a in hit:
        if a is None:
            c["other"] += 1
        else:
            c[a["outcome"]] = c.get(a["outcome"], 0) + 1
    return len(hit), c


def fisher_2x2(a, b, c, d):
    """Two-sided Fisher exact p for [[a,b],[c,d]] (exact, small tables)."""
    from math import comb
    n = a + b + c + d
    r1, r2 = a + b, c + d
    c1 = a + c
    def p_tab(x):
        return comb(r1, x) * comb(r2, c1 - x) / comb(n, c1)
    p0 = p_tab(a)
    lo, hi = max(0, c1 - r2), min(r1, c1)
    return sum(p_tab(x) for x in range(lo, hi + 1) if p_tab(x) <= p0 + 1e-12)


def main():
    print("P47 phase 1 - the pre-contact acquisition census")
    print("=" * 78)
    allsum = {}
    for name, paths in BATTERIES:
        s = summarise(name, paths)
        allsum[name] = s
        print(f"\n## {name}  ({len(s['paths'])} logs)")
        for rel in s["paths"]:
            print(f"   - {rel}")
        print(f"   attempts {s['n_attempts']}: placed {s['placed']} cnp {s['cnp']} "
              f"no-grasp {s['nograsp']} skip {s['skip']} open {s['open']}")
        print(f"   [fingertip rows] {fmt(s['tip'])}")
        print(f"   [axis rows]      {fmt(s['axis'])}   n={len(s['axis'])}")
        print(f"   [catch-up resid] {fmt(s['catch'])}")
        for lab, pred in (("catch>6", lambda v: v > 6.0),
                          ("catch>20", lambda v: v > 20.0),
                          ("catch>50", lambda v: v > 50.0),
                          ("tip>60", lambda v: v > 60.0),
                          ("tip>62", lambda v: v > 62.0)):
            pairs = s["catch_pairs"] if lab.startswith("catch") else s["tippairs"]
            n, c = outcome_counts(pairs, pred)
            print(f"     {lab:<10s} rows={n:<3d} placed={c['placed']:<3d} "
                  f"cnp={c['cnp']:<3d} nograsp={c['nograsp']:<3d} skip={c['skip']:<3d} "
                  f"open={c['open']:<3d} unpaired={c['other']}")
        # the complement
        for lab, pred in (("catch<=6", lambda v: v <= 6.0), ("tip<=60", lambda v: v <= 60.0)):
            pairs = s["catch_pairs"] if lab.startswith("catch") else s["tippairs"]
            n, c = outcome_counts(pairs, pred)
            print(f"     {lab:<10s} rows={n:<3d} placed={c['placed']:<3d} "
                  f"cnp={c['cnp']:<3d} nograsp={c['nograsp']:<3d} skip={c['skip']:<3d} "
                  f"open={c['open']:<3d} unpaired={c['other']}")
        # the distance bands (the print's own number)
        print("     -- the print's distance, as bands (all rows > 50 mm) --")
        for lab, pred in (("<=59", lambda v: v <= 59),
                          ("60-61", lambda v: 60 <= v <= 61),
                          ("62", lambda v: v == 62),
                          (">=63", lambda v: v >= 63)):
            n, c = outcome_counts(s["tippairs"], pred)
            print(f"     tip {lab:<6s} rows={n:<3d} placed={c['placed']:<3d} "
                  f"cnp={c['cnp']:<3d} nograsp={c['nograsp']:<3d} skip={c['skip']:<3d}")
        if s["bad"]:
            print("     -- every row above the 6 mm catch-up tolerance --")
            for b in s["bad"]:
                print(f"       {b[0].split('/')[-1]:<24s} residual={b[1]:7.1f} mm  "
                      f"outcome={b[2]:<8s} {b[3]:<10s} arm={b[4]}")
        # carry onset
        if s["carry"]:
            zero = [c for c in s["carry"] if c["contacts"] == "0"]
            none = [c for c in s["carry"] if c["contacts"] in ("None", "n/a")]
            print(f"   [carry] rows {len(s['carry'])}: contacts@onset==0 (explicit) "
                  f"{len(zero)}; onset not detected {len(none)}")
        if s["settle"]:
            print(f"   [kinematic grip] rows {len(s['settle'])}")
    print("\n" + "=" * 78)
    print("POOLED (all batteries)")
    tip = [v for s in allsum.values() for v in s["tip"]]
    ax = [v for s in allsum.values() for v in s["axis"]]
    ca = [v for s in allsum.values() for v in s["catch"]]
    print(f"   fingertip rows {len(tip)}: {fmt(tip)}")
    print(f"   axis rows      {len(ax)}: {fmt(ax)}")
    print(f"   catch-up rows  {len(ca)}: {fmt(ca)}")
    allpairs, alltip = [], []
    P = {"placed": 0, "cnp": 0, "nograsp": 0, "skip": 0, "open": 0}
    for name, s in allsum.items():
        allpairs += s["catch_pairs"]
        alltip += s["tippairs"]
        for k in P:
            P[k] += s[k]
    print(f"   outcomes {P}")
    # the 2x2 the census turns on
    n_hi, c_hi = outcome_counts(allpairs, lambda v: v > 6.0)
    n_lo, c_lo = outcome_counts(allpairs, lambda v: v <= 6.0)
    print(f"   catch-up > 6 mm : {n_hi} rows -> placed {c_hi['placed']} "
          f"cnp {c_hi['cnp']} nograsp {c_hi['nograsp']} skip {c_hi['skip']} "
          f"(no-grasp rate {c_hi['nograsp'] / max(n_hi, 1):.0%})")
    print(f"   catch-up <= 6 mm: {n_lo} rows -> placed {c_lo['placed']} "
          f"cnp {c_lo['cnp']} nograsp {c_lo['nograsp']} skip {c_lo['skip']} "
          f"(no-grasp rate {c_lo['nograsp'] / max(n_lo, 1):.1%})")
    p = fisher_2x2(c_hi["nograsp"], n_hi - c_hi["nograsp"],
                   c_lo["nograsp"], n_lo - c_lo["nograsp"])
    print(f"   Fisher exact (nograsp | residual>6 vs <=6): p = {p:.3g}")
    n_hi2, c_hi2 = outcome_counts(alltip, lambda v: v >= 62)
    n_lo2, c_lo2 = outcome_counts(alltip, lambda v: v <= 60)
    print(f"   print >= 62 mm  : {n_hi2} rows -> placed {c_hi2['placed']} "
          f"cnp {c_hi2['cnp']} nograsp {c_hi2['nograsp']}")
    print(f"   print <= 60 mm  : {n_lo2} rows -> placed {c_lo2['placed']} "
          f"cnp {c_lo2['cnp']} nograsp {c_lo2['nograsp']}")
    p2 = fisher_2x2(c_hi2["nograsp"], n_hi2 - c_hi2["nograsp"],
                    c_lo2["nograsp"], n_lo2 - c_lo2["nograsp"])
    print(f"   Fisher exact (nograsp | print>=62 vs <=60): p = {p2:.3g}")


if __name__ == "__main__":
    main()
