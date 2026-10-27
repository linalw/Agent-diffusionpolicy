#!/usr/bin/env python3
"""P49 phase 1: the scripted selector's x-ceiling census (offline, read-only).

Answers, from the existing logs only:

  * the **selection-time x** of the chosen fruit per corpus (and the whole
    *usable* set where the `[bed-sel]` census exists), with the fractions above
    the registered 0.39 / 0.40 / 0.42 ceilings;
  * the **refusal arithmetic**: for each ceiling, how many attempts would refuse
    the chosen fruit, and - where the full live set is in the record - whether a
    next eligible fruit at/above the catch floor and `x <= ceiling` exists, and
    what the substitution would cost in belt travel;
  * the **tail events** (the P48 `|x| >= 0.38` set) and what the record says
    about their alternatives (`queue` at hand-over, and what it does *not* say);
  * the **two-line scope**: its selector returns at `lane`/`prefer_lane` before
    the single-arm rule, so an x-ceiling placed in the scripted single-arm
    branch cannot reach it.

Instrumentation / attribution
-----------------------------
`[bed-sel]` blocks (`FRUIT_BED_DIAG=1`, `tasks.bed_diag_report`) exist on four
logs of this tree's history, all on the shipped acceptance / pear scenarios:
  logs/p43/p2/d0_accept_A_s5.log      shipped farthest-upstream rule, seed 5
  logs/p43/p2/d0_pear_A_s5.log        same, pear supply
  logs/p43/p2/r_accept_B_s5_diag.log  the P43 nearest-above-floor rule (cross-check)
  logs/p43/p2/r_pear_B_s5_diag.log    same, pear

Those are the only logs in the tree with a per-attempt live-set census on the
*shipped* scenario. Every other corpus carries the chosen fruit's x only, in the
attempt's own `wait step=0 fruit_x=` row (the first wait-loop sample, i.e. after
the pre-pose but before the descent; the lateral x does not change during
transport - P38 phase 1 measured exactly 0.000 mm of lateral transport
contribution - so this is the selection-time x to printing precision; the
attempt-0 block of `d0_accept_A_s5` shows the identity: chosen `x=0.365` at
selection, `fruit_x=+0.3653` at the wait loop).

Two-line (interleaved) logs: the arm is recovered from the `wait step=0` row
itself (`station = fruit_y - dy` -> 0.0 left / -0.100 right) and the species
from the k-th `target ... with <arm> arm` row, the same ordinal pairing P48
validated against the `[biarm] result` rows.

Usage: python3 logs/p49/select_census.py > logs/p49/select_census_out.txt
"""
from __future__ import annotations

import glob
import os
import re
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --------------------------------------------------------------------------- #
# rows
# --------------------------------------------------------------------------- #
RE_BED_H = re.compile(
    r"\[bed-sel\] (?:attempt (\d+)|arm=(\w+) slot=(\d+)) t=([\d.]+) "
    r"live=(\d+) on_belt=(\d+) admitted=(\d+) window=(\d+) "
    r"(?:band=(\d+)/(\d+) )?pick=(none|\w+@[-+\d.]+)"
)
RE_BED_R = re.compile(
    r"\[bed-sel\]   (\w+)\s+along=([-+\d.]+) x=([\d.]+) z=([\d.]+) "
    r"r=([\d.]+) grade=(\w) -> (.*)"
)
RE_START = re.compile(r"\[run\] attempt (\d+): picking (\w+)")
RE_SKIP = re.compile(r"\[run\] attempt (\d+): no eligible fruit")
RE_RESULT = re.compile(
    r"\[run\] attempt (\d+): grasped=(\w+) placed=(\w+) lift=([-+\d.]+) m "
    r"force=([\d.]+) N notes=\[(.*?)\]"
)
RE_TARGET = re.compile(
    r"\[task\] target (\w+) \(grade (\w), ([\d.]+) cm\) with (left|right) arm"
)
RE_WAIT0 = re.compile(
    r"\[task\]   wait step=0 fruit_y=([-+\d.]+) fruit_x=([-+\d.]+) "
    r"fruit_z=([-+\d.]+) dy=([-+\d.]+)"
)
RE_HANDOVER = re.compile(
    r"\[task\]   intercept handover: fruit_y=([-+\d.]+) dy=([-+\d.]+) m "
    r"lead=([\d.]+) m at ([-+\d.]+) m/s .*?queue=(\d+)"
)
RE_CATCH = re.compile(r"\[task\] dynamic catch-up: residual=([\d.]+) mm \(tol (\d+) mm\)")
RE_ARRIVED = re.compile(
    r"\[task\] fruit at pick point: dy=([-+\d.]+) m arrived=(\w+) after (\d+) steps"
)
RE_DESCENT = re.compile(
    r"\[task\] dynamic descent: waited (\d+) ticks, intercept=([-+\d.]+) m "
    r"\(station ([-+\d.]+), shift ([-+\d.]+) m\)"
)
RE_APPROACH = re.compile(
    r"\[motion\] approach\(cartesian\): ([\d.]+) cm, (\d+) samples: .*?end=([\d.]+) mm"
)
RE_BIARM = re.compile(
    r"\[biarm\] result (left|right) index=(\d+) (\w+) grasped=(\w+) placed=(\w+)"
)

