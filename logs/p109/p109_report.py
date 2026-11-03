#!/usr/bin/env python3
"""P109 report - the descent margin (0.15 / 0.075 / 0) on the scripted single arm.

Reads `logs/p109/{M0,M05,M1}_s{5,6,101,202}.log` and prints, per arm and seed, the
endpoints `logs/p109/PREREG.md` registered, in its order:

  E0  the branch        the selected sequence (species / grade / fruit_x)
  E1a the row's `fruit dy`      (predicted invariant: == speed * t_desc)
  E1b the mechanism     g0 = fruit dy + shift  (the descent-start gap to the aim)
  E2  the aim quality   the descent's `end=`, the catch-up residual, and the
                        DERIVED end-of-descent arrival error g0 - speed*steps
  E3  the guard         the no-grasp class and the never-held subset
  E4  the count         placed / attempts
  E5  the landing       `place trace ... on_belt`
  E6  the budgets       the descent |v|max against 105's budget (see `--gate`)

and then the decision rule's three clauses per seed (E1b >= 12 mm, E3 not higher,
E4 not down by more than one).

`--same A B` compares two logs line for line on the `[fruit]` stream with the
phase's own instrumentation rows dropped - the replay proof the tree's rule asks
for (`[cycle]` is this phase's only added row).
"""

from __future__ import annotations

import argparse
import re
import statistics as st
import sys

ARMS = ("M0", "M05", "M1")
SEEDS = (5, 6, 101, 202)
MARGIN = {"M0": 0.150, "M05": 0.075, "M1": 0.0}
BELT = 0.12  # m/s, the shipped line's speed (`encoder=-0.120`)
HZ = 120.0

# instrumentation rows this phase adds / that are not physics (dropped by `--same`)
DROP = (
    re.compile(r"\[fruit\] \[cycle\]"),
    re.compile(r"\[fruit\] \[stats\]"),
    re.compile(r"\[fruit\] \[run\] summary"),
)

RE_STATS = re.compile(
    r"\[fruit\] \[stats\] attempts=(\d+) successes=(\d+) diverted=(\d+)"
)
RE_RUN = re.compile(
    r"\[fruit\] \[run\] attempt (\d+)(?: \((\w+)\))?: (.*?)grasped=(\w+) placed=(\w+)"
    r"(?: lift=([+-][\d.]+) m)?(?: force=([\d.]+) N)?.*?notes=\[(.*?)\]"
)
RE_TARGET = re.compile(r"\[fruit\] \[task\] target (\w+) \(grade (\w)")
RE_LEAD = re.compile(r"moving pick: meeting the fruit (\d+) mm upstream")
RE_DESC = re.compile(
    r"\[fruit\] \[task\] dynamic descent: waited (\d+) ticks, "
    r"intercept=([+-][\d.]+) m \(station ([+-][\d.]+), shift ([+-][\d.]+) m\), "
    r"fruit dy=([+-][\d.]+) m, deadline=([\d.]+) m, t_desc=([\d.]+) s"
)
RE_MOTION = re.compile(
    r"\[fruit\] \[motion\] approach\(cartesian\): [\d.]+ cm, (\d+) samples: "
    r".*?\|v\|max=([\d.]+) m/s.*?end=([\d.]+) mm"
)
RE_CATCH = re.compile(r"dynamic catch-up: residual=([\d.]+) mm \(tol ([\d.]+) mm\)")
RE_CARRY = re.compile(
    r"\[fruit\] \[carry\] (\w+) (\w+): .*?force_min=([\d.]+)N"
)
RE_PLACE = re.compile(
    r"place trace (\w+): release_bottom=([+-]?[\d.]+)mm .*?on_belt=(\w+)"
)
RE_X = re.compile(r"wait step=0 fruit_y=[+-]?[\d.]+ fruit_x=([+-][\d.]+)")


