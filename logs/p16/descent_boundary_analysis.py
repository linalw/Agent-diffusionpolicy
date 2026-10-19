#!/usr/bin/env python3
"""P16 offline diagnosis refresh: the descent shortfall and the hold walk.

Read-only on the tree (branch `p-supply`, 2026-10-19). Reads:

* `logs/p12a2/{10_seed11,11_seed5,12_seed23}_mass.log` - the mass base's
  `[motion] approach` / `dynamic descent:` / `dynamic catch-up:` lines;
* `logs/p14b/traces_s{11,5,23}/trace_NN_*.json` - the per-tick trace rows
  (the P14-B corpus, byte-identical to the mass base);
* `logs/r10/reach_intercept_{left,right}.json` - the R10 reach map.

Writes only under `logs/p16/`. No simulator, no `src/`/`scripts/` edit.
"""

from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
LOGS = os.path.join(ROOT, "logs")

MASS = {
    11: os.path.join(LOGS, "p12a2", "10_seed11_mass.log"),
    5: os.path.join(LOGS, "p12a2", "11_seed5_mass.log"),
    23: os.path.join(LOGS, "p12a2", "12_seed23_mass.log"),
}
TRACES = {
    11: os.path.join(LOGS, "p14b", "traces_s11"),
    5: os.path.join(LOGS, "p14b", "traces_s5"),
    23: os.path.join(LOGS, "p14b", "traces_s23"),
}

APPROACH_RE = re.compile(
    r"\[motion\] approach\(cartesian\): ([0-9.]+) cm, (\d+) samples.*?\|v\|max=([0-9.]+) m/s.*?end=([0-9.]+) mm"
)
DESCENT_RE = re.compile(
    r"dynamic descent: waited (\d+) ticks, intercept=([+-][0-9.]+) m \(station ([+-][0-9.]+), shift ([+-][0-9.]+) m\), "
    r"fruit dy=([+-][0-9.]+) m, deadline=([0-9.]+) m, t_desc=([0-9.]+) s"
)
CATCHUP_RE = re.compile(r"dynamic catch-up: residual=([0-9.]+) mm \(tol ([0-9.]+) mm\)")
CYCLE_RE = re.compile(
    r"\[cycle\] attempt (\d+): prepose=([0-9.]+)s hover=([0-9.]+)s descent=([0-9.]+)s close=([0-9.]+)s "
    r"grip=([0-9.]+)s lift=([0-9.]+)s"
)
RESULT_RE = re.compile(r"\[biarm\] result (\w+) index=(\d+) (\w+) grasped=(\w+) placed=(\w+) lift=([+-][0-9.]+)")
STATION_RE = re.compile(r"dynamic descent:.*station ([+-][0-9.]+)")