#: the shipped acceptance / pear chosen-x corpora (the task's list, plus P45 which
#: P48 pooled: the mass cells do not move the supply's x, so they are an
#: independent draw of the same selection population).
CORPORA = [
    ("shipped", [
        "logs/p39/p3/accept_C.log",
        "logs/p39/p3/pear_C.log",
        "logs/p41/p2/accept_profile.log",
        "logs/p41/p2/accept_preprofile.log",
        "logs/p41/p2/pear_profile.log",
    ]),
    ("P44-speed", sorted(glob.glob("logs/p44/p2/accept_s*.log"))
     + sorted(glob.glob("logs/p44/p2/pear_s*.log"))
     + sorted(glob.glob("logs/p44/p2/amend_*.log"))),
    ("P45-mass", sorted(glob.glob("logs/p45/p2/accept_s*.log"))
     + sorted(glob.glob("logs/p45/p2/pear_s*.log"))),
    ("P46-twoline", sorted(glob.glob("logs/p46/p1/twoline_s*.log"))
     + sorted(glob.glob("logs/p44/p2/twoline_s*.log"))),
]
DIAG = [
    "logs/p43/p2/d0_accept_A_s5.log",
    "logs/p43/p2/d0_pear_A_s5.log",
    "logs/p43/p2/r_accept_B_s5_diag.log",
    "logs/p43/p2/r_pear_B_s5_diag.log",
]

#: P48's four `> 6 mm` events, keyed by their catch-up residual (the unambiguous
#: field: the two-line's `index=` is a *fruit* index, not an attempt ordinal, and
#: the same fruit index recurs on later attempts).
EVENTS = [
    ("E1", "logs/p44/p2/accept_s5_S2.log", 219.6, "left"),
    ("E2", "logs/p44/p2/amend_F_S2.log", 245.8, "left"),
    ("E3", "logs/p46/p1/twoline_s5_C.log", 251.0, "left"),
    ("E4", "logs/p46/p1/twoline_s6_C.log", 480.6, "right"),
]

CEILINGS = (0.39, 0.40, 0.42)
BELT = 0.12  # m/s, `assets.py:215`
FLOOR = 0.399  # `_dynamic_select_floor()` = lead 0.189 + 0.12*1.5 + 0.03


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def pct(vals, q):
    if not vals:
        return float("nan")
    vals = sorted(vals)
    if len(vals) == 1:
        return vals[0]
    k = min(len(vals) - 1, max(0, int(round(q * (len(vals) - 1)))))
    return vals[k]