def pct(xs, q):
    if not xs:
        return float("nan")
    xs = sorted(xs)
    if len(xs) == 1:
        return xs[0]
    i = q * (len(xs) - 1)
    lo = int(i)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def read(path):
    out = {
        "stats": None,
        "attempts": [],
        "targets": [],
        "lead_mm": [],
        "waited": [],
        "shift_mm": [],
        "dy_mm": [],
        "g0_mm": [],
        "deadline_mm": [],
        "t_desc": [],
        "steps": [],
        "vmax": [],
        "end_mm": [],
        "catch_mm": [],
        "catch_tol": [],
        "force_min": [],
        "land": [],
    }
    try:
        lines = open(path, errors="replace").read().splitlines()
    except FileNotFoundError:
        return None
    for line in lines:
        m = RE_STATS.search(line)
        if m:
            out["stats"] = tuple(int(g) for g in m.groups())
        m = RE_RUN.search(line)
        if m:
            out["attempts"].append(
                {
                    "i": int(m.group(1)),
                    "arm": m.group(2),
                    "grasped": m.group(4) == "True",
                    "placed": m.group(5) == "True",
                    "lift": float(m.group(6)) if m.group(6) else None,
                    "notes": m.group(8),
                }
            )
        m = RE_TARGET.search(line)
        if m:
            out["targets"].append(m.group(1))
        m = RE_LEAD.search(line)
        if m:
            out["lead_mm"].append(float(m.group(1)))
        m = RE_DESC.search(line)
        if m:
            waited, _ic, _st, shift, dy, deadline, tdes = m.groups()
            shift_mm, dy_mm = float(shift) * 1000.0, float(dy) * 1000.0
            out["waited"].append(float(waited))
            out["shift_mm"].append(shift_mm)
            out["dy_mm"].append(dy_mm)
            out["g0_mm"].append(dy_mm + shift_mm)  # the measured break gap
            out["deadline_mm"].append(float(deadline) * 1000.0)
            out["t_desc"].append(float(tdes))
        m = RE_MOTION.search(line)
        if m:
            out["steps"].append(float(m.group(1)))
            out["vmax"].append(float(m.group(2)))
            out["end_mm"].append(float(m.group(3)))
        m = RE_CATCH.search(line)
        if m:
            out["catch_mm"].append(float(m.group(1)))
            out["catch_tol"].append(float(m.group(2)))
        m = RE_CARRY.search(line)
        if m:
            out["force_min"].append((m.group(2), float(m.group(3))))
        m = RE_PLACE.search(line)
        if m:
            out["land"].append(
                {"side": m.group(1), "bottom": float(m.group(2)), "on_belt": m.group(3) == "True"}
            )
    # derived: the fruit's position relative to the aim when the descent ends
    out["arrival_err_mm"] = [
        g0 - s * (BELT / HZ) * 1000.0 for g0, s in zip(out["g0_mm"], out["steps"])
    ]
    return out


def grep_x(path):
    xs = []
    try:
        for line in open(path, errors="replace"):
            if "wait step=0" in line:
                m = RE_X.search(line)
                if m:
                    xs.append(float(m.group(1)))
    except FileNotFoundError:
        pass
    return xs


def summary(arm, seed, d):
    if d is None or d["stats"] is None:
        return None
    attempts = d["attempts"]
    n_grasp = sum(1 for a in attempts if not a["grasped"])
    # never-seated on the lift leg: the pads closed on air (`grasp_lift` and
    # `force_min == 0.00 N`).  A `place*` row's zero is the downstream view of a
    # payload already gone (P60), so it is excluded.
    n_never = sum(
        1 for leg, f in d["force_min"] if leg.startswith("grasp") and f == 0.0
    )
    placed = sum(1 for a in attempts if a["placed"])
    notes = {}
    for a in attempts:
        for key in (a["notes"] or "").split(","):
            key = key.strip().strip("'\"")
            if key:
                notes[key] = notes.get(key, 0) + 1
    # landing: payload present at the release = release_bottom >= 0
    present = [r for r in d["land"] if r["bottom"] >= 0.0]
    on_belt = sum(1 for r in present if r["on_belt"])
    catch_bad = sum(1 for c, t in zip(d["catch_mm"], d["catch_tol"]) if c > t + 1e-9)
    # the bistable class: the catch-up did not merely miss the 6 mm tolerance,
    # it ran away to the belt's own travel budget (> 50 mm)
    runaways = sum(1 for c in d["catch_mm"] if c > 50.0)
    return {
        "arm": arm,
        "seed": seed,
        "stats": d["stats"],
        "attempts": len(attempts),
        "placed": placed,
        "no_grasp": n_grasp,
        "never_held": n_never,
        "catch_bad": catch_bad,
        "runaways": runaways,
        "g0_p50": pct(d["g0_mm"], 0.5),
        "g0_p90": pct(d["g0_mm"], 0.9),
        "deadline_p50": pct(d["deadline_mm"], 0.5),
        "dy_p50": pct(d["dy_mm"], 0.5),
        "dy_p90": pct(d["dy_mm"], 0.9),
        "shift_p50": pct(d["shift_mm"], 0.5),
        "waited_p50": pct(d["waited"], 0.5),
        "lead_p50": pct(d["lead_mm"], 0.5),
        "steps_p50": pct(d["steps"], 0.5),
        "vmax_max": max(d["vmax"]) if d["vmax"] else float("nan"),
        "end_p50": pct(d["end_mm"], 0.5),
        "end_p90": pct(d["end_mm"], 0.9),
        "catch_p50": pct(d["catch_mm"], 0.5),
        "catch_max": max(d["catch_mm"]) if d["catch_mm"] else float("nan"),
        "arr_p50": pct(d["arrival_err_mm"], 0.5),
        "arr_p90": pct(d["arrival_err_mm"], 0.9),
        "land_present": len(present),
        "land_ok": on_belt,
        "notes": notes,
        "targets": d["targets"],
        "xs": grep_x(f"logs/p109/{arm}_s{seed}.log"),
    }


