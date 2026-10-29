#!/usr/bin/env python3
"""P63 phase 2 report: **where the left's 26-29 deg goes** - hold/IK or the command path.

Reads the registered cell (`logs/p63/p2/D_{77,101,202}.log`, the shipped direct
profile with `FRUIT_CARRY_DIAG=1` + `FRUIT_ACQ_DIAG=1`), the F3 comparator
(`logs/p61/p2/S_{77,101,202}.log`, the same scenario/checkpoint/seeds on the
pre-instrument tree) and the command identity from `configs/waypoints.json` +
`src/fruit_sorting/motion.py`'s `top_down_quaternion`/`mirror_across_xz`.

    python3 logs/p63/p2_report.py            # print
    python3 logs/p63/p2_report.py --check    # + structural assertions

Definitions are fixed in `logs/p63/PREREG.md` (written before the run):
`hold_drift` = the leg's max commanded-vs-achieved wrist angle (degrees) over its
guarded ticks; `(no-hold)` = `hold_quaternion` was `None` on every guarded tick;
the primary population is the `grasp_lift` legs, the outcome is the **attempt's**
(`logs/p60/p3/report.py`'s `outcome()`), and an `escape` is
`clean_slip_max > 50 mm` (P61's convention).

The row format is unchanged for P61's parser by construction: this file imports
`logs/p60/p3/report.py`'s `parse_leg`/`parse_direct`/`outcome` as-is (that IS the
"still parses" check) and adds one `hold_drift` regex of its own.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CELL = [f"logs/p63/p2/D_{s}.log" for s in (77, 101, 202)]
CTRL = [f"logs/p61/p2/S_{s}.log" for s in (77, 101, 202)]
P60_REPORT = "logs/p60/p3/report.py"
WAYPOINTS = "configs/waypoints.json"
TASKS = "src/fruit_sorting/tasks.py"
HEADER = "logs/p63/p2/header.txt"

ESCAPE_MM = 50.0  # P61's escape floor
INHAND_MM = 1000.0  # P61 amendment A3's in-hand-slide ceiling (excludes ejections)
FARMS = ("left", "right")

_RE_DRIFT = re.compile(r"hold_drift=([\d.]+)deg(\(no-hold\))?")
_RE_ATT = re.compile(
    r"\[attitude\] (\w+) (\w+): tilt=([\d.]+)deg from world -Z, "
    r"tool_axis=\(([-+][\d.]+),([-+][\d.]+),([-+][\d.]+)\)"
)
_RE_MD5ROW = re.compile(r"^([0-9a-f]{32})\s+(\S+)$")

# P62 phase 2's measured left `grasp_lift` belt projection (logs/p62/P2_RESULTS.md
# section 2): the "still +0.32..+0.36" the registered decision rule names.
P62_PROJ = (0.3554, 0.3210)


# --------------------------------------------------------------------------- #
# P60's parser, imported as-is (the P61-P5 "still parses" check)
# --------------------------------------------------------------------------- #
def load_p60():
    spec = importlib.util.spec_from_file_location("p60_report", ROOT / P60_REPORT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# --------------------------------------------------------------------------- #
# the command identity, recomputed offline (PREREG section 3)
# --------------------------------------------------------------------------- #
def top_down_quaternion(closing_axis: str = "y") -> list[float]:
    """`motion.top_down_quaternion`, pure python (the mat->quat branches verbatim)."""
    if closing_axis == "x":
        m = [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, -1.0]]
    else:
        m = [[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]]
    if m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2.0
        w, x, y, z = (
            (m[2][1] - m[1][2]) / s, 0.25 * s,
            (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s,
        )
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2.0
        w, x, y, z = (
            (m[0][2] - m[2][0]) / s, (m[0][1] + m[1][0]) / s,
            0.25 * s, (m[1][2] + m[2][1]) / s,
        )
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2.0
        w, x, y, z = (
            (m[1][0] - m[0][1]) / s, (m[0][2] + m[2][0]) / s,
            (m[1][2] + m[2][1]) / s, 0.25 * s,
        )
    return [w, x, y, z]


def quat_matrix(q) -> list[list[float]]:
    w, x, y, z = (float(v) for v in q)
    n = math.sqrt(w * w + x * x + y * y + z * z)
    w, x, y, z = w / n, x / n, y / n, z / n
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]


def matrix_quat(r: list[list[float]]) -> list[float]:
    tr = r[0][0] + r[1][1] + r[2][2]
    if tr > 0.0:
        s = math.sqrt(tr + 1.0) * 2.0
        return [0.25 * s, (r[2][1] - r[1][2]) / s, (r[0][2] - r[2][0]) / s,
                (r[1][0] - r[0][1]) / s]
    i = max(range(3), key=lambda k: r[k][k])
    if i == 0:
        s = math.sqrt(1.0 + r[0][0] - r[1][1] - r[2][2]) * 2.0
        return [(r[2][1] - r[1][2]) / s, 0.25 * s, (r[0][1] + r[1][0]) / s,
                (r[0][2] + r[2][0]) / s]
    if i == 1:
        s = math.sqrt(1.0 + r[1][1] - r[0][0] - r[2][2]) * 2.0
        return [(r[0][2] - r[2][0]) / s, (r[0][1] + r[1][0]) / s, 0.25 * s,
                (r[1][2] + r[2][1]) / s]
    s = math.sqrt(1.0 + r[2][2] - r[0][0] - r[1][1]) * 2.0
    return [(r[1][0] - r[0][1]) / s, (r[0][2] + r[2][0]) / s,
            (r[1][2] + r[2][1]) / s, 0.25 * s]


def mirror_across_xz(q) -> list[float]:
    """`motion.mirror_across_xz`: M R M with M = diag(1, -1, 1)."""
    r = quat_matrix(q)
    m = [1.0, -1.0, 1.0]
    rm = [[m[i] * r[i][j] * m[j] for j in range(3)] for i in range(3)]
    return matrix_quat(rm)


def quat_dot(a, b) -> float:
    return abs(sum(float(x) * float(y) for x, y in zip(a, b)))


def belt_projection(q) -> float:
    """Tool axis (rotation column 2) world-y component; world belt travel is -y."""
    r = quat_matrix(q)
    return float(r[1][2])


# --------------------------------------------------------------------------- #
# statistics (pure python; no scipy)
# --------------------------------------------------------------------------- #
def pct(vals: list[float], q: float) -> float | None:
    if not vals:
        return None
    xs = sorted(vals)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return xs[int(pos)]
    return xs[lo] * (hi - pos) + xs[hi] * (pos - lo)


def rank(vals: list[float]) -> list[float]:
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3:
        return None
    rx, ry = rank(x), rank(y)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if dx == 0.0 or dy == 0.0:
        return None
    return num / (dx * dy)


def fmt(v, nd=2) -> str:
    return "n/a" if v is None else f"{v:.{nd}f}"


# --------------------------------------------------------------------------- #
# the corpus
# --------------------------------------------------------------------------- #
def load_cell(p60) -> tuple[list[dict], dict]:
    eps: list[dict] = []
    rows = 0
    with_field = 0
    nohold: list[dict] = []
    for path in CELL:
        for ep in p60.parse_direct(str(ROOT / path)):
            ep["log"] = Path(path).name
            for leg in ep["legs"]:
                rows += 1
                leg["_ep"] = dict(idx=ep["idx"], fruit=ep["fruit"], arm=ep["arm"])
                m = _RE_DRIFT.search(leg["line"])
                if m:
                    with_field += 1
                    leg["armed"] = 1
                    leg["drift"] = float(m.group(1))
                    leg["nohold"] = bool(m.group(2))
                    if leg["nohold"]:
                        nohold.append(leg)
                else:
                    leg["drift"] = None
                    leg["nohold"] = None
            eps.append(ep)
    return eps, dict(rows=rows, with_field=with_field, nohold=nohold)


def legs_of(eps: list[dict], arm: str, name: str | None = "grasp_lift") -> list[dict]:
    out = []
    for ep in eps:
        if ep["arm"] != arm:
            continue
        for leg in ep["legs"]:
            if name is not None and leg["name"] != name:
                continue
            out.append(dict(leg, ep=ep, outcome=ep["oc"]))
    return out


def split_note_keys(eps: list[dict]) -> dict[str, int]:
    keys: dict[str, int] = {}
    for ep in eps:
        for note in re.findall(r"'([^']*)'", ep.get("notes") or ""):
            note = note.strip()
            if not note:
                continue
            key = re.sub(r"\d+(?:\.\d+)?", "#", note)
            keys[key] = keys.get(key, 0) + 1
    return keys


# --------------------------------------------------------------------------- #
# sections
# --------------------------------------------------------------------------- #
def section_p1(p60, eps, info) -> None:
    print("== P1 - the instrument ==")
    print(f"  [carry] rows            : {info['rows']} "
          f"({len(eps)} episodes over {len(CELL)} logs)")
    print(f"  rows with hold_drift=   : {info['with_field']}/{info['rows']}")
    print(f"  rows flagged (no-hold)  : {len(info['nohold'])}", end="")
    if info["nohold"]:
        groups: dict[str, int] = {}
        for l in info["nohold"]:
            key = f"{l['side']}/{l['name']}"
            groups[key] = groups.get(key, 0) + 1
        print(" -> " + ", ".join(f"{k} x{v}" for k, v in sorted(groups.items())))
    else:
        print("")
    gl = [l for l in (legs_of(eps, a) for a in FARMS) for l in l]
    nohold_gl = [l for l in gl if l["nohold"]]
    print(f"  grasp_lift legs         : {len(gl)} "
          f"(live hold {len(gl) - len(nohold_gl)}, (no-hold) {len(nohold_gl)})")
    # the hold's clear sites (PREREG section 3), counted in the source
    src = (ROOT / TASKS).read_text(errors="replace").splitlines()
    sites = [i + 1 for i, line in enumerate(src)
             if line.strip() == "arm.hold_quaternion = None"]
    print(f"  hold cleared at lines   : {sites} (tasks.py `arm.hold_quaternion = None`)")
    head = (ROOT / HEADER).read_text(errors="replace") if (ROOT / HEADER).is_file() else ""
    not_set = head.split("# NOT set", 1)[-1].splitlines()[0] if "# NOT set" in head else ""
    print(f"  FRUIT_CARRY_HOLD_QUAT   : "
          f"{'SET (would move the hold to the grip attitude, tasks.py:3488)' if 'FRUIT_CARRY_HOLD_QUAT' not in not_set else 'unset -> tasks.py:3488 not taken; the T0 hold installed by the dynamic catch stands on grasp_lift'}")
    print(f"  scenario echo           : {scenario_echo()}")
    print()


def scenario_echo() -> str:
    txt = []
    for path in CELL:
        p = ROOT / path
        if not p.is_file():
            continue
        for line in p.read_text(errors="replace").splitlines():
            if "trigger=" in line and "lateral=" in line:
                txt.append(line.strip().lstrip("[").split("]")[-1].strip())
                break
    return txt[0] if txt else "n/a"


def section_identity(eps, info) -> None:
    print("== the command identity (offline, PREREG section 3) ==")
    cfg = json.loads((ROOT / WAYPOINTS).read_text())
    file_q = {arm: cfg["grasp_quaternion"][arm] for arm in FARMS}
    t0 = top_down_quaternion("x")
    installed = {"left": mirror_across_xz(t0), "right": t0}
    print(f"  top_down('x')           : {[round(v, 6) for v in t0]}")
    for arm in FARMS:
        same = quat_dot(installed[arm], file_q[arm]) > 1.0 - 1e-9
        print(f"  {arm:5s}: catch's install vs configs/waypoints.json "
              f"-> {'IDENTICAL' if same else 'DIFFERS'} "
              f"(install {[round(v, 6) for v in installed[arm]]}, "
              f"file {[round(v, 6) for v in file_q[arm]]})")
        print(f"          belt projection of that command: "
              f"{belt_projection(installed[arm]):+.4f}")
    gl = [l for l in (legs_of(eps, a) for a in FARMS) for l in l]
    live = [l for l in gl if not l["nohold"]]
    print(f"  => on a grasp_lift leg with the hold live, `hold_drift` IS the "
          f"tilt from the commanded T0 (left) / T0' (right) attitude")
    print(f"     grasp_lift legs with the hold live: {len(live)}/{len(gl)}")
    print()


def section_p2(eps) -> dict:
    print("== P2 - the drift, per arm and per outcome (grasp_lift legs) ==")
    out = {}
    for arm in FARMS:
        legs = legs_of(eps, arm)
        out[arm] = {}
        print(f"  {arm}: {len(legs)} grasp_lift legs")
        for oc in ("placed", "cnp", "never-held"):
            sub = [l for l in legs if l["outcome"] == oc]
            drift = [l["drift"] for l in sub if l["drift"] is not None and not l["nohold"]]
            if not sub:
                continue
            out[arm][oc] = dict(n=len(sub), vals=drift,
                                med=statistics.median(drift) if drift else None,
                                lo=min(drift) if drift else None,
                                hi=max(drift) if drift else None,
                                p10=pct(drift, 0.10), p90=pct(drift, 0.90))
            print(f"    {oc:11s} n={len(sub):2d} "
                  f"drift n={len(drift):2d} "
                  f"median={fmt(out[arm][oc]['med'],1):>5s} "
                  f"range=[{fmt(out[arm][oc]['lo'],1)},{fmt(out[arm][oc]['hi'],1)}] "
                  f"p10/p90={fmt(out[arm][oc]['p10'],1)}/{fmt(out[arm][oc]['p90'],1)} deg")
    print("  per leg (drift deg, clean_slip mm, outcome):")
    for arm in FARMS:
        for l in legs_of(eps, arm):
            print(f"    {arm:5s} ep{l['ep']['idx']:2d} {l['ep']['fruit']:11s} "
                  f"{l['outcome']:10s} drift={fmt(l['drift'],1):>5s}"
                  f"{'(no-hold)' if l['nohold'] else '':>9s} "
                  f"clean_slip={l['clean_slip']:8.1f}mm "
                  f"onset_row={l['onset_row']} force@onset="
                  f"{fmt(l['force_onset'],2)}N")
    print()
    return out


def decision(p2) -> tuple[str, str]:
    """The registered decision rule (PREREG section 4)."""
    lc = p2.get("left", {}).get("cnp", {}).get("med")
    rc = p2.get("right", {}).get("cnp", {}).get("med")
    lp = p2.get("left", {}).get("placed", {}).get("med")
    ln = p2.get("left", {}).get("cnp", {}).get("n", 0)
    rn = p2.get("right", {}).get("cnp", {}).get("n", 0)
    if lc is not None and lc >= 20.0 and (rn == 0 or (rc is not None and rc >= 20.0)):
        return ("hold/IK", f"the failing legs' median drift is {lc:.1f} deg on the "
                           f"left" + (f" and {rc:.1f} deg on the right" if rc is not None
                                      else " (the right has no cnp legs in this cell)"))
    if lc is not None and lc < 10.0:
        return ("command path",
                f"the failing legs' median drift is only {lc:.1f} deg "
                f"while P62 measured the achieved belt projection at "
                f"+{P62_PROJ[0]:.4f}/+{P62_PROJ[1]:.4f}")
    if lc is None:
        return ("not evaluable", f"the left has {ln} cnp legs with a live hold; "
                                 f"no distribution to read")
    return ("undecided (report both ways)",
            f"left cnp median {lc:.1f} deg (placed {fmt(lp,1)}), "
            f"right cnp n={rn} median {fmt(rc,1)} - neither branch's threshold is met")


def section_p3(eps) -> dict:
    print("== P3 - does the drift predict the slip? (grasp_lift, live hold) ==")
    out = {}
    for arm in FARMS:
        legs = [l for l in legs_of(eps, arm)
                if l["drift"] is not None and not l["nohold"]]
        inhand = [l for l in legs if l["clean_slip"] <= INHAND_MM]
        x = [l["drift"] for l in legs]
        y = [l["clean_slip"] for l in legs]
        rho = spearman(x, y)
        rho_i = spearman([l["drift"] for l in inhand],
                         [l["clean_slip"] for l in inhand])
        esc = [l for l in legs if l["clean_slip"] > ESCAPE_MM]
        out[arm] = dict(n=len(legs), rho=rho, rho_inhand=rho_i, esc=len(esc),
                        esc_drift=statistics.median([l["drift"] for l in esc])
                        if esc else None,
                        ok_drift=statistics.median(
                            [l["drift"] for l in legs if l["clean_slip"] <= ESCAPE_MM])
                        if any(l["clean_slip"] <= ESCAPE_MM for l in legs) else None,
                        slips=[l["clean_slip"] for l in legs])
        print(f"  {arm:5s} n={len(legs):2d}  Spearman(drift, clean_slip)="
              f"{fmt(rho,3):>6s}  sign="
              f"{'negative' if (rho is not None and rho < 0) else 'positive' if rho else 'n/a'}"
              f"   | in-hand subset (slip <= {INHAND_MM:.0f} mm) n={len(inhand)}"
              f" rho={fmt(rho_i,3)}")
        print(f"        escapes (> {ESCAPE_MM:.0f} mm): {len(esc)}/{len(legs)}  "
              f"drift median escapes={fmt(out[arm]['esc_drift'],1)} / "
              f"non-escapes={fmt(out[arm]['ok_drift'],1)} deg  "
              f"clean_slip range [{min(y):.1f}, {max(y):.1f}] mm")
    pooled = [l for l in (legs_of(eps, a) for a in FARMS) for l in l
              if l["drift"] is not None and not l["nohold"]]
    pool_i = [l for l in pooled if l["clean_slip"] <= INHAND_MM]
    rho = spearman([l["drift"] for l in pooled], [l["clean_slip"] for l in pooled])
    rho_i = spearman([l["drift"] for l in pool_i], [l["clean_slip"] for l in pool_i])
    print(f"  pooled n={len(pooled)} Spearman={fmt(rho,3)}"
          f"   | in-hand n={len(pool_i)} rho={fmt(rho_i,3)}")
    out["pooled_rho"] = rho
    out["pooled_rho_inhand"] = rho_i
    print()
    return out


def section_p4(eps, p60) -> dict:
    print("== P4 - the split (report only) and the note keys ==")
    counts = {}
    for arm in FARMS:
        sub = [e for e in eps if e["arm"] == arm]
        c = {k: sum(1 for e in sub if e["oc"] == k)
             for k in ("placed", "cnp", "never-held")}
        counts[arm] = dict(c, n=len(sub))
        print(f"  {arm:5s} n={len(sub):3d}  placed={c['placed']:2d} "
              f"cnp={c['cnp']:2d} never-held={c['never-held']:2d}")
    placed = sum(1 for e in eps if e["oc"] == "placed")
    per_seed: dict[str, list[int]] = {}
    for e in eps:
        per_seed.setdefault(e["log"], [0, 0])
        per_seed[e["log"]][1] += 1
        per_seed[e["log"]][0] += 1 if e["oc"] == "placed" else 0
    print(f"  pooled: placed {placed}/{len(eps)}  per seed "
          + ", ".join(f"{k.replace('D_', '').replace('.log', '')}: {v[0]}/{v[1]}"
                      for k, v in sorted(per_seed.items())))
    keys = split_note_keys(eps)
    print("  note keys (digit-normalised):")
    for k, n in sorted(keys.items(), key=lambda kv: -kv[1]):
        print(f"    {n:3d} x {k}")
    # F3: vs P61's cell
    ctrl = []
    for path in CTRL:
        if (ROOT / path).is_file():
            ctrl += p60.parse_direct(str(ROOT / path))
    if ctrl:
        for e in ctrl:
            e["oc"] = p60.outcome(e)
        ckeys = split_note_keys(ctrl)
        new = sorted(set(keys) - set(ckeys))
        print(f"  F3 comparator (logs/p61/p2, {len(ctrl)} episodes):")
        for arm in FARMS:
            sub = [e for e in ctrl if e["arm"] == arm]
            c = {k: sum(1 for e in sub if e["oc"] == k)
                 for k in ("placed", "cnp", "never-held")}
            cur = [e for e in eps if e["arm"] == arm]
            cc = {k: sum(1 for e in cur if e["oc"] == k)
                  for k in ("placed", "cnp", "never-held")}
            print(f"    {arm:5s} cell n={len(cur):2d} placed={cc['placed']:2d} "
                  f"cnp={cc['cnp']:2d} never-held={cc['never-held']:2d}   | "
                  f"P61 n={len(sub):2d} placed={c['placed']:2d} "
                  f"cnp={c['cnp']:2d} never-held={c['never-held']:2d}")
        cplace = sum(1 for e in ctrl if e["oc"] == "placed")
        print(f"    pooled cell {placed}/{len(eps)} vs P61 {cplace}/{len(ctrl)}")
        print(f"  new note keys vs P61: {new if new else 'none'}")
        counts["new_keys"] = new
        counts["ctrl"] = len(ctrl)
    print()
    return counts


# --------------------------------------------------------------------------- #
# checks
# --------------------------------------------------------------------------- #
def load_attitude(path: str, p60) -> tuple[list[dict], list[dict]]:
    """The A1 addendum: episodes + `[attitude]` rows, joined by episode index."""
    eps = p60.parse_direct(path)
    for ep in eps:
        ep["oc"] = p60.outcome(ep)
    rows: list[dict] = []
    cur = None
    for line in (ROOT / path).read_text(errors="replace").splitlines():
        m = re.search(r"\[rl\] episode (\d+): \w+ grade=", line)
        if m:
            cur = int(m.group(1))
            continue
        m = _RE_ATT.search(line)
        if m and cur is not None:
            tilt = float(m.group(3))
            tool = [float(m.group(4)), float(m.group(5)), float(m.group(6))]
            rows.append(dict(idx=cur, side=m.group(1), name=m.group(2),
                             tilt=tilt, tool=tool))
    return eps, rows


def section_a1(p60) -> dict:
    path = "logs/p63/p2/A1_77.log"
    if not (ROOT / path).is_file():
        print(f"== addendum A1 - not run ({path} absent) ==\n")
        return {}
    eps, rows = load_attitude(path, p60)
    by_ep = {e["idx"]: e for e in eps}
    drift = {}
    for ep in eps:
        for leg in ep["legs"]:
            m = _RE_DRIFT.search(leg["line"])
            if m:
                drift[(ep["idx"], leg["side"], leg["name"])] = \
                    (float(m.group(1)), bool(m.group(2)))
    print(f"== addendum A1 - the achieved attitude per leg ({path}, reporting only) ==")
    print(f"  episodes={len(eps)}  [attitude] rows={len(rows)}  "
          f"grasp_lift rows={sum(1 for r in rows if r['name'] == 'grasp_lift')}")
    per_arm: dict[str, list[dict]] = {a: [] for a in FARMS}
    print("  per leg (grasp_lift): drift = the per-leg MAX over guarded ticks; "
          "tilt = [attitude]'s read at the leg's end (both from T0 = tool axis (0,0,-1))")
    for r in rows:
        if r["name"] != "grasp_lift":
            continue
        key = (r["idx"], r["side"], r["name"])
        if key not in drift:
            continue
        d, nohold = drift[key]
        ep = by_ep.get(r["idx"])
        arm = ep["arm"] if ep else r["side"]
        sin_t = math.sin(math.radians(max(r["tilt"], 1e-6)))
        belt = abs(r["tool"][1])
        rec = dict(drift=d, tilt=r["tilt"], tool=r["tool"], belt=belt,
                   share=(belt / sin_t) if sin_t > 1e-6 else None,
                   outcome=ep["oc"] if ep else "?", fruit=ep["fruit"] if ep else "?",
                   idx=r["idx"], arm=arm)
        per_arm[arm].append(rec)
        print(f"    {arm:5s} ep{r['idx']:2d} {rec['fruit']:11s} {rec['outcome']:10s} "
              f"drift={d:5.1f}  tilt={r['tilt']:5.1f}  "
              f"tool_y={r['tool'][1]:+.4f} (belt component)  "
              f"tool_x={r['tool'][0]:+.4f}  share={fmt(rec['share'],2)}")
    out = {}
    print("  per-arm medians (grasp_lift, live hold):")
    for arm in FARMS:
        recs = per_arm[arm]
        if not recs:
            continue
        out[arm] = dict(
            n=len(recs),
            drift=statistics.median([r["drift"] for r in recs]),
            tilt=statistics.median([r["tilt"] for r in recs]),
            belt=statistics.median([r["belt"] for r in recs]),
            share=statistics.median([r["share"] for r in recs if r["share"] is not None])
            if any(r["share"] is not None for r in recs) else None,
            gap=statistics.median([abs(r["drift"] - r["tilt"]) for r in recs]),
            gap_max=max(abs(r["drift"] - r["tilt"]) for r in recs),
            downstream=sum(1 for r in recs if r["tool"][1] < -0.05),
            upstream=sum(1 for r in recs if r["tool"][1] > 0.05),
            across=sum(1 for r in recs if abs(r["tool"][1]) <= 0.05),
        )
        print(f"    {arm:5s} n={out[arm]['n']:2d}  drift median "
              f"{fmt(out[arm]['drift'],1)}  tilt median {fmt(out[arm]['tilt'],1)}  "
              f"|tool_y| median {fmt(out[arm]['belt'],3)}  "
              f"belt share of the tilt {fmt(out[arm]['share'],2)}  "
              f"|drift-tilt| median {fmt(out[arm]['gap'],1)}")
        print(f"          tilt azimuth: downstream (tool_y < -0.05) "
              f"{out[arm]['downstream']}/{out[arm]['n']}, upstream (> +0.05) "
              f"{out[arm]['upstream']}/{out[arm]['n']}, across |y| <= 0.05 "
              f"{out[arm]['across']}/{out[arm]['n']}; |drift-tilt| max "
              f"{fmt(out[arm]['gap_max'],1)} deg")
    print()
    return out


def run_checks(p60, eps, info, p2, p3, p4, a1) -> int:
    bad = 0

    def ok(cond, msg):
        nonlocal bad
        print(f"  {'PASS' if cond else 'FAIL'}: {msg}")
        if not cond:
            bad += 1

    print("== checks ==")
    ok(info["rows"] > 0, f"the cell has [carry] rows ({info['rows']})")
    ok(info["with_field"] == info["rows"],
       f"every [carry] row carries hold_drift= ({info['with_field']}/{info['rows']})")
    ok(all(l["drift"] is not None and 0.0 <= l["drift"] <= 180.0
           for e in eps for l in e["legs"]),
       "every drift is a finite angle in [0, 180] deg")
    ok(all(len(e["legs"]) > 0 for e in eps if e["oc"] != "never-held"),
       "every grasped attempt has at least one [carry] row")
    # the arm label agrees between the episode and its legs
    ok(all(l["side"] == e["arm"] for e in eps for l in e["legs"]),
       "every leg's side matches its episode's arm")
    # P60's parser (the P61-P5 check) reads every row
    rows = sum(1 for e in eps for l in e["legs"])
    parsed = 0
    for path in CELL:
        for line in (ROOT / path).read_text(errors="replace").splitlines():
            m = re.search(r"\[carry\] (\w+) (\w+): (.*)$", line)
            if m:
                leg = p60.parse_leg(m.group(3))
                if leg.get("clean_slip") is not None and leg.get("ticks") is not None:
                    parsed += 1
    ok(parsed == rows, f"logs/p60/p3/report.py parse_leg reads all {rows} rows")
    # the command identity
    cfg = json.loads((ROOT / WAYPOINTS).read_text())
    ok(quat_dot(mirror_across_xz(top_down_quaternion("x")),
                cfg["grasp_quaternion"]["left"]) > 1.0 - 1e-9,
       "the catch's left install == configs/waypoints.json's left grasp (T0)")
    # no-hold is expected on 0 grasp_lift legs (PREREG Pa)
    gl_nohold = [l for l in (legs_of(eps, a) for a in FARMS) for l in l if l["nohold"]]
    print(f"  {'PASS' if not gl_nohold else 'NOTE'}: no-hold on grasp_lift legs "
          f"= {len(gl_nohold)} (PREREG Pa predicted 0)")
    ok(all(l["name"].startswith("place") for l in info["nohold"]),
       "every (no-hold) row is a place leg (the hold is cleared for name != grasp_lift)")
    # the A1 addendum: the two instruments read the *same* angle (both from the
    # T0 command, tool axis (0,0,-1)) but at different ticks - the drift is a
    # per-leg max over the guarded ticks, the tilt a read at the leg's end after
    # one more step + the settle, so they agree to a few degrees, not exactly.
    if a1:
        for arm in FARMS:
            rec = a1.get(arm)
            if not rec:
                continue
            ok(rec["gap"] is not None and rec["gap"] <= 6.0,
               f"A1 {arm}: |hold_drift - [attitude] tilt| median "
               f"{fmt(rec['gap'], 1)} deg <= 6 (same angle, different tick)")
    # tree md5s identical before/after the batch
    before = ROOT / "logs/p63/p2/tree_md5_before.txt"
    after = ROOT / "logs/p63/p2/tree_md5_after.txt"
    ok(before.is_file() and after.is_file()
       and before.read_text() == after.read_text(),
       "tree md5s identical before/after the batch")
    # every log finished (has the rollout summary)
    for path in CELL:
        txt = (ROOT / path).read_text(errors="replace")
        ok("[rl] rollout" in txt or "episodes" in txt,
           f"{Path(path).name} carries the rollout summary")
    print(f"  {'PASS' if bad == 0 else 'FAIL'}: {bad} failure(s)")
    return bad


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    p60 = load_p60()
    eps, info = load_cell(p60)
    for ep in eps:
        ep["oc"] = p60.outcome(ep)
    missing = [p for p in CELL if not (ROOT / p).is_file()]
    if missing:
        print(f"missing logs: {missing}")
        return 2

    print("# P63 phase 2 - where the left's 26-29 deg goes (hold/IK vs command path)")
    print(f"# cell: {', '.join(CELL)}")
    print(f"# comparator (F3): {', '.join(CTRL)}")
    print()
    section_p1(p60, eps, info)
    section_identity(eps, info)
    p2 = section_p2(eps)
    verdict, why = decision(p2)
    print(f"== the decision (PREREG section 4) ==\n  VERDICT: {verdict}\n  because: {why}\n")
    p3 = section_p3(eps)
    p4 = section_p4(eps, p60)
    a1 = section_a1(p60)

    if args.check:
        return 1 if run_checks(p60, eps, info, p2, p3, p4, a1) else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