def fnum(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def fmt(vals, w=6, d=4):
    if not vals:
        return "n=0"
    return (f"n={len(vals):<3d} min={min(vals):.{d}f} p50={pct(vals, .5):.{d}f} "
            f"p90={pct(vals, .9):.{d}f} max={max(vals):.{d}f}")


def load(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        print(f"  MISSING {rel}", file=sys.stderr)
        return None
    with open(p, errors="replace") as fh:
        return fh.read()


# --------------------------------------------------------------------------- #
# part 1: the full live-set corpora
# --------------------------------------------------------------------------- #
def parse_bed_blocks(rel):
    """[{attempt, live, on_belt, usable, rows:[(species, along, x, grade, reason)]}]"""
    text = load(rel)
    if text is None:
        return []
    blocks, cur = [], None
    for line in text.splitlines():
        if "[bed-sel]" not in line:
            continue
        m = RE_BED_H.search(line)
        if m:
            cur = {
                "log": rel,
                "attempt": int(m.group(1)) if m.group(1) is not None else None,
                "arm": m.group(2),
                "t": float(m.group(4)),
                "live": int(m.group(5)),
                "on_belt": int(m.group(6)),
                "admitted": int(m.group(7)),
                "window": int(m.group(8)),
                "pick": m.group(11),
                "rows": [],
            }
            blocks.append(cur)
            continue
        m = RE_BED_R.search(line)
        if m and cur is not None:
            cur["rows"].append(
                (m.group(1), fnum(m.group(2)), fnum(m.group(3)), m.group(6), m.group(7))
            )
    for b in blocks:
        b["usable"] = [r for r in b["rows"] if r[4] in ("usable", "chosen")]
        b["chosen"] = next((r for r in b["rows"] if r[4] == "chosen"), None)
    return blocks


# --------------------------------------------------------------------------- #
# part 2: the chosen-x corpora
# --------------------------------------------------------------------------- #
def parse_single(rel):
    """Exact block attribution: one record per `[run] attempt N: picking ...`."""
    text = load(rel)
    if text is None:
        return []
    out, cur = [], None
    for line in text.splitlines():
        if "[fruit]" not in line:
            continue
        m = RE_START.search(line)
        if m:
            cur = {"log": rel, "idx": int(m.group(1)), "species": m.group(2),
                   "arm": None, "diameter": None, "x": None, "dy0": None,
                   "queue": None, "residual": None, "approach_end": None,
                   "outcome": "open"}
            out.append(cur)
            continue
        m = RE_SKIP.search(line)
        if m:
            cur = {"log": rel, "idx": int(m.group(1)), "species": None, "arm": None,
                   "diameter": None, "x": None, "dy0": None, "queue": None,
                   "residual": None, "approach_end": None, "outcome": "skip"}
            out.append(cur)
            cur = None
            continue
        if cur is None:
            continue
        m = RE_RESULT.search(line)
        if m:
            g, p = m.group(2) == "True", m.group(3) == "True"
            cur["outcome"] = "placed" if p else ("cnp" if g else "nograsp")
            cur = None
            continue
        m = RE_TARGET.search(line)
        if m:
            cur["species"] = m.group(1)
            cur["diameter"] = fnum(m.group(3))
            cur["arm"] = m.group(4)
            continue
        m = RE_WAIT0.search(line)
        if m and cur["x"] is None:
            cur["x"] = fnum(m.group(2))
            cur["dy0"] = fnum(m.group(4))
            continue
        m = RE_HANDOVER.search(line)
        if m:
            cur["queue"] = int(m.group(5))
            continue
        m = RE_CATCH.search(line)
        if m:
            cur["residual"] = fnum(m.group(1))
            continue
        m = RE_APPROACH.search(line)
        if m:
            cur["approach_end"] = fnum(m.group(3))
            continue
    return out


def parse_twoline(rel):
    """Per-arm ordinal pairing (target <-> wait <-> hand-over <-> descent <-> catch).

    The two-line prints one window per slot with both arms' rows interleaved, so
    every row is assigned to an arm from its own geometry where it has one:
      * `wait step=0`      -> station = fruit_y - dy
      * `intercept handover` -> station = fruit_y - dy  (dy is the 0.189 m lead,
        so fruit_y = station + dy: 0.189 left / 0.088 right, 0.10 m apart)
      * `dynamic descent`  -> the row prints its own `station`
    The catch-up/approach rows carry no position, so they are paired to the
    descents in print order (P48 validated that pairing against species + outcome).
    """
    text = load(rel)
    if text is None:
        return []
    targets = {"left": [], "right": []}
    waits = {"left": [], "right": []}
    handovers = {"left": [], "right": []}
    results = {"left": [], "right": []}
    descent_arms, catches, approaches = [], [], []

    def arm_of(station):
        if station is None:
            return None
        if abs(station) < 0.05:
            return "left"
        if abs(station + 0.100) < 0.05:
            return "right"
        return None

    for line in text.splitlines():
        if "[fruit]" not in line:
            continue
        m = RE_TARGET.search(line)
        if m:
            targets[m.group(4)].append((m.group(1), fnum(m.group(3))))
            continue
        m = RE_WAIT0.search(line)
        if m:
            arm = arm_of(fnum(m.group(1)) - fnum(m.group(4)))
            if arm is not None:
                waits[arm].append({"x": fnum(m.group(2)), "dy0": fnum(m.group(4))})
            continue
        m = RE_HANDOVER.search(line)
        if m:
            arm = arm_of(fnum(m.group(1)) - fnum(m.group(2)))
            if arm is not None:
                handovers[arm].append(
                    {"dy": fnum(m.group(2)), "queue": int(m.group(5)),
                     "arrived": None}
                )
            continue
        m = RE_ARRIVED.search(line)
        if m:
            continue
        m = RE_DESCENT.search(line)
        if m:
            descent_arms.append(arm_of(fnum(m.group(3))))
            continue
        m = RE_CATCH.search(line)
        if m:
            catches.append(fnum(m.group(1)))
            continue
        m = RE_APPROACH.search(line)
        if m:
            approaches.append(fnum(m.group(3)))
            continue
        m = RE_BIARM.search(line)
        if m:
            results[m.group(1)].append(
                ("placed" if m.group(5) == "True"
                 else ("cnp" if m.group(4) == "True" else "nograsp"),
                 int(m.group(2)), m.group(3))
            )
            continue

    # the k-th catch / approach belongs to the k-th descent, whose arm is printed
    catch_by_arm = {"left": [], "right": []}
    appr_by_arm = {"left": [], "right": []}
    for k, arm in enumerate(descent_arms):
        if arm is None:
            continue
        if k < len(catches):
            catch_by_arm[arm].append(catches[k])
        if k < len(approaches):
            appr_by_arm[arm].append(approaches[k])

    out = []
    for arm in ("left", "right"):
        n = min(len(targets[arm]), len(waits[arm]))
        for k in range(n):
            sp, dia = targets[arm][k]
            w = waits[arm][k]
            res = results[arm][k] if k < len(results[arm]) else (None, None, None)
            ho = handovers[arm][k] if k < len(handovers[arm]) else {}
            out.append({
                "log": rel, "arm": arm, "species": sp, "diameter": dia,
                "x": w["x"], "dy0": w["dy0"],
                "queue": ho.get("queue"),
                "residual": catch_by_arm[arm][k] if k < len(catch_by_arm[arm]) else None,
                "approach_end": appr_by_arm[arm][k] if k < len(appr_by_arm[arm]) else None,
                "outcome": res[0] or "open", "idx": res[1], "ordinal": k,
            })
    return out


def is_twoline(rel, text_head):
    return "[biarm] result" in text_head


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    print("P49 phase 1 - the scripted selector's x-ceiling: the selection census")
    print("=" * 118)
    print("tree: read-only. belt 0.12 m/s, control 120 Hz, catch floor "
          f"{FLOOR:.3f} m above the station (= lead 0.189 + 0.12*1.5 + 0.03).")
    print("x is the *lateral* belt coordinate: band 0.18-0.39 clean, hard cliff at "
          "0.42 (P34/P38/P47), station x ~ 0.333.")

    # ------------------------------------------------------------------ #
    print("\n" + "#" * 118)
    print("# 1. THE FULL LIVE-SET CORPORA  ([bed-sel], FRUIT_BED_DIAG=1)")
    print("#" * 118)
    all_blocks = []
    for rel in DIAG:
        blocks = parse_bed_blocks(rel)
        all_blocks += blocks
        print(f"\n## {rel}   ({len(blocks)} selection blocks)")
        for b in blocks:
            ch = b["chosen"]
            ux = [r[2] for r in b["usable"]]
            print(f"   att {str(b['attempt']):>2s} t={b['t']:7.2f} live={b['live']} "
                  f"on_belt={b['on_belt']} usable={len(b['usable'])} "
                  f"chosen={(ch[0] if ch else '-'):<10s} "
                  f"x={(f'{ch[2]:.4f}' if ch else '    -   '):>8s} "
                  f"along={(f'{ch[1]:+.3f}' if ch else '  -   '):>7s} "
                  f"usable_x={[round(v, 3) for v in ux]}")

    sized = [len(b["usable"]) for b in all_blocks]
    hist = {}
    for n in sized:
        hist[n] = hist.get(n, 0) + 1
    print(f"\n### 1.1 the usable-set size (n = {len(all_blocks)} selection instants, "
          "2 scenarios x 2 rules)")
    for n in sorted(hist):
        print(f"   {n} usable fruit: {hist[n]:3d} blocks ({100*hist[n]/len(all_blocks):5.1f} %)")
    ux = [r[2] for b in all_blocks for r in b["usable"]]
    cx = [b["chosen"][2] for b in all_blocks if b["chosen"]]
    print(f"   usable candidate x:   {fmt(ux)}")
    print(f"   chosen fruit x:       {fmt(cx)}")
    print("   -> the shipped acceptance/pear line presents **one floored fruit per "
          "attempt most of the time**")
    print("      (usable-set size never reaches 3 in 40 selections), and the whole "
          "usable population's x")
    print(f"      sits inside 0.209-0.369: the registered ceiling is "
          f"{0.39 - max(ux):.3f} m above the largest usable candidate.")

    print("\n### 1.2 the instrument's neutrality (why the census can sit inside an arm)")
    a = [l for l in (load("logs/p43/p2/d0_accept_A_s5.log") or "").splitlines()
         if l.startswith("[fruit]") and "[bed-" not in l and "[supply-diag]" not in l
         and "[feed]" not in l]
    b = [l for l in (load("logs/p43/p2/post_revert_accept_unset.log") or "").splitlines()
         if l.startswith("[fruit]") and "[bed-" not in l and "[supply-diag]" not in l
         and "[feed]" not in l]
    same = sum(1 for x, y in zip(a, b) if x == y)
    print(f"   d0_accept_A_s5.log (FRUIT_BED_DIAG=1) vs post_revert_accept_unset.log "
          f"(no diag), same scenario:")
    print(f"   {same}/{min(len(a), len(b))} `[fruit]` lines identical "
          f"({len(a)} vs {len(b)} rows) -> the census is print-only.")

    # ------------------------------------------------------------------ #
    print("\n" + "#" * 118)
    print("# 2. THE CHOSEN-X DISTRIBUTION  (wait step=0 fruit_x, the selection's x)")
    print("#" * 118)
    rows = []
    for name, paths in CORPORA:
        atts = []
        print(f"\n## {name}")
        for rel in paths:
            text = load(rel)
            if text is None:
                continue
            got = parse_twoline(rel) if is_twoline(rel, text) else parse_single(rel)
            got = [a for a in got if a.get("x") is not None]
            if not got:
                continue
            atts += got
            xs = [a["x"] for a in got]
            print(f"   {os.path.basename(rel):26s} n={len(xs):2d} "
                  f"max={max(xs):.4f}  >0.39={sum(1 for v in xs if v > 0.39)} "
                  f">0.40={sum(1 for v in xs if v > 0.40)} "
                  f">0.42={sum(1 for v in xs if v > 0.42)}")
        xs = [a["x"] for a in atts]
        print(f"   -- {name}: {fmt(xs)}")
        print(f"      >0.39 {sum(1 for v in xs if v > 0.39)}/{len(xs)} "
              f"({100*sum(1 for v in xs if v > 0.39)/max(1,len(xs)):.1f} %), "
              f">0.40 {sum(1 for v in xs if v > 0.40)}/{len(xs)}, "
              f">0.42 {sum(1 for v in xs if v > 0.42)}/{len(xs)}")
        for a in atts:
            a["corpus"] = name
        rows += atts

    xs = [a["x"] for a in rows]
    print(f"\n### 2.1 pooled raw rows: {fmt(xs)}")
    print(f"   >0.39 {sum(1 for v in xs if v > 0.39)}/{len(xs)}  "
          f">0.40 {sum(1 for v in xs if v > 0.40)}/{len(xs)}  "
          f">0.42 {sum(1 for v in xs if v > 0.42)}/{len(xs)}")
    seen, uniq = {}, []
    for a in rows:
        key = (round(a["x"], 4), a["species"], round(a["diameter"] or 0, 2))
        if key in seen:
            seen[key].append(a["log"])
            continue
        seen[key] = [a["log"]]
        uniq.append(a)
    uxs = [a["x"] for a in uniq]
    print(f"\n### 2.2 pooled **unique** attempts (a bit-identical replay of one attempt "
          f"across arms collapses;\n      key = (x@4dp, species, diameter)): {fmt(uxs)}")
    print(f"   >0.39 {sum(1 for v in uxs if v > 0.39)}/{len(uxs)} "
          f"({100*sum(1 for v in uxs if v > 0.39)/max(1,len(uxs)):.1f} %)   "
          f">0.40 {sum(1 for v in uxs if v > 0.40)}/{len(uxs)}   "
          f">0.42 {sum(1 for v in uxs if v > 0.42)}/{len(uxs)}")
    tail = [a for a in uniq if a["x"] > 0.39]
    print("   the rows above 0.39 (unique):")
    for a in sorted(tail, key=lambda z: -z["x"]):
        print(f"     x={a['x']:.4f} {a['species']:<10s} dia={a['diameter']} "
              f"arm={a['arm']} outcome={a['outcome']:<8s} corpus={a['corpus']} "
              f"{os.path.basename(a['log'])}"
              f"{' +' + str(len(seen[(round(a['x'],4), a['species'], round(a['diameter'] or 0,2))])-1) + ' replay(s)' if len(seen[(round(a['x'],4), a['species'], round(a['diameter'] or 0,2))])>1 else ''}")

    # ------------------------------------------------------------------ #
    print("\n" + "#" * 118)
    print("# 3. THE REFUSAL ARITHMETIC")
    print("#" * 118)
    print("\n### 3.1 how many attempts would refuse the chosen fruit")
    for c in CEILINGS:
        n_all = sum(1 for b in all_blocks if b["chosen"] and b["chosen"][2] > c)
        n_u = sum(1 for v in uxs if v > c)
        print(f"   ceiling {c:.2f}: diag corpus (full live sets, n={len(all_blocks)}) "
              f"refuses {n_all};  pooled unique attempts (n={len(uxs)}) refuses {n_u} "
              f"({100*n_u/max(1,len(uxs)):.1f} %)")
    print("   per corpus, unique attempts refused at 0.39:")
    for name in dict.fromkeys(a["corpus"] for a in uniq):
        sel = [a for a in uniq if a["corpus"] == name]
        print(f"     {name:<14s} {sum(1 for a in sel if a['x'] > 0.39)}/{len(sel)}  "
              f"(0.40: {sum(1 for a in sel if a['x'] > 0.40)}, "
              f"0.42: {sum(1 for a in sel if a['x'] > 0.42)})")

    print("\n### 3.2 the next eligible fruit: availability and cost (full-set corpus)")
    print(f"   rule: usable = at/above the catch floor {FLOOR:.3f}; the ceiling keeps "
          "only usable fruit with x <= ceiling;")
    print("   the shipped farthest-upstream rule then takes the largest `along` of that set.")
    for c in CEILINGS:
        hit = [b for b in all_blocks if b["chosen"] and b["chosen"][2] > c]
        avail = [b for b in hit if any(r[2] <= c for r in b["usable"] if r is not b["chosen"])]
        print(f"   ceiling {c:.2f}: {len(hit)} refusals, "
              f"{len(avail)} with a next eligible fruit inside the ceiling")
    # the structural read, independent of whether the ceiling binds
    n1 = sum(1 for b in all_blocks if len(b["usable"]) == 1)
    n2 = sum(1 for b in all_blocks if len(b["usable"]) == 2)
    print(f"   structural: a ceiling that binds meets a usable set of 1 in {n1}/{len(all_blocks)} "
          f"selections (-> **skip**, no substitute exists)")
    print(f"               and of 2 in {n2}/{len(all_blocks)} -> a substitute exists only if "
          "the *other* fruit is inside the ceiling.")
    print("   the substitution's cost, under the two rules in the corpus "
          "(d_along > 0 = the substitute arrives *sooner*):")
    for b in all_blocks:
        if len(b["usable"]) == 2 and b["chosen"]:
            other = next(r for r in b["usable"] if r is not b["chosen"])
            d = b["chosen"][1] - other[1]
            rule = ("nearest" if os.path.basename(b["log"]).startswith("r_")
                    else "upstream")
            print(f"     {rule:<8s} att {str(b['attempt']):>2s} "
                  f"{os.path.basename(b['log']):24s} "
                  f"chosen x={b['chosen'][2]:.3f} along={b['chosen'][1]:+.3f} | "
                  f"alt x={other[2]:.3f} along={other[1]:+.3f} | d_along={d:+.3f} m "
                  f"= {d/BELT:+.2f} s")
    print("   under the **shipped farthest-upstream** rule the substitute is always "
          "the nearer fruit (d_along > 0),")
    print("   i.e. a substitution *saves* 0.9-2.1 s of belt travel - it is the skip, "
          "not the substitute, that costs.")

    print("\n### 3.3 the skip cost (the driver's own loop)")
    print("   `20_pick_place.py` advances 60 ticks (0.5 s = 60 mm of belt travel) "
          "*before* every selection, then selects;")
    print("   a `no eligible fruit` result `continue`s to the next attempt index. So a "
          "refused slot costs")
    print("   **one of the ATTEMPTS and 0.5 s of sim**, not a 15 s cycle, and it repeats "
          "until an *inside* fruit")
    print("   rises above the floor (the refused fruit never becomes legal - its x is a "
          "constant).")
    # selection-time along from the diag corpus: the [bed-sel] block reads `along` at
    # the selection, the attempt's own `wait step=0` 1.6 s later - the pair gives the
    # selection->wait offset and the floor's remaining legality.
    off, alongs = [], []
    for b in all_blocks:
        if b["attempt"] is None:
            continue
        atts = parse_single(b["log"])
        rec = next((a for a in atts if a["idx"] == b["attempt"]), None)
        if b["chosen"] and rec and rec["dy0"] is not None:
            off.append(b["chosen"][1] - rec["dy0"])
        if b["chosen"]:
            alongs.append(b["chosen"][1])
    if off:
        print(f"   selection -> `wait step=0` offset (the pre-pose's belt travel): "
              f"{fmt(off)} m = {pct(off,.5)/BELT:.2f} s")
    print(f"   selection-time along of the chosen fruit: {fmt(alongs)} m against the "
          f"floor {FLOOR:.3f}")
    slots = [(a - FLOOR) / (BELT * 0.5) for a in alongs]
    print(f"   -> a refused fruit is refused for {min(slots):.1f}-{max(slots):.1f} slots "
          f"(p50 {pct(slots,.5):.1f}) **if nothing else is legal**; the slot resumes as "
          "soon as")
    print("      an inside fruit crosses the floor (supply gaps 0.10-0.35 m = 0.8-2.9 s "
          "= 2-6 slots).")
    print("   The refused fruit itself is not a lost placement: the P48 population places "
          "0 of 6 rows above 0.39,")
    print("   so the ceiling re-allocates an attempt that was going to fail, and the cost "
          "is the wait it inserts.")

    # ------------------------------------------------------------------ #
    print("\n" + "#" * 118)
    print("# 4. THE TAIL EVENTS (P48's > 6 mm set): what the record holds")
    print("#" * 118)
    for tag, rel, resid, arm in EVENTS:
        text = load(rel)
        if text is None:
            continue
        got = parse_twoline(rel) if is_twoline(rel, text) else parse_single(rel)
        rec = None
        for a in got:
            if a.get("residual") is not None and abs(a["residual"] - resid) < 0.05:
                rec = a
                break
        if rec is None:
            print(f"   {tag}: no record with residual {resid} in {rel}")
            continue
        ordinal = (f"att {rec['ordinal']}" if rec.get("ordinal") is not None
                   else f"att {rec['idx']}")
        print(f"   {tag:3s} {os.path.basename(rel):22s} {ordinal:7s} {str(rec['arm']):<5s} "
              f"{str(rec['species']):<10s} x={rec['x']:.4f} dy0={rec['dy0']:+.4f} "
              f"queue={rec['queue']} residual={rec['residual']} "
              f"end={rec['approach_end']} outcome={rec['outcome']}")
    print("\n   `queue` is `_queue_depth()`: fruit with along in [pick_y-0.05, pick_y+0.45], "
          "**not** the floored set")
    print("   - it counts candidates below the 0.399 catch floor too, and at the "
          "hand-over instant the selected fruit itself is inside it.")
    print("   So `queue=2` says: one other fruit in a 0.50 m band, 1.63 s after the "
          "selection (0.196 m of belt travel),")
    print("   and says nothing about that fruit's x. **The alternatives at the three "
          "tail instants are not in the record**:")
    print("   no arm that carries them ran FRUIT_BED_DIAG, and FRUIT_SUPPLY_DIAG prints "
          "counts, not positions.")
    print("   -> whether a 0.39 ceiling would have *converted* or only *skipped* those "
          "instances is not answerable offline;")
    print("      it is what phase 2's event-bearing arm measures (see PREREG E1/E2).")

    # ------------------------------------------------------------------ #
    print("\n" + "#" * 118)
    print("# 5. THE x=0.42 CLIFF AND THE TWO-LINE SCOPE")
    print("#" * 118)
    tw = [a for a in rows if is_twoline(a["log"], load(a["log"]) or "")]
    for arm in ("left", "right"):
        sel = [a["x"] for a in tw if a["arm"] == arm]
        print(f"   two-line {arm:<5s}: {fmt(sel)}  "
              f"(>0.39 {sum(1 for v in sel if v > 0.39)}/{len(sel)})")
    print(f"   two-line pooled: {fmt([a['x'] for a in tw])}")
    print("   The shipped selector's return order (`tasks.py select_target`, "
          "`:5797` onward):")
    print("     1. `_reach_anywhere_active()` -> `_reach_anywhere_select` (opt-in, off)")
    print("     2. floor  = pick_y + `_dynamic_select_floor()`; usable = along >= floor")
    print("     3. `lane is not None`      -> `usable[0]`          (shared-station worker)")
    print("     4. `prefer_lane is not None` -> lane/grade rule     (**the two-line**)")
    print("     5. `FRUIT_SELECT_NEAREST_ABOVE_FLOOR` (off) / `_balance_arm` -> the "
          "farthest-upstream pick")
    print("   A ceiling in the single-arm branch (step 5) is unreachable from steps 3/4: "
          "the two-line returns before it.")
    print("   And it must not reach it: the two-line's per-arm station separation is its "
          "clearance mechanism (W2),")
    print("   its eligibility is the per-arm grade (W3 pure routing), and a global x-ceiling "
          "would refuse a whole arm's")
    print("   stream off its own delivered-x tail - the R5/V1 lane-starvation repeat - while "
          "its reference")
    print("   `configs/motion_reference_twoline.json` would move. Scope: "
          "**scripted single-arm dynamic line only**.")
    print(f"   The 0.42 cliff: the corpus's largest chosen x is {max(xs):.4f} and its "
          f"largest *usable* candidate {max(ux):.3f},")
    print("   so a 0.42 ceiling refuses nothing that exists here (and 0.40 also refuses "
          "nothing): the only")
    print("   ceiling with any action on this corpus is 0.39, and its action is confined to "
          "the 0.390-0.397 window.")

    # ------------------------------------------------------------------ #
    print("\n" + "#" * 118)
    print("# 6. SUMMARY")
    print("#" * 118)
    print(f"   chosen x, pooled unique (n={len(uxs)}): p50 {pct(uxs,.5):.3f}, "
          f"p90 {pct(uxs,.9):.3f}, max {max(uxs):.3f}; >0.39 "
          f"{sum(1 for v in uxs if v > 0.39)}, >0.40 {sum(1 for v in uxs if v > 0.40)}, "
          f">0.42 {sum(1 for v in uxs if v > 0.42)}")
    print(f"   the full-set corpus (n={len(all_blocks)}): usable set 1-2 fruit, "
          f"usable x max {max(ux):.3f} -> 0 refusals at every ceiling")
    print("   the tail is instance-bound: 2 distinct instances (3 raw events) in ~"
          f"{len(uxs)} unique attempts, both kiwis at the release-offset tail")


if __name__ == "__main__":
    main()