def table(rows):
    hdr = (
        f"{'arm':4} {'seed':>4} {'att':>4} {'plcd':>5} {'nograsp':>8} {'never':>6} "
        f"{'catch>tol':>10} {'runaway':>8} {'g0p50':>7} {'g0p90':>7} {'deadline':>9} {'dy_p50':>7} "
        f"{'shift':>6} {'wait':>5} {'lead':>5} {'steps':>6} {'vmax':>6} "
        f"{'end_p50':>8} {'end_p90':>8} {'catch':>6} {'arr_p50':>8} {'land':>7}"
    )
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        if r is None:
            continue
        print(
            f"{r['arm']:4} {r['seed']:>4} {r['attempts']:>4} {r['placed']:>5} "
            f"{r['no_grasp']:>8} {r['never_held']:>6} {r['catch_bad']:>10} {r['runaways']:>8} "
            f"{r['g0_p50']:>7.1f} {r['g0_p90']:>7.1f} {r['deadline_p50']:>9.1f} "
            f"{r['dy_p50']:>7.1f} {r['shift_p50']:>6.1f} {r['waited_p50']:>5.0f} "
            f"{r['lead_p50']:>5.0f} {r['steps_p50']:>6.0f} {r['vmax_max']:>6.3f} "
            f"{r['end_p50']:>8.1f} {r['end_p90']:>8.1f} {r['catch_p50']:>6.1f} "
            f"{r['arr_p50']:>8.1f} "
            f"{r['land_ok']:>3}/{r['land_present']:<3}"
        )


def decision(rows):
    by = {(r["arm"], r["seed"]): r for r in rows if r}
    print("\n== the decision rule (PREREG section 4), per seed ==")
    print(
        f"{'seed':>4} {'g0 M0':>7} {'g0 M1':>7} {'d_g0':>7} {'>=12?':>6} "
        f"{'nograsp M0':>10} {'M1':>4} {'ok?':>4} {'plcd M0':>8} {'M1':>4} {'ok?':>4}"
    )
    wins = []
    for seed in SEEDS:
        m0, m1 = by.get(("M0", seed)), by.get(("M1", seed))
        if not m0 or not m1:
            print(f"{seed:>4}   (incomplete)")
            wins.append(None)
            continue
        dg = m0["g0_p50"] - m1["g0_p50"]
        c1 = dg >= 12.0
        c2 = m1["no_grasp"] <= m0["no_grasp"]
        c3 = m1["placed"] >= m0["placed"] - 1
        wins.append(c1 and c2 and c3)
        print(
            f"{seed:>4} {m0['g0_p50']:>7.1f} {m1['g0_p50']:>7.1f} {dg:>+7.1f} "
            f"{str(c1):>6} {m0['no_grasp']:>10} {m1['no_grasp']:>4} {str(c2):>4} "
            f"{m0['placed']:>8} {m1['placed']:>4} {str(c3):>4}"
        )
    print()
    if all(w is True for w in wins) and wins:
        print("VERDICT: all three clauses pass at every seed -> M1 is a CANDIDATE.")
    else:
        print("VERDICT: at least one clause fails -> a report, not a lever.")
    # the half-margin arm, reported
    half = [by.get(("M05", s)) for s in SEEDS]
    if all(half):
        print("\n== the dose axis (M0.5 = 0.075), reported ==")
        for seed in SEEDS:
            m0, m5, m1 = by[("M0", seed)], by[("M05", seed)], by[("M1", seed)]
            print(
                f"  seed {seed:>3}: g0 {m0['g0_p50']:6.1f} / {m5['g0_p50']:6.1f} / "
                f"{m1['g0_p50']:6.1f} mm | no-grasp {m0['no_grasp']} / "
                f"{m5['no_grasp']} / {m1['no_grasp']} | placed {m0['placed']} / "
                f"{m5['placed']} / {m1['placed']}"
            )


