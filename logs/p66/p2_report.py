#!/usr/bin/env python3
"""P66 phase 2 report: the lift-end-height ladder - does the rotation move, and does the class follow?

Reads the registered cell (`logs/p66/p2/{C1,L1,L2,C2}_{77,101,202}.log`,
`FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1`, `logs/p66/PREREG_P2.md`) and the
instrument's own rows. Definitions are fixed in the prereg (written before the
run, amended only where marked in `logs/p66/P2_RESULTS.md`):

* `drift_end` = the **last** guarded tick's commanded-vs-achieved wrist angle on
  a `grasp_lift` leg (`hold_drift` is the leg's max, reported beside it);
* `res_end` / `dz_end` = the achieved TCP position error at the leg's end
  against the target that tick issued (norm, and its world-z component);
* the **achieved belt projection** = `|tool_y|` of the `[attitude]` row's
  `tool_axis` (the TCP frame's column 2, `motion.py`'s "direction the fingers
  extend"), and its **share** of `sin(tilt)` (the azimuth invariant);
* an **escape** = `clean_slip_max > 50 mm` (P61's convention); the attempt's
  outcome is P60's (`outcome()`), imported as-is.

    python3 logs/p66/p2_report.py            # print
    python3 logs/p66/p2_report.py --check    # + structural assertions
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P60_REPORT = "logs/p60/p3/report.py"
ARMS = ("C1", "L1", "L2", "C2")
SEEDS = (77, 101, 202)
CELL = [f"logs/p66/p2/{a}_{s}.log" for a in ARMS for s in SEEDS]
ESCAPE_MM = 50.0

#: the registered ladder (`logs/p66/PREREG_P2.md`, cell table): dz is the height
#: above `jaw_target`'s `belt_top + 0.28` base, replacing the hand's 0.08 add.
RUNG_DZ = {"C1": None, "L1": 0.00, "L2": -0.08, "C2": None}
RUNG_H = {"C1": 0.36, "L1": 0.28, "L2": 0.20, "C2": 0.36}
#: the predrcted `drift_end` (deg) and the band F1 is judged on
PRED = {"C1": (24.6, 3.0), "L1": (8.0, 3.0), "L2": (3.0, 2.0), "C2": (24.6, 3.0)}
#: the registered projection band (the shipped lift's achieved value, P62)
PROJ_BAND = (0.32, 0.37, 0.03)

_RE_DRIFT_END = re.compile(r"drift_end=(n/a|[\d.]+)")
_RE_DRIFT_MAX = re.compile(r"hold_drift=([\d.]+)deg")
_RE_RES_END = re.compile(r"res_end=(n/a|[\d.]+)mm")
_RE_DZ_END = re.compile(r"dz_end=([+-]?[\d.]+|n/a)mm")
_RE_QM = re.compile(r"q_margin=(n/a|-?[\d.]+@j\d/t\d+)")
_RE_QCM = re.compile(r"q_cmd_margin=(n/a|-?[\d.]+@j\d)")
_RE_ATT = re.compile(
    r"\[attitude\] (\w+) (\w+): tilt=([\d.]+)deg from world -Z, "
    r"tool_axis=\(([-+][\d.]+),([-+][\d.]+),([-+][\d.]+)\)"
)
_RE_LIFT_DZ_ROW = re.compile(r"\[grasp\] lift_dz: dz=([+-][\d.]+) m.*armed target=([\d.]+) m")
_RE_DURATION = re.compile(r"\[rl\] run wall end \d+\.\d+ duration ([\d.]+)s")


def load_p60():
    spec = importlib.util.spec_from_file_location("p60_report", ROOT / P60_REPORT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def fmt(v, nd=2) -> str:
    return "n/a" if v is None else f"{v:.{nd}f}"


def spread(vals, nd=2) -> str:
    vals = [v for v in vals if v is not None]
    if not vals:
        return "n/a"
    if len(vals) == 1:
        return f"{vals[0]:.{nd}f}"
    return f"{statistics.median(vals):.{nd}f} [{min(vals):.{nd}f}-{max(vals):.{nd}f}]"


def load_log(path: str, p60) -> dict:
    """Episodes (P60's parser) + this cell's extra fields + `[attitude]` rows."""
    path_obj = ROOT / path
    eps = p60.parse_direct(str(path_obj))
    for ep in eps:
        ep["oc"] = p60.outcome(ep)
        ep["log"] = Path(path).name
        ep["arm_log"] = Path(path).name.split("_")[0]
        for leg in ep["legs"]:
            line = leg["line"]
            m = _RE_DRIFT_END.search(line)
            leg["drift_end"] = None if (not m or m.group(1) == "n/a") else float(m.group(1))
            m = _RE_DRIFT_MAX.search(line)
            leg["drift_max"] = None if not m else float(m.group(1))
            m = _RE_RES_END.search(line)
            leg["res_end"] = None if (not m or m.group(1) == "n/a") else float(m.group(1))
            m = _RE_DZ_END.search(line)
            leg["dz_end"] = None if (not m or m.group(1) == "n/a") else float(m.group(1))
            m = _RE_QM.search(line)
            leg["q_margin"] = None if (not m or m.group(1) == "n/a") else float(
                m.group(1).split("@")[0]
            )
            m = _RE_QCM.search(line)
            leg["q_cmd_margin"] = None if (not m or m.group(1) == "n/a") else float(
                m.group(1).split("@")[0]
            )
    rows = []
    cur = None
    for line in path_obj.read_text(errors="replace").splitlines():
        m = re.search(r"\[rl\] episode (\d+): \w+ grade=", line)
        if m:
            cur = int(m.group(1))
            continue
        m = _RE_ATT.search(line)
        if m and cur is not None:
            rows.append(
                dict(
                    idx=cur,
                    side=m.group(1),
                    name=m.group(2),
                    tilt=float(m.group(3)),
                    tool=(float(m.group(4)), float(m.group(5)), float(m.group(6))),
                )
            )
    dz_row = None
    for line in path_obj.read_text(errors="replace").splitlines():
        m = _RE_LIFT_DZ_ROW.search(line)
        if m:
            dz_row = dict(dz=float(m.group(1)), target=float(m.group(2)))
            break
    dur = None
    for line in path_obj.read_text(errors="replace").splitlines():
        m = _RE_DURATION.search(line)
        if m:
            dur = float(m.group(1))
    return dict(eps=eps, attitude=rows, dz_row=dz_row, duration=dur)


def cell_data(p60) -> dict:
    out = {}
    for arm in ARMS:
        eps, att, runs = [], [], []
        for seed in SEEDS:
            d = load_log(f"logs/p66/p2/{arm}_{seed}.log", p60)
            for ep in d["eps"]:
                ep["seed"] = seed
            eps += d["eps"]
            att += d["attitude"]
            runs.append(d)
        out[arm] = dict(eps=eps, attitude=att, runs=runs)
    return out


def lift_legs(eps, side="left"):
    return [
        dict(leg, ep=ep)
        for ep in eps
        if ep["arm"] == side
        for leg in ep["legs"]
        if leg["name"] == "grasp_lift"
    ]


def counts(eps) -> dict:
    out = {}
    for side in ("left", "right"):
        sub = [e for e in eps if e["arm"] == side]
        out[side] = dict(
            n=len(sub),
            placed=sum(1 for e in sub if e["oc"] == "placed"),
            cnp=sum(1 for e in sub if e["oc"] == "cnp"),
            never=sum(1 for e in sub if e["oc"] == "never-held"),
        )
    out["placed_total"] = sum(1 for e in eps if e["oc"] == "placed")
    out["n_total"] = len(eps)
    return out


def note_keys(eps) -> dict:
    keys: dict[str, int] = {}
    for ep in eps:
        for note in re.findall(r"'([^']*)'", ep.get("notes") or ""):
            key = re.sub(r"\d+(?:\.\d+)?", "#", note.strip())
            if key:
                keys[key] = keys.get(key, 0) + 1
    return keys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    missing = [p for p in CELL if not (ROOT / p).is_file()]
    if missing:
        print(f"missing logs: {missing}")
        return 2
    p60 = load_p60()
    data = cell_data(p60)

    print("# P66 phase 2 - the lift-end-height ladder (logs/p66/PREREG_P2.md)")
    print(f"# cell: {', '.join(Path(p).name for p in CELL)}")
    print("# prediction (drift_end): C 24.6 +- 3 / L1 8 +- 3 / L2 3 +- 2 deg")
    print()

    # ---------------------------------------------------------------- P1
    print("== P1 - the instrument and the arm identity ==")
    for arm in ARMS:
        d = data[arm]
        rows = [l for e in d["eps"] for l in e["legs"]]
        lifts = lift_legs(d["eps"])
        place = [l for e in d["eps"] for l in e["legs"] if l["name"].startswith("place")]
        att = [r for r in d["attitude"] if r["name"] == "grasp_lift" and r["side"] == "left"]
        dz_rows = [r["dz_row"] for r in d["runs"] if r["dz_row"]]
        print(
            f"  {arm}: episodes={len(d['eps'])} [carry]={len(rows)} "
            f"left_lift_legs={len(lifts)} "
            f"drift_end live={sum(1 for l in lifts if l['drift_end'] is not None)}/{len(lifts)} "
            f"place(n/a)={sum(1 for l in place if l['drift_end'] is None)}/{len(place)} "
            f"[attitude] left_lift={len(att)} "
            f"lift_dz rows={len(dz_rows)}/{len(d['runs'])}"
        )
    for arm in ARMS:
        dz = [r["dz_row"] for r in data[arm]["runs"] if r["dz_row"]]
        if RUNG_DZ[arm] is None:
            print(f"  {arm} rung: unset (the shipped {RUNG_H[arm]:.2f} m) -> "
                  f"lift_dz rows={len(dz)} (want 0)")
        else:
            vals = sorted({round(x["dz"], 4) for x in dz})
            tgt = sorted({round(x["target"], 4) for x in dz})
            print(f"  {arm} rung: FRUIT_LIFT_DZ={RUNG_DZ[arm]:+.2f} -> rows={len(dz)}/{len(data[arm]['runs'])} "
                  f"dz={vals} armed_target_m={tgt} (want {RUNG_H[arm]:.2f} m above the floor's belt_top)")
    actu = [
        l
        for arm in ARMS
        for e in data[arm]["eps"]
        for l in e["legs"]
        if (l.get("guard") or 0) or (l.get("events") or 0) or (l.get("holds") or 0)
        or (l.get("reseat") or 0.0) or (l.get("relief") or 0)
    ]
    print(f"  diag actuation: {sum(len(e['legs']) for a in ARMS for e in data[a]['eps'])} rows, "
          f"guard/events/holds/reseat/relief != 0 on {len(actu)} (want 0)")
    print()

    # ---------------------------------------------------------------- P2
    print("== P2 - the mediator: drift_end per arm (left grasp_lift legs) ==")
    drift = {}
    for arm in ARMS:
        lifts = lift_legs(data[arm]["eps"])
        vals = [l["drift_end"] for l in lifts if l["drift_end"] is not None]
        mx = [l["drift_max"] for l in lifts if l["drift_max"] is not None]
        drift[arm] = dict(n=len(vals), vals=vals, med=statistics.median(vals) if vals else None)
        pred, band = PRED[arm]
        med = drift[arm]["med"]
        inside = med is not None and abs(med - pred) <= band
        print(f"  {arm} (lift end {RUNG_H[arm]:.2f} m, n={len(vals)}): "
              f"drift_end={spread(vals, 1)}  vs predicted {pred:.1f} +- {band:.1f} -> "
              f"{'INSIDE' if inside else 'OUTSIDE'} (median |delta| {fmt(None if med is None else abs(med - pred), 1)})")
        print(f"       hold_drift (the leg's max, for reference)={spread(mx, 1)}")
        for oc in ("placed", "cnp"):
            sub = [l["drift_end"] for l in lifts if l["ep"]["oc"] == oc and l["drift_end"] is not None]
            if sub:
                print(f"       {oc:6s} n={len(sub):2d} drift_end={spread(sub, 1)}")
    print("  ladder monotonicity (medians): " + " -> ".join(
        f"{arm} {fmt(drift[arm]['med'], 1)}" for arm in ("C1", "L1", "L2", "C2")))
    print()

    print("== P2b - the end position error (res_end / dz_end) and the margins ==")
    for arm in ARMS:
        lifts = lift_legs(data[arm]["eps"])
        print(f"  {arm}: res_end={spread([l['res_end'] for l in lifts], 1)} mm  "
              f"dz_end={spread([l['dz_end'] for l in lifts], 1)} mm  "
              f"q_margin={spread([l['q_margin'] for l in lifts], 3)}  "
              f"q_cmd_margin={spread([l['q_cmd_margin'] for l in lifts], 3)}")
    print()

    # ---------------------------------------------------------------- P3
    print("== P3 - the manipulation check: the achieved belt projection ==")
    print("  |tool_y| of the [attitude] tool_axis; share = |tool_y| / sin(tilt)")
    proj = {}
    for arm in ARMS:
        rows = [r for r in data[arm]["attitude"] if r["name"] == "grasp_lift" and r["side"] == "left"]
        belt = [abs(r["tool"][1]) for r in rows]
        tilt = [r["tilt"] for r in rows]
        share = [
            abs(r["tool"][1]) / math.sin(math.radians(r["tilt"]))
            for r in rows
            if r["tilt"] > 1e-6
        ]
        proj[arm] = dict(belt=belt, tilt=tilt, share=share)
        lo, hi, tol = PROJ_BAND
        inside = bool(belt) and all(lo - tol <= b <= hi + tol for b in belt)
        print(f"  {arm}: proj={spread(belt, 3)} deg=|{spread(tilt, 1)}| "
              f"share={spread(share, 2)}  vs registered band [{lo:.2f},{hi:.2f}] +- {tol:.2f} -> "
              f"{'INSIDE' if inside else 'OUTSIDE'}")
    print("  (the band is the shipped lift's own value; projection = sin(tilt) * share, so the")
    print("   registered 'unchanged' clause and the registered drift prediction cannot both hold -")
    print("   see P2_RESULTS section 3: the surviving invariant is the SHARE.)")
    print()

    # ---------------------------------------------------------------- P4
    print("== P4 - the class (the primary endpoint) ==")
    for arm in ARMS:
        c = counts(data[arm]["eps"])
        print(f"  {arm}: left n={c['left']['n']:2d} placed={c['left']['placed']:2d} "
              f"cnp={c['left']['cnp']:2d} never-held={c['left']['never']:2d} | "
              f"right n={c['right']['n']:2d} placed={c['right']['placed']:2d} "
              f"cnp={c['right']['cnp']:2d} never-held={c['right']['never']:2d} | "
              f"pooled placed {c['placed_total']}/{c['n_total']}")
    print()
    for arm in ARMS:
        c = counts(data[arm]["eps"])
        per_seed = {}
        for e in data[arm]["eps"]:
            per_seed.setdefault(e["seed"], [0, 0])
            per_seed[e["seed"]][1] += 1
            per_seed[e["seed"]][0] += 1 if e["oc"] == "placed" else 0
        print(f"  {arm} per seed: " + ", ".join(
            f"{s}: {v[0]}/{v[1]}" for s, v in sorted(per_seed.items())))
    print()
    print("  the left's escaping legs (clean_slip_max > 50 mm) - onset_row / slip / class:")
    for arm in ARMS:
        lifts = lift_legs(data[arm]["eps"])
        esc = [l for l in lifts if (l.get("clean_slip") or 0.0) > ESCAPE_MM]
        onset = [l["onset_row"] for l in esc if l.get("onset_row") is not None]
        slip = [l["clean_slip"] for l in esc]
        print(f"    {arm}: escapes={len(esc)}/{len(lifts)}  onset_row={spread(onset, 1)}  "
              f"clean_slip_max={spread(slip, 1)} mm")
    print()
    print("  s/attempt (log wall / 15, and the episode's own sim ticks):")
    for arm in ARMS:
        d = data[arm]
        walls = [r["duration"] for r in d["runs"] if r["duration"]]
        ticks = [e["ticks"] for e in d["eps"] if e.get("ticks")]
        print(f"    {arm}: wall={spread([w / 15.0 for w in walls], 1)} s/pick "
              f"(log durations {[round(w, 1) for w in walls]})  "
              f"ticks/pick={spread([t / 120.0 for t in ticks], 1)} s sim")
    print()

    print("== P4b - the right arm (the unarmed one; the registered secondary) ==")
    for arm in ARMS:
        lifts = lift_legs(data[arm]["eps"], "right")
        rows = [r for r in data[arm]["attitude"] if r["name"] == "grasp_lift" and r["side"] == "right"]
        c = counts(data[arm]["eps"])["right"]
        print(f"  {arm}: right lift_legs={len(lifts)} drift_end={spread([l['drift_end'] for l in lifts], 1)} "
              f"(hold_drift max {spread([l['drift_max'] for l in lifts], 1)}) "
              f"proj={spread([abs(r['tool'][1]) for r in rows], 3)} | "
              f"placed={c['placed']}/{c['n']} cnp={c['cnp']} never-held={c['never']}")
    print()

    # ---------------------------------------------------------------- P5
    print("== P5 - falsifiers ==")
    # F1
    f1 = []
    for arm in ARMS:
        pred, band = PRED[arm]
        med = drift[arm]["med"]
        f1.append((arm, med is not None and abs(med - pred) <= band))
    print(f"  F1 (drift_end inside every band): "
          f"{'PASS - no arm misses' if all(v for _, v in f1) else 'FIRED - ' + str([a for a, v in f1 if not v])}")
    # F2
    print("  F2 (slip/onset move but the cnp count does not): see P4 - report only, no automatic verdict")
    # F3
    base = note_keys(data["C1"]["eps"]) | {}  # the control arm's keys
    for arm in ARMS:
        new = sorted(set(note_keys(data[arm]["eps"])) - set(base))
        print(f"  F3 ({arm} vs the C1 control's note keys): new={new if new else 'none'}")
    # F4
    lost = []
    for arm in ARMS:
        for e in data[arm]["eps"]:
            if "fruit fell off the line" in (e.get("notes") or ""):
                lost.append((arm, e["seed"], e["idx"]))
    print(f"  F4 (the place leg loses payloads): "
          f"{'PASS - none' if not lost else f'FIRED - {lost}'}")
    print()

    if args.check:
        return run_checks(p60, data)
    return 0


def run_checks(p60, data) -> int:
    bad = 0

    def ok(cond, msg):
        nonlocal bad
        print(f"  {'PASS' if cond else 'FAIL'}: {msg}")
        if not cond:
            bad += 1

    print("== checks ==")
    for arm in ARMS:
        d = data[arm]
        ok(len(d["eps"]) == 45, f"{arm}: 45 episodes ({len(d['eps'])})")
        lifts = lift_legs(d["eps"])
        ok(lifts and all(l["drift_end"] is not None for l in lifts),
           f"{arm}: every left grasp_lift row carries drift_end ({sum(1 for l in lifts if l['drift_end'] is not None)}/{len(lifts)})")
        ok(all(l["res_end"] is not None and l["dz_end"] is not None for l in lifts),
           f"{arm}: every left grasp_lift row carries res_end/dz_end")
        place = [l for e in d["eps"] for l in e["legs"] if l["name"].startswith("place")]
        ok(all(l["drift_end"] is None for l in place),
           f"{arm}: every place row prints drift_end=n/a ({len(place)} rows)")
        ok(all(l["drift_end"] is not None and 0.0 <= l["drift_end"] <= 180.0 for l in lifts),
           f"{arm}: every drift_end is a finite angle in [0, 180] deg")
        rows = sum(len(e["legs"]) for e in d["eps"])
        parsed = 0
        for seed in SEEDS:
            for line in (ROOT / f"logs/p66/p2/{arm}_{seed}.log").read_text(errors="replace").splitlines():
                m = re.search(r"\[carry\] (\w+) (\w+): (.*)$", line)
                if m:
                    leg = p60.parse_leg(m.group(3))
                    if leg.get("clean_slip") is not None and leg.get("ticks") is not None:
                        parsed += 1
        ok(parsed == rows, f"{arm}: logs/p60/p3/report.py parse_leg reads all {rows} rows")
        actu = [l for e in d["eps"] for l in e["legs"]
                if (l.get("guard") or 0) or (l.get("events") or 0) or (l.get("holds") or 0)
                or (l.get("reseat") or 0.0) or (l.get("relief") or 0)]
        ok(not actu, f"{arm}: the diag did not actuate (guard/events/holds/reseat/relief all 0)")
        dzs = [r["dz_row"] for r in d["runs"] if r["dz_row"]]
        if RUNG_DZ[arm] is None:
            ok(not dzs, f"{arm}: the control prints no [grasp] lift_dz row")
        else:
            ok(len(dzs) == len(SEEDS) and all(abs(x["dz"] - RUNG_DZ[arm]) < 1e-9 for x in dzs),
               f"{arm}: every run prints its own rung (dz={RUNG_DZ[arm]:+.2f})")
            ok(all(abs(x["target"] - (1.17 + RUNG_H[arm])) < 0.02 for x in dzs),
               f"{arm}: the printed armed target is the rung's height ({1.17 + RUNG_H[arm]:.2f} m)")
    for arm in ARMS:
        rows = [r for r in data[arm]["attitude"] if r["name"] == "grasp_lift" and r["side"] == "left"]
        ok(len(rows) >= 3, f"{arm}: the [attitude] rows exist for the projection check ({len(rows)})")
    before = ROOT / "logs/p66/p2/tree_md5_before.txt"
    after = ROOT / "logs/p66/p2/tree_md5_after.txt"
    ok(before.is_file() and after.is_file() and before.read_text() == after.read_text(),
       "tree md5s identical before/after the batch")
    print(f"  {'PASS' if bad == 0 else 'FAIL'}: {bad} failure(s)")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