def quant(values, fmt="%.1f"):
    if not values:
        return "n=0"
    values = sorted(values)
    n = len(values)
    med = values[n // 2] if n % 2 else 0.5 * (values[n // 2 - 1] + values[n // 2])
    return (
        f"n={n} min={fmt % values[0]} med={fmt % med} max={fmt % values[-1]}"
    )


def part_a(out):
    out.append("=" * 78)
    out.append("PART A: the mass base's descent shortfall (the [motion] end= rows)")
    out.append("=" * 78)
    pooled_end = []
    pooled_dist = []
    pooled_vmax = []
    for seed, path in MASS.items():
        if not os.path.exists(path):
            out.append(f"seed {seed}: MISSING {path}")
            continue
        text = open(path, encoding="utf-8", errors="replace").read()
        ends, dists, vmaxs, samples = [], [], [], []
        for m in APPROACH_RE.finditer(text):
            dist, n, vmax, end = float(m.group(1)), int(m.group(2)), float(m.group(3)), float(m.group(4))
            ends.append(end)
            dists.append(dist)
            vmaxs.append(vmax)
            samples.append(n)
        desc = [DESCENT_RE.search(line) for line in text.splitlines() if "dynamic descent:" in line]
        desc = [d for d in desc if d]
        cup = [float(m.group(1)) for m in CATCHUP_RE.finditer(text)]
        cyc = [float(m.group(4)) for m in CYCLE_RE.finditer(text)]
        n_attempts = len(RESULT_RE.findall(text))
        out.append(f"\n--- seed {seed} ({os.path.basename(path)}), {n_attempts} [biarm] result rows ---")
        out.append(f"approach legs: {len(ends)}; end=  mm: {quant(ends)}")
        out.append(f"  end= rows: {['%.1f' % v for v in ends]}")
        out.append(f"  distance cm: {quant(dists)}; |v|max: {quant(vmaxs, '%.3f')}; samples: {quant(samples, '%d')}")
        if desc:
            waits = [int(d.group(1)) for d in desc]
            shifts = [abs(float(d.group(4))) for d in desc]
            fdys = [float(d.group(5)) for d in desc]
            deadlines = [float(d.group(6)) for d in desc]
            tdesc = [float(d.group(7)) for d in desc]
            out.append(f"dynamic descents: {len(desc)}")
            out.append(f"  waited ticks: {quant(waits, '%d')}; |shift| m: {quant(shifts, '%.4f')}; fruit dy m: {quant(fdys, '%.4f')}")
            out.append(f"  deadline m: {quant(deadlines, '%.4f')}; t_desc s: {quant(tdesc, '%.3f')}")
            out.append(f"  shifts (m): {['%+.4f' % float(d.group(4)) for d in desc]}")
        if cup:
            out.append(f"catch-up residual mm: {quant(cup)}; rows: {['%.1f' % v for v in cup]}")
        if cyc:
            out.append(f"[cycle] descent segment s: {quant(cyc, '%.2f')}")
        pooled_end += ends
        pooled_dist += dists
        pooled_vmax += vmaxs
    out.append(f"\nPOOLED approach legs {len(pooled_end)}: end= mm {quant(pooled_end)}")
    out.append(f"POOLED distance cm {quant(pooled_dist)}; |v|max {quant(pooled_vmax, '%.3f')}")
    out.append(
        "\nNOTE: the mass base's descent is the dynamic catch's 5.5-5.8 cm hover->grip leg\n"
        "(not the v1 static line's 6.4-9.6 cm approach). The v1 record for comparison:\n"
        "  logs/161 (shipped):  end= 42,88,46,45,43,48,80,45,59,47 mm (median 47)\n"
        "  logs/160 (carry cap 0.28): 42,90,40,43,50,77,62,54,72,50 mm (median 51)\n"
        "  logs/163 (integral bias): median 53 mm;  logs/165 (soft gains): unchanged\n"
        "  logs/166/167 (the collision probe): jaw stops 3.8 cm down with the belt (finger box\n"
        "  z=[1.146,1.215] below belt top 1.170) vs 23 cm without it."
    )


def load_trace(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def blocks(rows, phase):
    """Contiguous index ranges of `phase` in the row list."""
    out = []
    cur = None
    for i, r in enumerate(rows):
        if r.get("phase") == phase:
            if cur is None:
                cur = [i, i]
            else:
                cur[1] = i
        else:
            if cur is not None:
                out.append(tuple(cur))
                cur = None
    if cur is not None:
        out.append(tuple(cur))
    return out


MASTER_TABLE = os.path.join(LOGS, "p14b", "master_table.md")


def load_classes():
    """(seed, file) -> class from the P14-B master table (the P10-E rules)."""
    classes = {}
    if not os.path.exists(MASTER_TABLE):
        return classes
    for line in open(MASTER_TABLE, encoding="utf-8"):
        if not line.startswith("|") or "seed" in line or "---" in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6:
            continue
        try:
            seed = int(cells[1].lstrip("s"))
        except ValueError:
            continue
        classes[(seed, cells[2])] = cells[5]
    return classes


def classify(rows, outcome, seed, fname, classes):
    # the P14-B master table is authoritative (ok/carried/B1/B2, the P10-E
    # rules from the logs' `grasped` field, which the trace does not carry).
    key = fname.replace("trace_", "").replace("_scripted_", "_").removesuffix(".json")
    if (seed, key) in classes:
        return classes[(seed, key)]
    n_probe = sum(1 for r in rows if r.get("phase") == "takeoff_probe")
    if outcome == "ok":
        return "ok"
    if n_probe >= 120:
        return "B1"
    return "B2"


def part_b(out):
    out.append("")
    out.append("=" * 78)
    out.append("PART B: the trace decomposition - the hold walk and the hand's settling")
    out.append("=" * 78)
    out.append(
        "walk = |hand_rel(last hold) - hand_rel(freeze)| (the P14-B rule; freeze = last close row).\n"
        "jaw_d/fruit_d = the world displacement of the jaw centre / fruit from the freeze to the\n"
        "last hold row. rel_d = the world relative displacement (fruit - jaw) over the same span.\n"
    )
    rows_out = []
    per_class = {}
    classes = load_classes()
    for seed, tdir in TRACES.items():
        files = sorted(f for f in os.listdir(tdir) if f.endswith(".json"))
        for fname in files:
            d = load_trace(os.path.join(tdir, fname))
            rows = d["rows"]
            close = blocks(rows, "close")
            hold = blocks(rows, "hold")
            if not close or not hold:
                continue
            freeze = rows[close[-1][1]]
            hold_rows = rows[hold[0][0]: hold[0][1] + 1]
            last = hold_rows[-1]
            hr0 = freeze["hand_rel"]
            hr1 = last["hand_rel"]
            walk = sum((hr1[i] - hr0[i]) ** 2 for i in range(3)) ** 0.5 * 1000.0
            # the P14-B rule: the dfz (freeze-referenced drift) change across the
            # hold segment (first hold row -> last hold row)
            hr_first = hold_rows[0]["hand_rel"]
            dfz0 = sum((hr_first[i] - hr0[i]) ** 2 for i in range(3)) ** 0.5 * 1000.0
            walk_p14b = walk - dfz0
            # the phase-by-phase jaw motion (world) - where the hand moves
            catch = blocks(rows, "catchup")
            cu0 = rows[catch[0][0]]["jaw"] if catch else freeze["jaw"]
            cu1 = rows[catch[-1][1]]["jaw"] if catch else freeze["jaw"]
            cl0 = rows[close[0][0]]["jaw"]
            cu_d = [cu1[i] - cu0[i] for i in range(3)]
            cl_d = [freeze["jaw"][i] - cl0[i] for i in range(3)]
            # the z command vs the achieved z at the freeze and the last hold
            # (the catch/hold z command = fruit_z + the pad standoff 0.070)
            z_cmd_freeze = freeze["fruit"][2] + 0.070
            z_cmd_last = last["fruit"][2] + 0.070
            # the ejection / tracking read: the fruit's peak |v| during the hold
            # and the hand's own y velocity across the hold vs the fruit's
            hv = []
            if len(hold_rows) >= 2:
                a, b = hold_rows[0], hold_rows[-1]
                dt = max(b["t"] - a["t"], 1e-6)
                hv = [(b["jaw"][i] - a["jaw"][i]) / dt for i in range(3)]
            fvy_peak = max((abs(r["fruit_vel"][1]) for r in hold_rows), default=0.0)
            fvx_peak = max((abs(r["fruit_vel"][0]) for r in hold_rows), default=0.0)
            # the handoff's relative tip-fruit velocity (the last two catchup rows)
            relv = [float("nan")] * 3
            if catch and catch[0][1] >= 1:
                r0 = rows[catch[0][1] - 1]
                r1 = rows[catch[0][1]]
                dtc = max(r1["t"] - r0["t"], 1e-6)
                relv = [
                    (r1["tip"][k] - r0["tip"][k]) / dtc - r1["fruit_vel"][k]
                    for k in range(3)
                ]
            # the post-descent state: the first catch-up row's tip-to-fruit
            # offset (what the descent left for the solver) and the residual
            # the catch-up loop drives to its 6 mm tolerance
            cu1_row = rows[catch[0][0]] if catch else None
            pd_tip = None
            pd_res = None
            if cu1_row is not None:
                tip = cu1_row["tip"]
                fr = cu1_row["fruit"]
                pd_tip = [tip[i] - fr[i] for i in range(3)]
                des = [fr[0], fr[1], fr[2] + 0.010]  # fruit + FRUIT_DYNAMIC_PAD_LIFT
                pd_res = sum((tip[i] - des[i]) ** 2 for i in range(3)) ** 0.5 * 1000.0
            jaw0 = freeze["jaw"]
            jaw1 = last["jaw"]
            fruit0 = freeze["fruit"]
            fruit1 = last["fruit"]
            jaw_d = [jaw1[i] - jaw0[i] for i in range(3)]
            fruit_d = [fruit1[i] - fruit0[i] for i in range(3)]
            rel_d = [fruit_d[i] - jaw_d[i] for i in range(3)]
            cls = classify(rows, d.get("outcome", "fail"), seed, fname, classes)
            rows_out.append(
                {
                    "seed": seed,
                    "file": fname,
                    "arm": d.get("arm"),
                    "outcome": d.get("outcome"),
                    "cls": cls,
                    "walk_mm": walk,
                    "walk_p14b_mm": walk_p14b,
                    "jaw_d": jaw_d,
                    "fruit_d": fruit_d,
                    "rel_d": rel_d,
                    "hr_d": [hr1[i] - hr0[i] for i in range(3)],
                    "cu_d": cu_d,
                    "cl_d": cl_d,
                    "pd_tip": pd_tip,
                    "pd_res": pd_res,
                    "hv": hv,
                    "fvy_peak": fvy_peak,
                    "fvx_peak": fvx_peak,
                    "relv": relv,
                    "z_err_freeze": 1000.0 * (freeze["jaw"][2] - z_cmd_freeze),
                    "z_err_last": 1000.0 * (last["jaw"][2] - z_cmd_last),
                    "hold_rows": len(hold_rows),
                    "force_freeze": freeze.get("force"),
                    "force_last": last.get("force"),
                    "sep_freeze": freeze.get("sep"),
                    "sep_last": last.get("sep"),
                }
            )
            per_class.setdefault(cls, []).append(rows_out[-1])
    out.append(f"attempts analysed: {len(rows_out)}")
    hdr = (
        f"{'seed':>4} {'file':<28} {'arm':<5} {'out':<4} {'cls':<4} {'walk':>6} "
        f"{'|jaw_d|':>7} {'jaw_dx':>7} {'jaw_dy':>7} {'jaw_dz':>7} "
        f"{'|fruit_d|':>9} {'|rel_d|':>7} {'rel_dy':>7} {'rel_dx':>7} {'rel_dz':>7}"
    )
    out.append(hdr)
    for r in sorted(rows_out, key=lambda r: (r["seed"], r["file"])):
        jd = r["jaw_d"]
        fd = r["fruit_d"]
        rd = r["rel_d"]
        out.append(
            f"{r['seed']:>4} {r['file']:<28} {str(r['arm']):<5} {str(r['outcome']):<4} {r['cls']:<4} "
            f"{r['walk_mm']:>6.1f} "
            f"{1000*sum(v*v for v in jd)**0.5:>7.1f} {1000*jd[0]:>7.1f} {1000*jd[1]:>7.1f} {1000*jd[2]:>7.1f} "
            f"{1000*sum(v*v for v in fd)**0.5:>9.1f} "
            f"{1000*sum(v*v for v in rd)**0.5:>7.1f} {1000*rd[1]:>7.1f} {1000*rd[0]:>7.1f} {1000*rd[2]:>7.1f}"
        )
    out.append("")
    out.append("per-class summaries (mm); rel_d* = the world relative displacement (fruit - jaw):")
    out.append("  rel_dy = along-belt (the belt axis), rel_dx = cross-belt, rel_dz = vertical")
    for cls in ("ok", "carried", "B1", "B2"):
        rs = per_class.get(cls, [])
        if not rs:
            continue
        walks = [r["walk_mm"] for r in rs]
        walks_p14b = [r["walk_p14b_mm"] for r in rs]
        jaw_z = [1000 * r["jaw_d"][2] for r in rs]
        jaw_y = [1000 * r["jaw_d"][1] for r in rs]
        jaw_x = [1000 * r["jaw_d"][0] for r in rs]
        rel_y = [1000 * r["rel_d"][1] for r in rs]
        rel_z = [1000 * r["rel_d"][2] for r in rs]
        rel_x = [1000 * r["rel_d"][0] for r in rs]
        zef = [r["z_err_freeze"] for r in rs]
        zel = [r["z_err_last"] for r in rs]
        out.append(
            f"  {cls:<8} walk(freeze) {quant(walks):<24} walk(P14-B) {quant(walks_p14b)}"
        )
        out.append(
            f"  {'':<8} jaw_dx {quant(jaw_x):<26} jaw_dy {quant(jaw_y):<26} jaw_dz {quant(jaw_z)}"
        )
        out.append(
            f"  {'':<8} rel_dy {quant(rel_y):<26} rel_dx {quant(rel_x):<26} rel_dz {quant(rel_z)}"
        )
        out.append(
            f"  {'':<8} z_err@freeze {quant(zef):<22} z_err@hold_end {quant(zel)}   (jaw z - (fruit z + 70 mm))"
        )
    # the ejection / tracking read
    out.append("")
    out.append("the hold's ejection / tracking read (the fruit's peak |v| during the hold vs the")
    out.append("hand's own mean y velocity across the hold; the handoff's relative tip-fruit velocity):")
    for cls in ("ok", "carried", "B1", "B2"):
        rs = per_class.get(cls, [])
        if not rs:
            continue
        fy = [r["fvy_peak"] for r in rs]
        fx = [r["fvx_peak"] for r in rs]
        hy = [1000 * r["hv"][1] for r in rs if r["hv"]]
        rv = [r["relv"][1] for r in rs if r["relv"] and r["relv"][1] == r["relv"][1]]
        out.append(
            f"  {cls:<8} fruit |vy|peak {quant(fy, '%.3f'):<26} |vx|peak {quant(fx, '%.3f'):<26} hand vy {quant(hy)} mm/s"
        )
        out.append(f"  {'':<8} handoff relv_y mm/s {quant([1000*v for v in rv])}")
    # the post-descent state (the first catch-up row)
    out.append("")
    out.append("the post-descent state (the first catch-up row; tip - fruit, and the residual vs")
    out.append("the desired tip = fruit + 10 mm z, the loop's own 6 mm tolerance):")
    for cls in ("ok", "carried", "B1", "B2"):
        rs = per_class.get(cls, [])
        if not rs:
            continue
        tips = [r["pd_tip"] for r in rs if r["pd_tip"] is not None]
        res = [r["pd_res"] for r in rs if r["pd_res"] is not None]
        if not tips:
            continue
        out.append(
            f"  {cls:<8} tip-fruit dx {quant([1000*t[0] for t in tips]):<26} dy {quant([1000*t[1] for t in tips]):<26} dz {quant([1000*t[2] for t in tips])}"
        )
        out.append(f"  {'':<8} post-descent residual mm {quant(res)}")
    # the phase-by-phase jaw motion: catch-up, close, hold
    out.append("")
    out.append("phase-by-phase jaw motion (world, mm) - where the hand moves:")
    for cls in ("ok", "carried", "B1", "B2"):
        rs = per_class.get(cls, [])
        if not rs:
            continue
        cu = [1000 * sum(v * v for v in r["cu_d"]) ** 0.5 for r in rs]
        cl = [1000 * sum(v * v for v in r["cl_d"]) ** 0.5 for r in rs]
        cl_y = [1000 * r["cl_d"][1] for r in rs]
        cl_z = [1000 * r["cl_d"][2] for r in rs]
        cu_y = [1000 * r["cu_d"][1] for r in rs]
        cu_z = [1000 * r["cu_d"][2] for r in rs]
        out.append(
            f"  {cls:<8} |catchup| {quant(cu):<22} |close| {quant(cl):<24} close_dy {quant(cl_y):<26} close_dz {quant(cl_z)}"
        )
        out.append(
            f"  {'':<8} catchup_dy {quant(cu_y):<24} catchup_dz {quant(cu_z)}"
        )
    # the walk's composition in the hand frame
    out.append("")
    out.append("the walk vector's hand-frame components (hand_rel(last)-hand_rel(freeze)); in this")
    out.append("quat the hand x = -world y (along belt), hand y = -world x (cross belt), hand z = -world z:")
    for cls in ("ok", "carried", "B1", "B2"):
        rs = per_class.get(cls, [])
        if not rs:
            continue
        comps = []
        for r in rs:
            hd = r["hr_d"]
            comps.append((abs(hd[0]) * 1000, abs(hd[1]) * 1000, abs(hd[2]) * 1000))
        out.append(
            f"  {cls:<8} |dx| {quant([c[0] for c in comps]):<26} |dy| {quant([c[1] for c in comps]):<26} |dz| {quant([c[2] for c in comps])}"
        )
    # the no-grasp attempts in detail (the P15 target class)
    out.append("")
    out.append("the no-grasp (B1/B2) attempts, hold-segment detail (world rel_d = fruit-jaw):")
    for r in sorted(rows_out, key=lambda r: (r["seed"], r["file"])):
        if r["cls"] not in ("B1", "B2"):
            continue
        hd = r["hr_d"]
        rd = r["rel_d"]
        out.append(
            f"  s{r['seed']} {r['file'][6:]:<24} {r['cls']} walk={r['walk_mm']:.1f} (P14-B {r['walk_p14b_mm']:.1f})  "
            f"rel_dy={1000*rd[1]:+.1f} rel_dx={1000*rd[0]:+.1f} rel_dz={1000*rd[2]:+.1f} mm  "
            f"jaw_dy={1000*r['jaw_d'][1]:+.1f} jaw_dx={1000*r['jaw_d'][0]:+.1f} jaw_dz={1000*r['jaw_d'][2]:+.1f}  "
            f"z_err {r['z_err_freeze']:+.1f}->{r['z_err_last']:+.1f} mm  "
            f"F {r['force_freeze']}->{r['force_last']} N"
        )
    return rows_out


def part_c(out):
    out.append("")
    out.append("=" * 78)
    out.append("PART C: the reach-band geometry (the R10 map + the aim window)")
    out.append("=" * 78)
    for side in ("left", "right"):
        path = os.path.join(LOGS, "r10", f"reach_intercept_{side}.json")
        d = json.load(open(path, encoding="utf-8"))
        xs = sorted({r["x"] for r in d})
        dys = sorted({r["dy"] for r in d})
        out.append(f"\n{side}: grip_residual (mm) per (x, dy); '*' = <= 6 mm clean")
        head = "  x\\dy " + " ".join(f"{dy:+.2f}" for dy in dys)
        out.append(head)
        for x in xs:
            cells = []
            for dy in dys:
                r = [q for q in d if q["x"] == x and q["dy"] == dy]
                if not r:
                    cells.append("  n/a")
                    continue
                mm = r[0]["grip_residual"] * 1000.0
                cells.append(("*" if mm <= 6.0 else " ") + f"{mm:5.1f}")
            out.append(f"  {x:.2f} " + " ".join(cells))
        # the clean bands
        out.append(f"  clean (<=6 mm) bands per x:")
        for x in xs:
            clean = []
            for dy in dys:
                r = [q for q in d if q["x"] == x and q["dy"] == dy]
                if r and r[0]["grip_residual"] * 1000.0 <= 6.0:
                    clean.append(dy)
            if clean:
                out.append(f"    x={x:.2f}: dy {min(clean):+.2f} .. {max(clean):+.2f}")
            else:
                out.append(f"    x={x:.2f}: none")
        zs = [r["jaw_grip"][2] for r in d]
        out.append(f"  jaw_grip z: min {min(zs):.3f} max {max(zs):.3f} m (belt top 1.170)")
    out.append(
        "\nThe shipped mass-base aim window: intercept = station_y + shift, |shift| <= 0.03\n"
        "(FRUIT_DYNAMIC_INTERCEPT_MAX); stations: left y=0.00, right y=-0.10. The R10-A.1\n"
        "band fix: left x=0.28 = -0.05..+0.10 (the +0.15/+0.20 rows are 8.2/6.5 mm, outside\n"
        "the 6 mm tolerance)."
    )


def main():
    out = []
    part_a(out)
    rows = part_b(out)
    part_c(out)
    text = "\n".join(out) + "\n"
    dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), "descent_boundary_tables.txt")
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)
    # machine-readable summary for the design doc
    summary = {
        "n_attempts": len(rows),
        "walk_mm": {r["file"]: round(r["walk_mm"], 2) for r in rows},
    }
    with open(os.path.join(os.path.dirname(dest), "descent_boundary_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