def same(a, b):
    """Line-for-line identity on the `[fruit]` stream, the phase's rows dropped."""
    la = [l for l in open(a, errors="replace").read().splitlines() if l.startswith("[fruit]")]
    lb = [l for l in open(b, errors="replace").read().splitlines() if l.startswith("[fruit]")]
    fa = [l for l in la if not any(p.search(l) for p in DROP)]
    fb = [l for l in lb if not any(p.search(l) for p in DROP)]
    n = min(len(fa), len(fb))
    first = next((i for i in range(n) if fa[i] != fb[i]), None)
    same_n = sum(1 for i in range(n) if fa[i] == fb[i])
    print(f"A {a}: {len(fa)} rows (dropped {len(la) - len(fa)})")
    print(f"B {b}: {len(fb)} rows (dropped {len(lb) - len(fb)})")
    if first is None and len(fa) == len(fb):
        print(f"IDENTICAL {len(fa)}/{len(fa)}")
        return 0
    print(f"identical {same_n}/{n}; first difference at filtered index {first}")
    if first is not None:
        print(f"  A: {fa[first][:160]}")
        print(f"  B: {fb[first][:160]}")
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--same", nargs=2, metavar=("A", "B"))
    ap.add_argument("--detail", action="store_true", help="per-attempt class ledger")
    args = ap.parse_args()
    if args.same:
        sys.exit(same(*args.same))

    rows = []
    for arm in ARMS:
        for seed in SEEDS:
            d = read(f"logs/p109/{arm}_s{seed}.log")
            rows.append(summary(arm, seed, d))
    table(rows)
    pooled = {}
    for arm in ARMS:
        rs = [r for r in rows if r and r["arm"] == arm]
        if rs:
            pooled[arm] = (
                sum(r["placed"] for r in rs),
                sum(r["attempts"] for r in rs),
                sum(r["no_grasp"] for r in rs),
                sum(r["never_held"] for r in rs),
            )
    print("\n== pooled ==")
    for arm, (p, a, g, nv) in pooled.items():
        print(f"  {arm:4} placed {p}/{a} = {p / a * 100:.1f}%   no-grasp {g}   never-seated-lift {nv}")

    print("\n== the class ledger (failure notes, per arm) ==")
    for arm in ARMS:
        acc = {}
        for r in rows:
            if r and r["arm"] == arm:
                for k, v in r["notes"].items():
                    acc[k] = acc.get(k, 0) + v
        print(f"  {arm:4} " + (", ".join(f"{k} x{v}" for k, v in sorted(acc.items())) or "-"))

    print("\n== the branch (E0): selected species per attempt ==")
    for arm in ARMS:
        seq = {r["seed"]: ",".join(r["targets"]) for r in rows if r and r["arm"] == arm}
        if seq:
            print(f"  {arm:4} " + " | ".join(f"s{s}: {v}" for s, v in seq.items()))
    print("\n== fruit_x at the target row ==")
    for arm in ARMS:
        for r in rows:
            if r and r["arm"] == arm and r["xs"]:
                print(f"  {arm:4} s{r['seed']:<4} " + " ".join(f"{x:+.3f}" for x in r["xs"][:6]))

    decision(rows)

    # The acceptance A/B (PREREG section 5): 10 attempts, the shipped two-line
    # session, the only place the phase reads the two-line's catch.
    print("\n== the acceptance A/B (two-line, 10 attempts) ==")
    for tag, label in (("accept_m0", "M0 unset"), ("accept_m1", "M1 armed")):
        d = read(f"logs/p109/{tag}.log")
        if d is None or d["stats"] is None:
            print(f"  {label:10} (no log)")
            continue
        u = summary(tag, 0, d)
        print(
            f"  {label:10} placed {u['placed']}/{u['attempts']} no_grasp {u['no_grasp']} "
            f"runaways {u['runaways']} catch_p50 {u['catch_p50']:.1f} "
            f"g0_p50 {u['g0_p50']:.1f} arr_p50 {u['arr_p50']:.1f} "
            f"end_p50 {u['end_p50']:.1f} vmax {u['vmax_max']:.3f}"
        )

    if args.detail:
        print("\n== per-attempt ledger ==")
        for arm in ARMS:
            for seed in SEEDS:
                d = read(f"logs/p109/{arm}_s{seed}.log")
                if not d:
                    continue
                print(f"  {arm} s{seed}:")
                for a in d["attempts"]:
                    print(
                        f"    {a['i']:>2} grasped={str(a['grasped']):5} "
                        f"placed={str(a['placed']):5} lift={a['lift']} notes=[{a['notes'][:60]}]"
                    )


if __name__ == "__main__":
    main()
