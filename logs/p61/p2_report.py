#!/usr/bin/env python3
"""P61 phase 2 report: the **direction** of the direct line's carry slip.

Reads the registered cell (`logs/p61/p2/S_{77,101,202}.log`, `FRUIT_CARRY_DIAG=1`
+ `FRUIT_MOTION_REPORT=1`), the F3 comparator (`logs/p60/p3/D_{77,101,202}.log`,
the same scenario/checkpoint on the pre-instrument tree), and the offline frame
map from `configs/waypoints_oriented.json`.

    python3 logs/p61/p2_report.py            # print
    python3 logs/p61/p2_report.py --check    # + structural assertions

Definitions are fixed in `logs/p61/PREREG.md` (written before the run):
`escape` = `clean_slip_max > 50 mm`, `transient` = `5 < clean_slip_max <= 50 mm`,
the primary unit is an attempt's FIRST escaping leg (P60 §3.4's convention),
`dominant axis` = `argmax |component|`, `mixed` when the runner-up is
`>= 0.70 x` the largest component.

The frame map is **not** fitted here: it is `R_arm^T v_world` with `R_arm` the
calibrated grasp quaternion (`(w,x,y,z)`, `tasks.py:213`) and `v_world` the
candidate world direction, computed in `frame_map()` from the config file.
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
CELL = ["logs/p61/p2/S_77.log", "logs/p61/p2/S_101.log", "logs/p61/p2/S_202.log"]
CTRL = ["logs/p60/p3/D_77.log", "logs/p60/p3/D_101.log", "logs/p60/p3/D_202.log"]
P60_REPORT = "logs/p60/p3/report.py"
WAYPOINTS = "configs/waypoints_oriented.json"
B_METRIC = "logs/w8/B_metric.py"

ESCAPE_MM = 50.0   # PREREG §4 P2
TRANSIENT_MM = 5.0  # PREREG §4 P2 (W8-B's escape floor)
MIXED_RATIO = 0.70  # PREREG §3 decision table
DEADZONE_MM = 5.0   # report-level sign-triple dead zone

_RE_SLIP = re.compile(
    r"slip_xyz=\(([-+]?[\d.]+),([-+]?[\d.]+),([-+]?[\d.]+)\)mm"
)
_RE_CLEAN = re.compile(r"clean_slip_max=([\d.]+)mm")
_RE_MOTION = re.compile(r"\[motion\] carry (\w+): (.*)$")
_RE_MOTION_V = re.compile(
    r"steps=(\d+), \|v\|max=([\d.]+) m/s, \|a\|max=([\d.]+) m/s\^2"
)
_RE_MOTION_CMD = re.compile(r"\|v\|cmd=([\d.]+) \|a\|cmd=([\d.]+)")
_RE_MOTION_REC = re.compile(r"recoveries=(\d+):")


# --------------------------------------------------------------------------- #
# the P60 parser, imported as-is: that IS the P5 "still parses" check
# --------------------------------------------------------------------------- #
def load_p60():
    spec = importlib.util.spec_from_file_location("p60_report", ROOT / P60_REPORT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# --------------------------------------------------------------------------- #
# the offline frame map (PREREG §3)
# --------------------------------------------------------------------------- #
def quat_matrix(q) -> list[list[float]]:
    w, x, y, z = (float(v) for v in q)
    n = math.sqrt(w * w + x * x + y * y + z * z)
    w, x, y, z = w / n, x / n, y / n, z / n
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]


def rot_t_vec(m, v) -> list[float]:
    return [sum(m[j][i] * float(v[j]) for j in range(3)) for i in range(3)]


CANDIDATES = [
    ("world -y (belt travel)", (0.0, -1.0, 0.0)),
    ("world -z (down / lift axis)", (0.0, 0.0, -1.0)),
    ("world +z (up)", (0.0, 0.0, 1.0)),
    ("world +x (across belt)", (1.0, 0.0, 0.0)),
    ("world -x (across belt)", (-1.0, 0.0, 0.0)),
]

#: The grasp's own axes in world coordinates. Column 1 is the **jaw opening
#: axis** (`kinematic_gripper.py:407`, `axis = rot[:, 1]` - the pads are placed
#: at `centre +/- axis*gap/2`), column 2 the **tool axis** the fingers extend
#: along (`down = rot[:, 2]`, the wrist sits behind the pads along `-down`).
#: NB the `_carry_attitude` docstring's "jaws close along X" holds for a
#: top-down attitude, not for these calibrated quaternions: here the jaw axis is
#: 30 deg off the belt (`cos = 0.858`) and the tool axis 59 deg (`cos = 0.513`),
#: so "belt drag" and "slid through the jaws" are **not separable by direction
#: alone** (PREREG amendment A1).
GRASP_AXES = [
    ("tool axis (finger length)", 2),
    ("jaw opening axis", 1),
    ("hand x (up/down)", 0),
]


def frame_map() -> dict:
    cfg = json.loads((ROOT / WAYPOINTS).read_text(encoding="utf-8"))
    quats = cfg["grasp_quaternion"]
    rots = {arm: quat_matrix(q) for arm, q in quats.items()}
    out = {"raw": {}, "rots": rots, "quats": quats}
    for arm, rot in rots.items():
        out["raw"][arm] = {
            name: rot_t_vec(rot, v) for name, v in CANDIDATES
        }
    # the arms' relation: R_right ?= M R_left M^T with M = diag(-1, +1, -1)
    left = rots["left"]
    right = rots["right"]
    m = [-1.0, 1.0, -1.0]
    pred = [[m[i] * left[i][j] * m[j] for j in range(3)] for i in range(3)]
    out["mirror_err"] = max(
        abs(pred[i][j] - right[i][j]) for i in range(3) for j in range(3)
    )
    return out


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #
def parse_cell(path: str, p60) -> list[dict]:
    """Episodes + `[carry]` legs (p60's parser) + `slip_xyz` + `[motion]` rows."""
    eps = p60.parse_direct(path)
    # independent scan: the slip token and the clean_slip it must match, in file order
    slips: list[tuple[float, tuple[float, float, float], str]] = []
    motions: list[dict] = []
    cur_idx = None
    for line in open(path, encoding="utf-8", errors="replace"):
        m = p60._RE_OPEN.search(line)
        if m:
            cur_idx = int(m.group(1))
            continue
        if p60._RE_CLOSE.search(line):
            cur_idx = None
            continue
        m = re.search(r"\[carry\] (\w+) (\w+): (.*)$", line)
        if m:
            clean = _RE_CLEAN.search(m.group(3))
            slip = _RE_SLIP.search(m.group(3))
            vec = None
            if slip:
                vec = (float(slip.group(1)), float(slip.group(2)), float(slip.group(3)))
            slips.append(
                (float(clean.group(1)) if clean else float("nan"), vec, line.rstrip())
            )
            continue
        m = _RE_MOTION.search(line)
        if m and "clearance" not in m.group(1):
            body = m.group(2)
            v = _RE_MOTION_V.search(body)
            cmd = _RE_MOTION_CMD.search(body)
            rec = _RE_MOTION_REC.search(body)
            motions.append(
                dict(
                    ep=cur_idx,
                    name=m.group(1),
                    vmax=float(v.group(2)) if v else None,
                    amax=float(v.group(3)) if v else None,
                    vcmd=float(cmd.group(1)) if cmd else None,
                    acmd=float(cmd.group(2)) if cmd else None,
                    recoveries=int(rec.group(1)) if rec else None,
                    line=line.rstrip(),
                )
            )
    n_legs = sum(len(e["legs"]) for e in eps)
    if len(slips) != n_legs:
        raise SystemExit(
            f"{path}: {len(slips)} [carry] rows by the slip scan but {n_legs} legs "
            "by the P60 parser - the row format broke (P5)"
        )
    k = 0
    for ep in eps:
        ep["motions"] = []
        for leg in ep["legs"]:
            clean, vec, line = slips[k]
            k += 1
            leg["slip_xyz"] = vec
            leg["clean_printed"] = clean
            leg["raw_line"] = line
            leg["ep"] = ep["idx"]
            leg["arm"] = ep["arm"]
            leg["src"] = Path(path).name
    for mo in motions:
        for ep in eps:
            if ep["idx"] == mo["ep"]:
                ep["motions"].append(mo)
                break
    return eps


def parse_control(path: str, p60) -> list[dict]:
    return p60.parse_direct(path)


# --------------------------------------------------------------------------- #
# readings
# --------------------------------------------------------------------------- #
def vec_norm(v) -> float:
    return math.sqrt(sum(float(c) ** 2 for c in v))


def dominant(v) -> str:
    mags = {"x": abs(v[0]), "y": abs(v[1]), "z": abs(v[2])}
    order = sorted(mags, key=lambda k: mags[k], reverse=True)
    if mags[order[1]] >= MIXED_RATIO * mags[order[0]]:
        return f"mixed({order[0]}>{order[1]})"
    return order[0]


def unit(v):
    n = vec_norm(v)
    return None if n <= 0 else tuple(c / n for c in v)


def mean_dir(vecs):
    """Mean of the unit vectors (the mean direction), and its cosine spread."""
    us = [unit(v) for v in vecs]
    us = [u for u in us if u is not None]
    if not us:
        return None
    m = [sum(u[i] for u in us) / len(us) for i in range(3)]
    n = vec_norm(m)
    return None if n <= 0 else tuple(c / n for c in m)


def cos(a, b) -> float:
    return sum(x * y for x, y in zip(a, b))


def pairwise_mean_cos(vecs) -> float | None:
    us = [unit(v) for v in vecs]
    us = [u for u in us if u is not None]
    if len(us) < 2:
        return None
    vals = [
        cos(us[i], us[j])
        for i in range(len(us))
        for j in range(i + 1, len(us))
    ]
    return sum(vals) / len(vals)


def fmt(vals, nd=1) -> str:
    vals = [v for v in vals if v is not None]
    if not vals:
        return "n/a"
    if len(vals) == 1:
        return f"{vals[0]:.{nd}f}"
    return (
        f"{statistics.median(vals):.{nd}f} [{min(vals):.{nd}f}-{max(vals):.{nd}f}]"
    )


def sign_triple(v, deadzone: float = 0.0) -> tuple[int, int, int]:
    def s(c):
        if abs(c) <= deadzone:
            return 0
        return 1 if c > 0 else -1

    return (s(v[0]), s(v[1]), s(v[2]))


def escapes(eps, arm=None, name=None) -> list[dict]:
    out = []
    for ep in eps:
        if arm and ep["arm"] != arm:
            continue
        for leg in ep["legs"]:
            if name and leg["name"] != name:
                continue
            if leg.get("clean_printed", 0.0) > ESCAPE_MM:
                out.append(leg)
    return out


def first_escape(eps, arm=None) -> list[dict]:
    out = []
    for ep in eps:
        if arm and ep["arm"] != arm:
            continue
        for leg in ep["legs"]:
            if leg.get("clean_printed", 0.0) > ESCAPE_MM:
                out.append(leg)
                break
    return out


def transients(eps, arm=None) -> list[dict]:
    out = []
    for ep in eps:
        if arm and ep["arm"] != arm:
            continue
        for leg in ep["legs"]:
            c = leg.get("clean_printed", 0.0)
            if TRANSIENT_MM < c <= ESCAPE_MM:
                out.append(leg)
    return out


#: A `[carry]` displacement above this is **not an in-hand slide**: W8-B's escape
#: corpus tops at 957 mm, the hand's own transfer is 0.5-0.6 m, and a lost
#: payload's downstream `place0` row reads 1.0-1.5 m. The rows above it are
#: ejections/kicks (one here is 49.6 m, `sep@onset` already at the 98 mm stop)
#: and respawn teleports. Registered as amendment A3.
LOST_MM = 1000.0


def first_slide(eps, arm=None) -> list[dict]:
    """The attempt's first **in-hand slide**: a `grasp_lift` leg, 50-1000 mm.

    `place0` rows are excluded by construction: once the payload is out of the
    hand the metric measures the hand's motion away from it (P60 §3.4's reading
    rule), so a transfer-leg vector is not a slip.
    """
    out = []
    for ep in eps:
        if arm and ep["arm"] != arm:
            continue
        for leg in ep["legs"]:
            c = leg.get("clean_printed", 0.0)
            if leg["name"] == "grasp_lift" and ESCAPE_MM < c <= LOST_MM:
                out.append(leg)
                break
    return out


def ejecta(eps, arm=None) -> list[dict]:
    out = []
    for ep in eps:
        if arm and ep["arm"] != arm:
            continue
        for leg in ep["legs"]:
            if leg["name"] == "grasp_lift" and leg.get("clean_printed", 0.0) > LOST_MM:
                out.append(leg)
    return out


def downstream(eps, arm=None) -> list[dict]:
    """`place0` rows past the escape bar: the downstream view, never a slip."""
    out = []
    for ep in eps:
        if arm and ep["arm"] != arm:
            continue
        for leg in ep["legs"]:
            if leg["name"].startswith("place") and leg.get("clean_printed", 0.0) > ESCAPE_MM:
                out.append(leg)
    return out


def world_vectors(legs, rot) -> list[tuple[float, float, float]]:
    """`R_arm @ unit(slip_xyz)` - the same vectors seen in world axes.

    Derived (not a registered endpoint): an orthogonal transform of the printed
    field, so it adds no information, only legibility. World frame: Z up, belt
    travel along -Y, jaws close along X (`_carry_attitude`'s docstring).
    """
    out = []
    for leg in legs:
        u = unit(leg["slip_xyz"])
        if u is None:
            continue
        out.append(tuple(sum(rot[i][j] * u[j] for j in range(3)) for i in range(3)))
    return out


def world_dominant(w) -> str:
    mags = {"x": abs(w[0]), "y": abs(w[1]), "z": abs(w[2])}
    order = sorted(mags, key=lambda k: mags[k], reverse=True)
    if mags[order[1]] >= MIXED_RATIO * mags[order[0]]:
        return f"mixed({order[0]}>{order[1]})"
    return order[0]


# --------------------------------------------------------------------------- #
# sections
# --------------------------------------------------------------------------- #
def section_p1(cell: dict) -> dict:
    rows = 0
    missing = 0
    worst = (0.0, None)
    over_letter = []
    over_bound = []
    for path, eps in cell.items():
        for ep in eps:
            for leg in ep["legs"]:
                rows += 1
                v = leg.get("slip_xyz")
                if v is None:
                    missing += 1
                    continue
                d = abs(vec_norm(v) - leg["clean_printed"])
                if d > worst[0]:
                    worst = (d, (path, ep["idx"], leg["name"], v,
                                 leg["clean_printed"]))
                if d > 0.1 + 1e-9:
                    over_letter.append((path, ep["idx"], leg["name"], v, d))
                if d > 0.15 + 1e-9:
                    over_bound.append((path, ep["idx"], leg["name"], v, d))
    print("\n== P1: the instrument's identity, |slip_xyz| == clean_slip_max ==")
    print(f"  [carry] rows            : {rows}")
    print(f"  rows with slip_xyz      : {rows - missing}")
    print(f"  max |norm - clean|      : {worst[0]:.3f} mm")
    if worst[1]:
        p, e, n, v, c = worst[1]
        print(f"    worst row             : {Path(p).name} ep{e} {n} "
              f"slip_xyz=({v[0]:.1f},{v[1]:.1f},{v[2]:.1f}) clean={c:.1f}")
    print(f"  rows > 0.1 mm (letter)  : {len(over_letter)}")
    print(f"  rows > 0.15 mm (bound)  : {len(over_bound)}  (PREREG: >0.15 is F1)")
    for row in over_letter[:8]:
        p, e, n, v, d = row
        print(f"    print-rounding        : {Path(p).name} ep{e} {n} "
              f"({v[0]:.1f},{v[1]:.1f},{v[2]:.1f}) d={d:.3f} mm")
    return dict(rows=rows, missing=missing, worst=worst[0],
                over_letter=len(over_letter), over_bound=len(over_bound))


def section_p2(cell: dict, fmap: dict) -> dict:
    """The direction read. **World frame is primary** (belt = world -y).

    `slip_xyz` is in the LEG (TCP) frame at the tick of the maximum, and that
    frame is **arm-specific**: `R_right = M R_left M^T`, `M = diag(-1,+1,-1)`, so
    the left's hand +y and the right's hand +y are **61.9 deg apart in the world**
    (both are 0.858 on world -y, but their x/z components are negated). A per-arm
    leg-frame "+y" comparison is therefore invalid; every row is mapped to the
    world with `R_arm = quaternion_matrix(grasp_quaternion[side])` and the arms
    are compared there. The mapping is an **approximation**: `grasp_quaternion` is
    the calibrated *grasp* attitude and the carry releases the attitude hold
    (`tasks.py:8398`), so the achieved attitude is not logged in this cell; the
    concentration statistic below bounds how much that smears the reading.
    """
    print("\n== P2: the direction (primary, **world frame**; belt = world -y) ==")
    print(f"  escape = clean_slip_max > {ESCAPE_MM:.0f} mm; unit = the attempt's "
          f"first grasp_lift leg in ({ESCAPE_MM:.0f}, {LOST_MM:.0f}] mm")
    all_eps = [ep for eps in cell.values() for ep in eps]
    arms = sorted({ep["arm"] for ep in all_eps})
    summary = {}
    print("\n  -- the frame map (offline, configs/waypoints_oriented.json) --")
    print(f"  R_right == M R_left M^T (M = diag(-1,+1,-1)) : max err "
          f"{fmap['mirror_err']:.2e}  (a 180 deg turn about the belt axis)")
    for arm in ("left", "right"):
        rot = fmap["rots"][arm]
        print(f"  {arm:5s} hand axes in world: x=({rot[0][0]:+.3f},{rot[1][0]:+.3f},"
              f"{rot[2][0]:+.3f})  y=({rot[0][1]:+.3f},{rot[1][1]:+.3f},{rot[2][1]:+.3f})"
              f"  z=({rot[0][2]:+.3f},{rot[1][2]:+.3f},{rot[2][2]:+.3f})")
    print("  candidate world dir          ->  L hand frame          R hand frame")
    for name, _v in CANDIDATES:
        lv = fmap["raw"]["left"][name]
        rv = fmap["raw"]["right"][name]
        print(f"  {name:28s} -> ({lv[0]:+.3f},{lv[1]:+.3f},{lv[2]:+.3f})  "
              f"({rv[0]:+.3f},{rv[1]:+.3f},{rv[2]:+.3f})")
    print("  the grasp's own axes in world (rot columns):")
    for arm in ("left", "right"):
        rot = fmap["rots"][arm]
        for name, col in GRASP_AXES:
            w = [rot[i][col] for i in range(3)]
            print(f"    {arm:5s} {name:26s} world=({w[0]:+.3f},{w[1]:+.3f},{w[2]:+.3f})"
                  f"  cos(belt -y)={-w[1]:+.3f}")

    for arm in arms:
        reg = first_escape(all_eps, arm)
        prim = first_slide(all_eps, arm)
        allesc = escapes(all_eps, arm)
        trans = transients(all_eps, arm)
        eject = ejecta(all_eps, arm)
        down = downstream(all_eps, arm)
        dev = [leg["slip_xyz"] for leg in prim if leg.get("slip_xyz")]
        print(f"\n  -- {arm} --")
        print(f"  attempts {sum(1 for e in all_eps if e['arm'] == arm)}; "
              f"escaping attempts (registered, first leg > {ESCAPE_MM:.0f}mm) "
              f"{len(reg)}; in-hand slides {len(prim)}; ejecta "
              f"(grasp_lift > {LOST_MM:.0f}mm) {len(eject)}; downstream "
              f"(place > {ESCAPE_MM:.0f}mm) {len(down)}; escaping legs "
              f"{len(allesc)}; transient legs {len(trans)}")
        if reg and len(reg) != len(prim):
            rv = [l["slip_xyz"] for l in reg if l.get("slip_xyz")]
            rmd = mean_dir(rv)
            ry = [v[1] for v in rv]
            print(f"  as registered (all {len(rv)} first-escaping legs, LEG frame): "
                  f"mean y {statistics.mean(ry):+.1f} mm, mean dir "
                  f"({rmd[0]:+.3f},{rmd[1]:+.3f},{rmd[2]:+.3f})  "
                  f"<- the extra legs are the ejecta/downstream rows below")
        for leg in eject + down:
            print(f"    EXCLUDED (A3) {leg['src']} ep{leg['ep']} {leg['name']} "
                  f"{leg['clean_printed']:.1f}mm "
                  f"({leg['slip_xyz'][0]:+.1f},{leg['slip_xyz'][1]:+.1f},"
                  f"{leg['slip_xyz'][2]:+.1f})  onset={leg.get('onset_row')} "
                  f"sep@onset={leg.get('sep_onset')} contacts@onset="
                  f"{leg.get('contacts_onset')}")
        if not dev:
            print("  no in-hand slide -> no direction read")
            summary[arm] = dict(n=0, n_reg=len(reg), n_eject=len(eject),
                                n_trans=len(trans))
            continue
        rot = fmap["rots"][arm]
        # ---- PRIMARY: world frame ------------------------------------- #
        wmm = [
            tuple(sum(rot[i][j] * v[j] for j in range(3)) for i in range(3))
            for v in dev
        ]
        wu = world_vectors(prim, rot)
        wy = [w[1] for w in wmm]
        wdom_map: dict[str, int] = {}
        for w in wu:
            k = world_dominant(w)
            wdom_map[k] = wdom_map.get(k, 0) + 1
        md_leg = mean_dir(dev)
        wd = tuple(sum(rot[i][j] * md_leg[j] for j in range(3)) for i in range(3))
        mw = [statistics.mean(w[i] for w in wmm) for i in range(3)]
        print("  WORLD (primary; belt = -y):")
        print("    dominant axis        : "
              + ", ".join(f"{k}={v}" for k, v in sorted(wdom_map.items())))
        print(f"    signed mean world-y  : {statistics.mean(wy):+.1f} mm  (median "
              f"{statistics.median(wy):+.1f} [{min(wy):+.1f}..{max(wy):+.1f}])  "
              f"y<0 {sum(1 for y in wy if y < 0)}/{len(wy)}")
        print(f"    mean world vector    : ({mw[0]:+.1f},{mw[1]:+.1f},{mw[2]:+.1f}) mm "
              f"| mean unit dir ({wd[0]:+.3f},{wd[1]:+.3f},{wd[2]:+.3f})")
        print(f"    axis shares          : +x {wd[0]:+.3f} | belt -y {-wd[1]:+.3f} | "
              f"-z {-wd[2]:+.3f}   per-leg: x>0 "
              f"{sum(1 for w in wu if w[0] > 0)}/{len(wu)}, y<0 "
              f"{sum(1 for w in wu if w[1] < 0)}/{len(wu)}, z<0 "
              f"{sum(1 for w in wu if w[2] < 0)}/{len(wu)}")
        # ---- mechanism decomposition: leg frame (arm-specific) --------- #
        doms: dict[str, int] = {}
        for v in dev:
            k = dominant(v)
            doms[k] = doms.get(k, 0) + 1
        xs = [v[0] for v in dev]
        ys = [v[1] for v in dev]
        zs = [v[2] for v in dev]
        print("  LEG frame (mechanism only; hand +y is 61.9 deg apart between the "
              "arms, so do not compare it across arms):")
        print("    dominant axis        : "
              + ", ".join(f"{k}={v}" for k, v in sorted(doms.items())))
        print(f"    components (mm)      : x {fmt(xs)} | y {fmt(ys)} | z {fmt(zs)}")
        print(f"    signed mean y        : {statistics.mean(ys):+.1f} mm (median "
              f"{statistics.median(ys):+.1f}); y>0 on "
              f"{sum(1 for y in ys if y > 0)}/{len(ys)}")
        print(f"    mean unit dir        : ({md_leg[0]:+.3f},{md_leg[1]:+.3f},"
              f"{md_leg[2]:+.3f})")
        print("    grasp-axis shares    : " + " | ".join(
            f"{name.split(' (')[0]} {md_leg[col]:+.3f}" for name, col in GRASP_AXES
        ) + "   (a belt drag would put +0.034/+0.858/+0.513 on x/y/z)")
        print(f"    cos(mean dir, world) : " + " | ".join(
            f"{name.split(' (')[0].replace('world ', '')} "
            f"{cos(md_leg, tuple(fmap['raw'][arm][name])):+.3f}"
            for name, _ in CANDIDATES
        ))
        print(f"    concentration        : "
              + ("n/a (n<2)" if pairwise_mean_cos(dev) is None
                 else f"{pairwise_mean_cos(dev):+.3f} (mean pairwise cos)"))
        if allesc and len(allesc) != len(prim):
            print(f"    secondary (all escaping legs, n={len(allesc)}): "
                  + ", ".join(
                      f"{k}={v}" for k, v in sorted(
                          {d: sum(1 for l in allesc
                                  if dominant(l['slip_xyz']) == d)
                           for d in {dominant(l['slip_xyz']) for l in allesc}}.items()
                      )
                  ))
        if trans:
            print("    transients (5-50 mm) : " + "; ".join(
                f"{l['src']}:ep{l['ep']} {l['name']} {l['clean_printed']:.1f}mm "
                f"({l['slip_xyz'][0]:+.1f},{l['slip_xyz'][1]:+.1f},"
                f"{l['slip_xyz'][2]:+.1f})" for l in trans
            ))
        summary[arm] = dict(
            n=len(dev), mean_world_y=statistics.mean(wy),
            median_world_y=statistics.median(wy),
            world_y_neg=sum(1 for y in wy if y < 0), wdom=wdom_map,
            mean_world=mw, world_dir=wd, n_reg=len(reg), n_eject=len(eject),
            n_down=len(down), n_trans=len(trans), doms=doms,
            mean_leg_dir=md_leg, mean_leg_y=statistics.mean(ys),
            leg_y_pos=sum(1 for y in ys if y > 0),
            conc=pairwise_mean_cos(dev),
        )
    return summary


def p60_outcome_placed(ep: dict) -> bool:
    """P60's outcome triple: `placed` is the episode's own flag."""
    return bool(ep.get("placed"))


def section_p3(cell: dict) -> dict:
    print("\n== P3: the motion contrast on grasp_lift (the hand's own speed) ==")
    all_eps = [ep for eps in cell.values() for ep in eps]
    arms = sorted({ep["arm"] for ep in all_eps})
    out = {}
    for arm in arms:
        rows = []
        placed_rows = []
        for ep in all_eps:
            if ep["arm"] != arm:
                continue
            lift = [m for m in ep["motions"] if m["name"] == "grasp_lift"]
            if lift:
                rows.append(lift[0])
                if p60_outcome_placed(ep):
                    placed_rows.append(lift[0])
        if not rows:
            print(f"  {arm:5s} no [motion] grasp_lift row")
            out[arm] = dict(n=0)
            continue
        for tag, sub in (("all", rows), ("placed", placed_rows)):
            if not sub:
                continue
            vm = [r["vmax"] for r in sub if r["vmax"] is not None]
            am = [r["amax"] for r in sub if r["amax"] is not None]
            vc = [r["vcmd"] for r in sub if r["vcmd"] is not None]
            ac = [r["acmd"] for r in sub if r["acmd"] is not None]
            rc = [r["recoveries"] for r in sub if r["recoveries"] is not None]
            print(f"  {arm:5s} {tag:6s} n={len(sub):2d}  |v|max {fmt(vm,3)} m/s   "
                  f"|a|max {fmt(am,3)} m/s^2   |v|cmd {fmt(vc,3)} |a|cmd {fmt(ac,3)}   "
                  f"recoveries sum={sum(rc)} max={max(rc) if rc else 0}")
            if tag == "all":
                out[arm] = dict(n=len(sub), vmax=vm, amax=am, vcmd=vc, acmd=ac,
                                rec=rc)
            else:
                out.setdefault(arm, {})["placed_vmax"] = vm
                out[arm]["placed_amax"] = am
    if len(arms) == 2 and out.get("left", {}).get("vmax") and \
            out.get("right", {}).get("vmax"):
        lm = statistics.median(out["left"]["vmax"])
        rm = statistics.median(out["right"]["vmax"])
        la = statistics.median(out["left"]["amax"])
        ra = statistics.median(out["right"]["amax"])
        print(f"  median ratio L/R       : |v|max {lm / rm:.3f}x   "
              f"|a|max {la / ra:.3f}x")
    return out


def section_p4(cell: dict, ctrl: dict, p60) -> dict:
    print("\n== P4: the split (report only) and the note keys ==")
    all_eps = [ep for eps in cell.values() for ep in eps]
    ctrl_eps = [ep for eps in ctrl.values() for ep in eps]
    for tag, eps in (("cell", all_eps), ("P60", ctrl_eps)):
        arms = sorted({e["arm"] for e in eps})
        line = []
        for arm in arms:
            sub = [e for e in eps if e["arm"] == arm]
            c = {k: sum(1 for e in sub if p60.outcome(e) == k)
                 for k in ("placed", "cnp", "never-held")}
            line.append(f"{arm} {c['placed']}/{c['cnp']}/{c['never-held']} (n={len(sub)})")
        print(f"  {tag:5s} placed/cnp/never-held: " + " | ".join(line)
              + f"  pooled placed "
              f"{sum(1 for e in eps if p60.outcome(e) == 'placed')}/{len(eps)}")

    def keys(eps):
        out = set()
        for e in eps:
            if e["success"]:
                continue
            text = e["notes"].strip("[]").strip()
            out.add("empty note" if not text else re.sub(r"[-+0-9.]+", "#", text))
        return out

    kc = keys(all_eps)
    k0 = keys(ctrl_eps)
    print(f"  note keys cell  : {sorted(kc)}")
    print(f"  note keys P60   : {sorted(k0)}")
    print(f"  NEW keys        : {sorted(kc - k0) or 'none'}")
    return dict(placed=sum(1 for e in all_eps if p60.outcome(e) == "placed"),
                n=len(all_eps), new_keys=sorted(kc - k0))


def section_p5(cell: dict, p60, p1: dict) -> dict:
    print("\n== P5: the row format still parses (read-only) ==")
    ok_fields = 0
    bad_fields = []
    for path, eps in cell.items():
        for ep in eps:
            for leg in ep["legs"]:
                parsed = p60.parse_leg(leg["raw_line"].split(": ", 1)[1])
                if "clean_slip" not in parsed or "in_hand_vmax" not in parsed:
                    bad_fields.append((path, ep["idx"], leg["name"]))
                elif abs(parsed["clean_slip"] - leg["clean_printed"]) > 1e-9:
                    bad_fields.append((path, ep["idx"], leg["name"]))
                else:
                    ok_fields += 1
    print(f"  logs/p60/p3/report.py parse_leg on the new rows : "
          f"{ok_fields} ok, {len(bad_fields)} bad")
    for row in bad_fields[:5]:
        print(f"    BAD {row}")
    bsrc = (ROOT / B_METRIC).read_text(encoding="utf-8")
    b_ok = (
        "clean_slip(t) = || R(t)^T (fruit(t) - pads(t))" in bsrc
        and "hand_rel" in bsrc
    )
    print("  logs/w8/B_metric.py reads trace-JSON rows (hand_rel), untouched by "
          f"this change: {'ok' if b_ok else 'CHECK'}")
    print("    (its clean_slip is the same framed quantity; the trace schema and "
          "the [carry] text are independent)")
    return dict(ok=ok_fields, bad=len(bad_fields), b_ok=b_ok)


def verdict(p1: dict, p2: dict, p3: dict) -> str:
    """The verdict is read in the **world** frame (belt = world -y)."""
    print("\n== verdict (world frame; belt = -y) ==")
    if p1["over_bound"] or p1["missing"]:
        print(f"  F1: the instrument failed ({p1['over_bound']} rows > 0.15 mm, "
              f"{p1['missing']} rows without slip_xyz) -> no interpretation")
        return "instrument-failure"
    left = p2.get("left", {})
    right = p2.get("right", {})
    if not left.get("n"):
        print("  the left has no escaping attempt -> no direction read")
        return "no-read"
    wd = left["world_dir"]
    belt = -wd[1]
    dom = max(left["wdom"], key=lambda k: left["wdom"][k])
    print(f"  left: n={left['n']}  world dominant {left['wdom']}  "
          f"mean world-y {left['mean_world_y']:+.1f} mm "
          f"(median {left['median_world_y']:+.1f}, y<0 {left['world_y_neg']}/{left['n']})")
    print(f"        world mean unit dir ({wd[0]:+.3f},{wd[1]:+.3f},{wd[2]:+.3f}) : "
          f"+x {wd[0]:+.3f} | belt -y {belt:+.3f} | -z {-wd[2]:+.3f}")
    rot = p2["_fmap"]["rots"]["left"]
    shares = {
        "tool axis": left["mean_leg_dir"][2],
        "jaw opening axis": left["mean_leg_dir"][1],
        "hand x (down)": left["mean_leg_dir"][0],
    }
    print("        leg-frame mechanism shares: " + ", ".join(
        f"{k} {v:+.3f}" for k, v in shares.items()))
    if right.get("n"):
        print(f"  right: n={right['n']}  world dominant {right['wdom']}  "
              f"mean world-y {right['mean_world_y']:+.1f} mm "
              f"(y<0 {right['world_y_neg']}/{right['n']})")
    else:
        print(f"  right: {right.get('n_trans', 0)} transient leg(s) only -> the arm "
              "contrast is unmeasurable on this cell (PREREG §4 P2)")
    top = "belt -y" if abs(belt) >= max(abs(wd[0]), abs(wd[2])) else (
        "world +x" if abs(wd[0]) >= abs(wd[2]) else "world -z")
    print(f"  -> the largest single world component is **{top}** "
          f"({max(abs(belt), abs(wd[0]), abs(wd[2])):+.3f}); the per-leg dominant "
          f"axis is **{dom}** ({left['wdom']})")
    if p3.get("left", {}).get("vmax") and p3.get("right", {}).get("vmax"):
        lm = statistics.median(p3["left"]["vmax"])
        rm = statistics.median(p3["right"]["vmax"])
        la = statistics.median(p3["left"]["amax"])
        ra = statistics.median(p3["right"]["amax"])
        print(f"  motion: median grasp_lift |v|max L/R {lm / rm:.3f}x, "
              f"|a|max L/R {la / ra:.3f}x")
    return (f"world {top} {max(abs(belt), abs(wd[0]), abs(wd[2])):+.3f}; "
            f"dominant {dom}; belt -y {belt:+.3f}; world-y "
            f"{left['mean_world_y']:+.1f} mm")


# --------------------------------------------------------------------------- #
# the P60 parser, imported as-is: that IS the P5 "still parses" check
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    p60 = load_p60()
    fmap = frame_map()
    cell = {p: parse_cell(p, p60) for p in CELL}
    ctrl = {p: parse_control(p, p60) for p in CTRL}

    print("P61 phase 2 - the direction of the direct line's carry slip")
    print("=" * 78)
    print(f"cell     : {', '.join(Path(p).name for p in CELL)}")
    print(f"comparator: {', '.join(Path(p).name for p in CTRL)} (P60 phase 3)")

    p1 = section_p1(cell)
    p2 = section_p2(cell, fmap)
    p2["_fmap"] = fmap
    p3 = section_p3(cell)
    p4 = section_p4(cell, ctrl, p60)
    p5 = section_p5(cell, p60, p1)
    v = verdict(p1, p2, p3)
    print(f"\n  VERDICT: {v}")

    if args.check:
        print("\n== --check ==")
        fails = []

        def ck(cond, what):
            print(("  ok  " if cond else "  FAIL") + f"  {what}")
            if not cond:
                fails.append(what)

        for path, eps in cell.items():
            ck(len(eps) == 15, f"{Path(path).name}: 15 episodes ({len(eps)})")
            ck(all(e["legs"] for e in eps if p60.outcome(e) == "cnp"),
               f"{Path(path).name}: every cnp attempt ran a carry leg")
        ck(p1["missing"] == 0, "every [carry] row carries slip_xyz")
        ck(p1["over_bound"] == 0,
           f"no row beyond the 0.15 mm print bound (worst {p1['worst']:.3f} mm)")
        ck(p5["bad"] == 0, "the P60 parser reads every new row")
        ck(p5["b_ok"], "B_metric reads trace rows, untouched")
        ck(sum(p2.get(a, {}).get("n", 0) for a in ("left", "right")) > 0,
           "at least one escaping attempt")
        for arm in ("left", "right"):
            s = p2.get(arm, {})
            if s.get("n"):
                ck(abs(sum(s["doms"].values()) - s["n"]) == 0,
                   f"{arm}: every escaping attempt classifies to one axis")
        before = (ROOT / "logs/p61/p2/tree_md5_before.txt")
        after = (ROOT / "logs/p61/p2/tree_md5_after.txt")
        if before.exists() and after.exists():
            ck(before.read_text().strip() == after.read_text().strip(),
               "tree md5s identical before/after the batch")
        print(f"\n  {'PASS' if not fails else 'FAIL'}: {len(fails)} failing check(s)")
        return 0 if not fails else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
