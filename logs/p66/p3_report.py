#!/usr/bin/env python3
"""P66 phase 3 report: the clearance cost of the lift-height ladder - does 0.24
match 0.20 at half the depth, and does the place leg keep the +33 mm floor?

Reads the registered cell (`logs/p66/p3/{control,C24,C20}_{77,101,202,303,404}.log`,
`FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1`, `logs/p66/DEVIATION.md`), the
instrument's own rows and the P60 parser (the attempt/leg definitions are its).

Definitions (fixed in `logs/p66/DEVIATION.md`, amended only where marked):

* `drift_end` = the **last** guarded tick's commanded-vs-achieved wrist angle on a
  `grasp_lift` leg; `|tool_y|` = the achieved belt projection of the `[attitude]`
  row's tool axis (the phase-2 dose, `DEVIATION.md` D3 - the *share* is
  withdrawn);
* `clr` = the leg's **minimum** payload clearance to the highest surface under
  it, with its surface code (P2-3's `_payload_clearance`; `@rail` is the surface
  of the +33 mm access floor, `logs/p30a/RAILS_DESIGN.md`);
* an **escape** = `clean_slip_max > 50 mm` (P61's convention); the attempt's
  outcome is P60's `outcome()`;
* the **standardised** placed rate = direct standardisation over the left's
  **species** mix, weights = the pooled left counts of the species present in
  every arm (the arm is the lane, `rl_env.py`'s grade -> bin -> arm rule, so the
  left arm is a single arm).

    python3 logs/p66/p3_report.py            # print
    python3 logs/p66/p3_report.py --check    # + structural assertions
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P60_REPORT = "logs/p60/p3/report.py"
ARMS = ("control", "C24", "C20")
SEEDS = (77, 101, 202, 303, 404)
CELL = [f"logs/p66/p3/{a}_{s}.log" for a in ARMS for s in SEEDS]
ESCAPE_MM = 50.0
#: the access floor of record: the placed payload must stay this far above the
#: inner rail's top (`logs/p30a/RAILS_DESIGN.md`; measured +31..+54 at the shipped
#: transfer z).
RAIL_FLOOR_MM = 33.0

#: the registered arms (`logs/p66/DEVIATION.md` D4: the brief's `-0.12/-0.16` are
#: `target - 0.36`; the code's base is the 0.28, so the heights are these values)
RUNG_DZ = {"control": 0.08, "C24": -0.04, "C20": -0.08}
RUNG_H = {"control": 0.36, "C24": 0.24, "C20": 0.20}
#: phase 2's measured `drift_end` medians at these heights (for the dose read)
P2_DRIFT = {0.36: 24.6, 0.28: 8.0, 0.20: 0.7}

_RE_DRIFT_END = re.compile(r"drift_end=(n/a|[\d.]+)")
_RE_DRIFT_MAX = re.compile(r"hold_drift=([\d.]+)deg")
_RE_RES_END = re.compile(r"res_end=(n/a|[\d.]+)mm")
_RE_CLR = re.compile(r"clr=(n/a|[+-]?[\d.]+)mm@(\w+)")
_RE_ATT = re.compile(
    r"\[attitude\] (\w+) (\w+): tilt=([\d.]+)deg from world -Z, "
    r"tool_axis=\(([-+][\d.]+),([-+][\d.]+),([-+][\d.]+)\)"
)
_RE_LIFT_DZ_ROW = re.compile(
    r"\[grasp\] lift_dz: dz=([+-][\d.]+)\((default|explicit)\) m above the 0\.28 base "
    r"-> ([\d.]+) m above floor"
)
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
    text = path_obj.read_text(errors="replace")
    eps = p60.parse_direct(str(path_obj))
    for ep in eps:
        ep["oc"] = p60.outcome(ep)
        ep["log"] = Path(path).name
        for leg in ep["legs"]:
            line = leg["line"]
            m = _RE_DRIFT_END.search(line)
            leg["drift_end"] = None if (not m or m.group(1) == "n/a") else float(m.group(1))
            m = _RE_DRIFT_MAX.search(line)
            leg["drift_max"] = None if not m else float(m.group(1))
            m = _RE_RES_END.search(line)
            leg["res_end"] = None if (not m or m.group(1) == "n/a") else float(m.group(1))
            m = _RE_CLR.search(line)
            leg["clr"] = None if (not m or m.group(1) == "n/a") else float(m.group(1))
            leg["clr_surface"] = None if not m or m.group(1) == "n/a" else m.group(2)
    rows = []
    cur = None
    for line in text.splitlines():
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
    for line in text.splitlines():
        m = _RE_LIFT_DZ_ROW.search(line)
        if m:
            dz_row = dict(
                dz=float(m.group(1)), origin=m.group(2), target=float(m.group(3))
            )
            break
    dur = None
    for line in text.splitlines():
        m = _RE_DURATION.search(line)
        if m:
            dur = float(m.group(1))
    return dict(eps=eps, attitude=rows, dz_row=dz_row, duration=dur, text=text)


def cell_data(p60) -> dict:
    out = {}
    for arm in ARMS:
        eps, att, runs = [], [], []
        for seed in SEEDS:
            d = load_log(f"logs/p66/p3/{arm}_{seed}.log", p60)
            for ep in d["eps"]:
                ep["seed"] = seed
            eps += d["eps"]
            att += d["attitude"]
            runs.append(d)
        out[arm] = dict(eps=eps, attitude=att, runs=runs)
    return out


def side_legs(eps, side, name=None):
    return [
        dict(leg, ep=ep)
        for ep in eps
        if ep["arm"] == side
        for leg in ep["legs"]
        if (name is None or leg["name"].startswith(name))
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
    return out


def per_species(eps, side="left") -> dict:
    out: dict[str, list[int]] = {}
    for ep in eps:
        if ep["arm"] != side:
            continue
        slot = out.setdefault(ep["fruit"], [0, 0])
        slot[1] += 1
        slot[0] += 1 if ep["oc"] == "placed" else 0
    return out


def standardised(tables: dict[str, dict[str, list[int]]]) -> tuple[dict, dict]:
    """Direct standardisation of the left's placed rate over **species**.

    Weights: the pooled left counts of the species that appear in **every** arm
    (the common support), renormalised. Returns `(rates, support)`; each rate
    also carries its restricted numerator/denominator so the reader can see what
    the weights did.
    """
    common = None
    for arm in ARMS:
        names = {k for k, v in tables[arm].items() if v[1] > 0}
        common = names if common is None else (common & names)
    support = sorted(common or [])
    pooled = {k: sum(tables[a].get(k, [0, 0])[1] for a in ARMS) for k in support}
    total = sum(pooled.values())
    out = {}
    for arm in ARMS:
        num = den = 0.0
        placed = n = 0
        for k in support:
            p, k_n = tables[arm].get(k, [0, 0])
            w = pooled[k] / total if total else 0.0
            num += w * (p / k_n if k_n else 0.0)
            den += w
            placed += p
            n += k_n
        out[arm] = dict(
            rate=(num / den if den else None),
            placed=placed,
            n=n,
            weight=den,
        )
    return out, dict(species=support, pooled=pooled, total=total)


def note_keys(eps) -> dict:
    keys: dict[str, int] = {}
    for ep in eps:
        for note in re.findall(r"'([^']*)'", ep.get("notes") or ""):
            key = re.sub(r"\d+(?:\.\d+)?", "#", note.strip())
            if key:
                keys[key] = keys.get(key, 0) + 1
    return keys


def fisher_one_sided(a: int, b: int, c: int, d: int) -> float:
    """P(X >= a) for the 2x2 table [[a, b], [c, d]] (rows = arm, cols = class)."""
    from math import comb

    n = a + b + c + d
    r1 = a + b
    c1 = a + c
    hi = min(r1, c1)
    num = sum(comb(r1, k) * comb(n - r1, c1 - k) for k in range(a, hi + 1))
    return num / comb(n, c1) if n and c1 <= n else float("nan")


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

    print("# P66 phase 3 - the clearance cost of the lift-height ladder")
    print(f"# cell: {', '.join(Path(p).name for p in CELL)}")
    print("# arms: control=+0.08 (0.36 m) / C24=-0.04 (0.24 m) / C20=-0.08 (0.20 m), all explicit")
    print("# the question: does 0.24 match 0.20 at half the depth, and is the place clr >= +33 mm?")
    print()

    # ---------------------------------------------------------------- P1
    print("== P1 - the instrument, the rung identity and the arm scope ==")
    for arm in ARMS:
        d = data[arm]
        rows = [l for e in d["eps"] for l in e["legs"]]
        lifts = side_legs(d["eps"], "left", "grasp_lift")
        place = side_legs(d["eps"], "left", "place")
        dz_rows = [r["dz_row"] for r in d["runs"] if r["dz_row"]]
        origins = sorted({r["origin"] for r in dz_rows})
        targets = sorted({round(r["target"], 4) for r in dz_rows})
        print(
            f"  {arm}: episodes={len(d['eps'])} [carry]={len(rows)} "
            f"left_lift_legs={len(lifts)} left_place_legs={len(place)} "
            f"clr on {sum(1 for l in rows if l['clr'] is not None)}/{len(rows)} rows | "
            f"dz rows={len(dz_rows)}/{len(d['runs'])} dz={sorted({round(r['dz'], 4) for r in dz_rows})} "
            f"origin={origins} target_m={targets}"
        )
    print(f"  wanted: dz={RUNG_DZ}, target={1.17 + RUNG_H['control']:.2f}/{1.17 + RUNG_H['C24']:.2f}/"
          f"{1.17 + RUNG_H['C20']:.2f} m above the floor (belt_top 1.17), origin=explicit in all arms")
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
    print("== P2 - THE QUESTION: the place leg's minimum `clr` against the +33 mm rail floor ==")
    print("  three explicit populations per arm, fixed before the read (the exclusion is")
    print("  structural: `_payload_clearance` tracks the payload's position whether or not the")
    print("  hand holds it, so a payload that is already gone reads the *main belt*):")
    print("    clean  = clean_slip <= 50 mm  -> the payload crossed the rail in the pads: THE FLOOR'S READ")
    print("    slide  = 50 < slip <= 400 mm  -> the payload slid out during the leg: its min clr is")
    print("                                     the slide's, reported beside (not excused)")
    print("    escaped= slip > 400 mm        -> excluded: the fruit is on another belt (-215..-219 mm")
    print("                                     is the record's own escaped-payload class)")
    place_min = {}
    for arm in ARMS:
        legs = side_legs(data[arm]["eps"], "left", "place")
        rail = [l for l in legs if l["clr"] is not None and l["clr_surface"] == "rail"]
        clean = [l for l in rail if (l.get("clean_slip") or 0.0) <= 50.0]
        slide = [l for l in rail if 50.0 < (l.get("clean_slip") or 0.0) <= 400.0]
        escaped = [l for l in legs if (l.get("clean_slip") or 0.0) > 400.0]
        vals = [l["clr"] for l in clean]
        place_min[arm] = dict(
            legs=clean,
            n=len(vals),
            median=statistics.median(vals) if vals else None,
            mn=min(vals) if vals else None,
            below=sum(1 for v in vals if v < RAIL_FLOOR_MM),
            negative=sum(1 for v in vals if v < 0.0),
            slide=[l["clr"] for l in slide],
            escaped=len(escaped),
            place_rows=len(legs),
        )
        msg = place_min[arm]
        print(
            f"  {arm} (lift end {RUNG_H[arm]:.2f} m): clean n={msg['n']} "
            f"clr_min={spread(vals, 0)} mm | below +{RAIL_FLOOR_MM:.0f} mm: "
            f"{msg['below']}/{msg['n']} | negative: {msg['negative']}/{msg['n']} || "
            f"slide n={len(slide)} clr={[round(v) for v in msg['slide']]} mm || "
            f"escaped {msg['escaped']}/{msg['place_rows']}"
        )
        for l in sorted(clean, key=lambda x: x["clr"]):
            if l["clr"] >= RAIL_FLOOR_MM:
                continue
            print(f"      clean clr={l['clr']:+.0f} mm ep={l['ep']['idx']} seed={l['ep']['seed']} "
                  f"{l['ep']['fruit']} | in-hand_vmax={fmt(l.get('in_hand_vmax'), 3)} "
                  f"clean_slip={fmt(l.get('clean_slip'), 1)} mm "
                  f"force_min={fmt(l.get('force_min'))} N outcome={l['ep']['oc']}")
        for l in slide:
            print(f"      slide clr={l['clr']:+.0f} mm ep={l['ep']['idx']} seed={l['ep']['seed']} "
                  f"{l['ep']['fruit']} | clean_slip={fmt(l.get('clean_slip'), 1)} mm "
                  f"loss_row={l.get('loss_row')}/{l.get('ticks')} "
                  f"in-hand_vmax={fmt(l.get('in_hand_vmax'), 3)} outcome={l['ep']['oc']}")
    print("  per-seed clean minima (the branch check - a rung's cost is not a single leg):")
    for arm in ARMS:
        per = {}
        for seed in SEEDS:
            vals = [l["clr"] for l in place_min[arm]["legs"] if l["ep"]["seed"] == seed]
            per[seed] = (len(vals), min(vals) if vals else None)
        print(f"    {arm}: " + ", ".join(
            f"{s}: n={v[0]} min={fmt(v[1], 0)}" for s, v in per.items()))
    print("  for context, the left's own LIFT leg (the main belt; its min is the leg's FIRST tick,")
    print("  i.e. the payload being seated - identical work in every arm, not this lever's object):")
    for arm in ARMS:
        lifts = side_legs(data[arm]["eps"], "left", "grasp_lift")
        vals = [l["clr"] for l in lifts
                if l["clr"] is not None and l["clr_surface"] == "belt"
                and (l.get("clean_slip") or 0.0) <= 400.0]
        print(f"    {arm}: n={len(vals)} clr_min={spread(vals, 0)} mm@belt")
    print("  THE SHIPPED-HEIGHT REFERENCE: the right arm is unarmed by this knob (its lift ends at")
    print("  0.36 m), so its clean place legs are the same-batch measurement of the floor that the")
    print("  control's left cannot give - the control's left never carries a payload into place:")
    ref_legs = []
    for arm in ARMS:
        legs = side_legs(data[arm]["eps"], "right", "place")
        clean = [
            l for l in legs
            if l["clr"] is not None and l["clr_surface"] == "rail"
            and (l.get("clean_slip") or 0.0) <= 50.0
        ]
        vals = [l["clr"] for l in clean]
        ref_legs += clean
        print(f"    {arm}: n={len(vals)} clr_min={spread(vals, 0)} mm@rail "
              f"| below +{RAIL_FLOOR_MM:.0f}: {sum(1 for v in vals if v < RAIL_FLOOR_MM)}/{len(vals)}")
    ref_vals = [l["clr"] for l in ref_legs]
    print(f"    pooled: n={len(ref_vals)} clr_min={spread(ref_vals, 0)} mm@rail, "
          f"{sum(1 for v in ref_vals if v < RAIL_FLOOR_MM)}/{len(ref_vals)} below the floor")
    print()
    print("== P2b - did the rail bite? the clean place legs' own motion (the record's signature")
    print("   is a jolt + ~4 cm of slip on the legs that dip under the rail top)")
    for arm in ARMS:
        legs = place_min[arm]["legs"]
        print(f"  {arm}: in-hand_vmax={spread([l.get('in_hand_vmax') for l in legs], 3)} "
              f"clean_slip_max={spread([l.get('clean_slip') for l in legs], 1)} mm "
              f"force_min={spread([l.get('force_min') for l in legs], 2)} N "
              f"| place-leg res_end={spread([l.get('res_end') for l in legs], 1)} mm "
              f"dz_end={spread([l.get('dz_end') for l in legs], 1)} mm")
    print()

    # ---------------------------------------------------------------- P3
    print("== P3 - the mediator: drift_end and |tool_y| per rung (the left's lift legs) ==")
    drift = {}
    for arm in ARMS:
        lifts = side_legs(data[arm]["eps"], "left", "grasp_lift")
        vals = [l["drift_end"] for l in lifts if l["drift_end"] is not None]
        rows = [r for r in data[arm]["attitude"]
                if r["name"] == "grasp_lift" and r["side"] == "left"]
        proj = [abs(r["tool"][1]) for r in rows]
        drift[arm] = dict(n=len(vals), med=statistics.median(vals) if vals else None,
                          proj=statistics.median(proj) if proj else None)
        print(f"  {arm} (lift end {RUNG_H[arm]:.2f} m, n={len(vals)}): "
              f"drift_end={spread(vals, 1)} deg | |tool_y|={spread(proj, 3)} "
              f"| res_end={spread([l['res_end'] for l in lifts], 1)} mm")
    print("  dose reference (phase 2, same instrument): 0.36 -> 24.6, 0.28 -> 8.0, 0.20 -> 0.7 deg")
    print()

    # ---------------------------------------------------------------- P4
    print("== P4 - the class (the primary): the left's placed, raw and standardised ==")
    for arm in ARMS:
        c = counts(data[arm]["eps"])
        print(f"  {arm}: left n={c['left']['n']:2d} placed={c['left']['placed']:2d} "
              f"cnp={c['left']['cnp']:2d} never-held={c['left']['never']:2d} | "
              f"right n={c['right']['n']:2d} placed={c['right']['placed']:2d} "
              f"cnp={c['right']['cnp']:2d} never-held={c['right']['never']:2d}")
    tables = {arm: per_species(data[arm]["eps"], "left") for arm in ARMS}
    print("  the left's per-species placed / n (the arm is the lane, so one arm per grade):")
    for arm in ARMS:
        print(f"    {arm}: " + ", ".join(
            f"{k} {v[0]}/{v[1]}" for k, v in sorted(tables[arm].items())))
    std, sup = standardised(tables)
    print(f"  standardised (species; common support {sup['species']}, "
          f"pooled weights {sup['pooled']}, total {sup['total']}):")
    for arm in ARMS:
        s = std[arm]
        print(f"    {arm}: standardised placed={fmt(s['rate'], 3)} "
              f"(restricted {s['placed']}/{s['n']}, weight {s['weight']:.3f})")
    print("  per-seed left placed:")
    for arm in ARMS:
        per = {}
        for e in data[arm]["eps"]:
            if e["arm"] != "left":
                continue
            slot = per.setdefault(e["seed"], [0, 0])
            slot[1] += 1
            slot[0] += 1 if e["oc"] == "placed" else 0
        print(f"    {arm}: " + ", ".join(f"{s}: {v[0]}/{v[1]}" for s, v in sorted(per.items())))
    print()
    print("  the left's escaping lift legs (clean_slip_max > 50 mm) and the place class:")
    for arm in ARMS:
        lifts = side_legs(data[arm]["eps"], "left", "grasp_lift")
        esc = [l for l in lifts if (l.get("clean_slip") or 0.0) > ESCAPE_MM]
        cnps = [l for l in lifts if l["ep"]["oc"] == "cnp"]
        place_cls = [l for l in cnps if (l.get("clean_slip") or 0.0) <= ESCAPE_MM]
        print(f"    {arm}: lift escapes={len(esc)}/{len(lifts)}  cnps={len(cnps)} "
              f"lift-class={len(esc)} place-class={len(place_cls)}")
    print()
    print("== P4b - the right arm (unarmed: the invariance check) ==")
    for arm in ARMS:
        c = counts(data[arm]["eps"])["right"]
        print(f"  {arm}: right placed={c['placed']}/{c['n']} "
              f"({100.0 * c['placed'] / c['n'] if c['n'] else float('nan'):.1f} %) "
              f"cnp={c['cnp']} never-held={c['never']}")
    try:
        p_right = fisher_one_sided(
            counts(data["control"]["eps"])["right"]["placed"],
            counts(data["control"]["eps"])["right"]["n"] - counts(data["control"]["eps"])["right"]["placed"],
            counts(data["C20"]["eps"])["right"]["placed"],
            counts(data["C20"]["eps"])["right"]["n"] - counts(data["C20"]["eps"])["right"]["placed"],
        )
        print(f"  control vs C20, right arm placed: one-sided Fisher p={p_right:.3f} "
              "(row 1 = control >= row 2 = C20)")
    except Exception as exc:  # noqa: BLE001
        print(f"  (right-arm Fisher unavailable: {exc})")
    print()
    print("  no new failure reason (note keys vs the same-batch control):")
    base = note_keys(data["control"]["eps"])
    for arm in ARMS:
        new = sorted(set(note_keys(data[arm]["eps"])) - set(base))
        print(f"    {arm}: new={new if new else 'none'}")
    print()
    print("  the cycle: s/attempt (log wall / 15) and s sim / pick")
    for arm in ARMS:
        d = data[arm]
        walls = [r["duration"] for r in d["runs"] if r["duration"]]
        ticks = [e["ticks"] for e in d["eps"] if e.get("ticks")]
        print(f"    {arm}: wall={spread([w / 15.0 for w in walls], 1)} s/pick "
              f"(durations {[round(w, 1) for w in walls]}) | "
              f"sim={spread([t / 120.0 for t in ticks], 1)} s/pick")
    print()

    # ---------------------------------------------------------------- P5
    print("== P5 - the verdict ==")
    c24 = std["C24"]["rate"] if "C24" in std else None
    c20 = std["C20"]["rate"] if "C20" in std else None
    cc = std["control"]["rate"] if "control" in std else None
    print(f"  Q1 does 0.24 match 0.20 at half the depth?  standardised placed "
          f"control {fmt(cc, 3)} / C24 {fmt(c24, 3)} / C20 {fmt(c20, 3)}")
    if None not in (c24, c20):
        print(f"     C24 - C20 = {c24 - c20:+.3f}; C24 - control = {c24 - cc:+.3f}; "
              f"C20 - control = {c20 - cc:+.3f}")
    lift_floor = RAIL_FLOOR_MM
    ref_legs = [
        l for a in ARMS for l in side_legs(data[a]["eps"], "right", "place")
        if l["clr"] is not None and l["clr_surface"] == "rail"
        and (l.get("clean_slip") or 0.0) <= ESCAPE_MM
    ]
    ref_vals = [l["clr"] for l in ref_legs]
    print(f"  floor reference (the unarmed right arm, lift end 0.36 m): n={len(ref_vals)} "
          f"clr_min={spread(ref_vals, 0)} mm@rail, "
          f"{sum(1 for v in ref_vals if v < RAIL_FLOOR_MM)}/{len(ref_vals)} below +{RAIL_FLOOR_MM:.0f} mm")
    print(f"  Q2 is the place clr >= +{lift_floor:.0f} mm?  " + " | ".join(
        f"{a}: min {fmt(place_min[a]['mn'], 0)} mm, {place_min[a]['below']}/{place_min[a]['n']} below"
        for a in ARMS))
    for arm in ("C24", "C20"):
        if arm not in place_min:
            continue
        msg = place_min[arm]
        neg = msg["negative"] > 0 or any(v < 0 for v in msg["slide"])
        print(f"  STOP RULE at {RUNG_H[arm]:.2f} m (DEVIATION D4): clean min "
              f"{fmt(msg['mn'], 0)} mm, {msg['below']}/{msg['n']} below the floor, "
              f"slide minima {[round(v) for v in msg['slide']]} -> "
              f"{'FIRED (a negative crossing exists)' if neg else 'not fired'}")
    ref_vals2 = [l["clr"] for l in ref_legs]
    print(f"  COST: the floor's same-batch reference is {spread(ref_vals2, 0)} mm "
          f"(the unarmed right arm at 0.36 m, "
          f"{sum(1 for v in ref_vals2 if v < RAIL_FLOOR_MM)}/{len(ref_vals2)} below the floor); "
          f"the two rungs read "
          + " / ".join(f"{a} {fmt(place_min[a]['median'], 0)} mm"
                       for a in ("C24", "C20") if a in place_min) + ".")
    print(f"  drift_end medians: " + " / ".join(
        f"{a} {fmt(drift[a]['med'], 1)}" for a in ARMS)
        + f" deg (phase 2 at 0.36/0.20: 24.6/0.7)")
    print()

    if args.check:
        return run_checks(p60, data, place_min)
    return 0


def run_checks(p60, data, place_min) -> int:
    bad = 0

    def ok(cond, msg):
        nonlocal bad
        print(f"  {'PASS' if cond else 'FAIL'}: {msg}")
        if not cond:
            bad += 1

    print("== checks ==")
    for arm in ARMS:
        d = data[arm]
        ok(len(d["eps"]) == 75, f"{arm}: 75 episodes ({len(d['eps'])})")
        rows = [l for e in d["eps"] for l in e["legs"]]
        ok(all(l["clr"] is not None for l in rows),
           f"{arm}: every [carry] row carries a numeric clr "
           f"({sum(1 for l in rows if l['clr'] is not None)}/{len(rows)})")
        ok(all(l.get("clr_surface") in ("belt", "obelt", "rail")
               for l in rows if l["clr"] is not None),
           f"{arm}: every clr names its surface")
        place = side_legs(d["eps"], "left", "place")
        clean_place = [l for l in place if (l.get("clean_slip") or 0.0) <= 50.0]
        ok(all(l["clr_surface"] == "rail" for l in clean_place if l["clr"] is not None),
           f"{arm}: every clean left place-leg clr is measured against the rail "
           f"({sum(1 for l in clean_place if l['clr_surface'] == 'rail')}/{len(clean_place)})")
        lifts = side_legs(d["eps"], "left", "grasp_lift")
        ok(lifts and all(l["drift_end"] is not None for l in lifts),
           f"{arm}: every left grasp_lift row carries drift_end "
           f"({sum(1 for l in lifts if l['drift_end'] is not None)}/{len(lifts)})")
        dzs = [r["dz_row"] for r in d["runs"] if r["dz_row"]]
        ok(len(dzs) == len(SEEDS) and all(abs(x["dz"] - RUNG_DZ[arm]) < 1e-9 for x in dzs),
           f"{arm}: every run prints its own rung (dz={RUNG_DZ[arm]:+.2f})")
        ok(all(x["origin"] == "explicit" for x in dzs),
           f"{arm}: every run's origin is `explicit` (the batch cannot see the flip)")
        ok(all(abs(x["target"] - (1.17 + RUNG_H[arm])) < 0.02 for x in dzs),
           f"{arm}: the printed target is the rung's height ({1.17 + RUNG_H[arm]:.2f} m)")
        actu = [l for e in d["eps"] for l in e["legs"]
                if (l.get("guard") or 0) or (l.get("events") or 0) or (l.get("holds") or 0)
                or (l.get("reseat") or 0.0) or (l.get("relief") or 0)]
        ok(not actu, f"{arm}: the diag did not actuate (guard/events/holds/reseat/relief all 0)")
        # the P60 parser reads every row (the field additions are backwards compatible)
        parsed = 0
        total = 0
        for seed in SEEDS:
            for line in (ROOT / f"logs/p66/p3/{arm}_{seed}.log").read_text(
                    errors="replace").splitlines():
                m = re.search(r"\[carry\] (\w+) (\w+): (.*)$", line)
                if m:
                    total += 1
                    leg = p60.parse_leg(m.group(3))
                    if leg.get("clean_slip") is not None and leg.get("ticks") is not None:
                        parsed += 1
        ok(parsed == total, f"{arm}: the P60 parser reads all {total} [carry] rows")
    before = ROOT / "logs/p66/p3/tree_md5_before.txt"
    after = ROOT / "logs/p66/p3/tree_md5_after.txt"
    ok(before.is_file() and after.is_file() and before.read_text() == after.read_text(),
       "tree md5s identical before/after the batch")
    print(f"  {'PASS' if bad == 0 else 'FAIL'}: {bad} failure(s)")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
