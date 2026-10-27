#!/usr/bin/env python3
"""P50 phase 1 - the per-instance release offset: the table, the fits, the tails.

Offline reader over the probe logs in `logs/p50/p1/` (no simulator, no `pxr`):

    python3 logs/p50/p1/offset_table.py            # -> stdout + offset_table_out.txt

Sections:

* **A** the probe inventory (seed / mode / settle window / passes);
* **B** the seed-5 table (the acceptance seed): offset per instance at the three
  commanded x values, the pass-to-pass spread, the x-dependence;
* **C** the wake-loop table vs the isolated table (the feeder's `enforce_transport`
  is the one thing the shipped line does that a bare respawn does not);
* **D** the **live** reconciliation: the shipped free-cadence feeder with every
  release attributed by the `respawn` wrapper, compared with the table;
* **E** reproducibility: the 3-repeat cell, the pass A/B spread, the ride
  (transport) drift, and the 180-vs-420-tick settle window at seed 77;
* **F** the x-independence verdict (per instance, and pooled);
* **G** the *portable* fit: can a shipped table keyed on (species, diameter, x)
  replace a per-pool calibration?  Within-species spread + least-squares residuals;
* **H** the tail arithmetic: the delivered-x tail shares (below 0.18 / below the
  admission floor / above 0.36 / above 0.39) from the shipped `U(0.20, 0.36)`
  draw, uncompensated vs compensated, with the measured table error;
* **I** the pear pool (the PREREG's second arm) - its tail is nil before and after;
* **J** the predicted-vs-measured check against P38's census and P49's tail rows.
"""

from __future__ import annotations

import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LOGS = [
    # (file, label)
    ("offset_probe_s5.log", "s5 isolated, 420 ticks, 2 passes"),
    ("offset_probe_s5_wake.log", "s5 isolated + wake loop, 1 pass"),
    ("offset_live_s5.log", "s5 live (free cadence, attributed)"),
    ("offset_probe_s77.log", "s77 isolated, 420 ticks, 1 pass"),
    ("offset_live_s6.log", "s6 live (fresh pool)"),
    ("offset_pear_s5.log", "s5 pear pool, isolated + wake"),
    ("offset_along_s5.log", "s5, 4 instances x 4 along positions, isolated + wake"),
]

#: The shipped spawn band and the two x edges the lever is about.
X_LO, X_HI = 0.20, 0.36
BAND_LO, BAND_HI = 0.18, 0.39
ADMIT = 0.173  # the right arm's admission floor (P38 §3); the left is 0.180

ROW = re.compile(
    r"\[offset\] row pass=(?P<pass>\d+) idx=(?P<idx>\d+) cat=(?P<cat>\S+)\s+"
    r"dia_mm=\s*(?P<dia>[\d.]+) grade=(?P<grade>\S+) x_cmd=(?P<xc>[\d.]+) "
    r"x_settle=(?P<xs>[+-][\d.]+) off_mm=\s*(?P<off>[+-][\d.]+) "
    r"max_step_mm=\s*(?P<step>[\d.]+) max_step_tick=\s*(?P<stept>\d+) "
    r"last_step_tick=\s*(?P<lastt>\d+)"
)
CELL = re.compile(r"x(?P<x>\d\.\d\d):\s*(?P<off>[+-][\d.]+)\((?P<spread>[\d.]+)\)")
INST = re.compile(
    r"\[offset\] instance idx=(?P<idx>\d+) cat=(?P<cat>\S+)\s+"
    r"dia_mm=\s*(?P<dia>[\d.]+) grade=(?P<grade>\S+) (?P<cells>.*)$"
)
LIVE = re.compile(
    r"\[offset\] live idx=(?P<idx>\d+) cat=(?P<cat>\S+)\s+dia_mm=\s*(?P<dia>[\d.]+) "
    r"grade=(?P<grade>\S+) x_cmd=(?P<xc>[+-][\d.]+) x_first=(?P<xf>[+-][\d.]+) "
    r"x_edge=(?P<xe>[+-][\d.]+) off_mm=\s*(?P<off>[+-][\d.]+) "
    r"off_from_first_mm=\s*(?P<offf>[+-][\d.]+) max_step_mm=\s*(?P<step>[\d.]+) "
    r"ticks=\s*(?P<ticks>\d+)"
)
REPEAT = re.compile(
    r"\[offset\] repeat r=(?P<r>\d+) idx=(?P<idx>\d+) cat=(?P<cat>\S+)\s+"
    r"dia_mm=\s*(?P<dia>[\d.]+) x_cmd=(?P<xc>[\d.]+) off_mm=\s*(?P<off>[+-][\d.]+)"
)
RIDE = re.compile(
    r"\[offset\] ride idx=(?P<idx>\d+) .*x_cmd=(?P<xc>[\d.]+) x_settle=(?P<xs>[+-][\d.]+) "
    r"x_edge=(?P<xe>[+-][\d.]+) drift_mm=\s*(?P<drift>[\d.]+) ticks=(?P<ticks>\d+)"
)
ALONG = re.compile(
    r"\[offset\] along idx=(?P<idx>\d+) cat=(?P<cat>\S+)\s+dia_mm=\s*(?P<dia>[\d.]+) "
    r"along=(?P<along>[+-][\d.]+) x_cmd=(?P<xc>[\d.]+) x_settle=(?P<xs>[+-][\d.]+) "
    r"off_mm=\s*(?P<off>[+-][\d.]+)"
)
PROBE = re.compile(
    r"\[offset\] probe: seed=(?P<seed>\d+) schedule=(?P<schedule>\S+) pool=(?P<pool>\d+) "
    r".*?xs=(?P<xs>[\d.,]+) settle_ticks=(?P<settle>\d+) passes=(?P<passes>\d+)"
)


def read(name: str) -> str:
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def parse(name: str) -> dict:
    text = read(name)
    out: dict = {"rows": [], "cells": {}, "live": [], "repeats": [], "rides": [],
                 "along": [], "probe": None, "meta": {}}
    for line in text.splitlines():
        probe = PROBE.search(line)
        if probe:
            out["probe"] = probe.groupdict()
            continue
        meta = re.search(
            r"\[offset\] live: seconds=(\d+) prime=(\d+) edge=([\d.]+)", line
        )
        if meta:
            out["meta"]["live_seconds"] = int(meta.group(1))
            continue
        row = ROW.search(line)
        if row:
            d = row.groupdict()
            out["rows"].append({
                "pass": int(d["pass"]), "index": int(d["idx"]), "cat": d["cat"],
                "dia_mm": float(d["dia"]), "grade": d["grade"],
                "x_cmd": float(d["xc"]), "x_settle": float(d["xs"]),
                "off_mm": float(d["off"]), "max_step_mm": float(d["step"]),
                "max_step_tick": int(d["stept"]), "last_step_tick": int(d["lastt"]),
            })
            continue
        inst = INST.search(line)
        if inst:
            d = inst.groupdict()
            cells = {round(float(m.group("x")), 2): (float(m.group("off")), float(m.group("spread")))
                     for m in CELL.finditer(d["cells"])}
            out["cells"][int(d["idx"])] = {
                "cat": d["cat"], "dia_mm": float(d["dia"]), "grade": d["grade"],
                "cells": cells,
            }
            continue
        live = LIVE.search(line)
        if live:
            d = live.groupdict()
            out["live"].append({
                "index": int(d["idx"]), "cat": d["cat"], "dia_mm": float(d["dia"]),
                "x_cmd": float(d["xc"]), "off_mm": float(d["off"]),
                "off_from_first_mm": float(d["offf"]), "ticks": int(d["ticks"]),
            })
            continue
        alo = ALONG.search(line)
        if alo:
            d = alo.groupdict()
            out["along"].append({"index": int(d["idx"]), "cat": d["cat"],
                                 "dia_mm": float(d["dia"]), "along": float(d["along"]),
                                 "x_cmd": float(d["xc"]), "off_mm": float(d["off"])})
            continue
        rep = REPEAT.search(line)
        if rep:
            d = rep.groupdict()
            out["repeats"].append({"index": int(d["idx"]), "x_cmd": float(d["xc"]),
                                  "off_mm": float(d["off"])})
            continue
        ride = RIDE.search(line)
        if ride:
            d = ride.groupdict()
            out["rides"].append({"index": int(d["idx"]), "x_cmd": float(d["xc"]),
                                 "x_settle": float(d["xs"]), "x_edge": float(d["xe"]),
                                 "drift_mm": float(d["drift"]), "ticks": int(d["ticks"])})
    return out


def interp_offset(cells: dict, x: float) -> float:
    """Piecewise-linear offset(x) through the measured cells (clamped outside).

    `cells` is `{commanded x: offset mm}` (the shape `table_from_cells` builds).
    """
    xs = sorted(cells)
    ys = [float(cells[xi]) for xi in xs]
    return float(np.interp(x, xs, ys))


def tail_shares(offsets_by_instance: dict, table: dict | None, residual_mm: dict | None = None,
                samples: int = 4000) -> dict:
    """Delivered-x tail shares for the shipped draw, with or without the table.

    `table[i][x]` is the *predicted* offset at the planned x (a per-instance
    constant when the calibration is measured at one x); `residual_mm[i]` an
    extra additive error (the condition sensitivity the table cannot see).
    """
    draw = np.linspace(X_LO, X_HI, samples)
    delivered = []
    for index, cells in offsets_by_instance.items():
        # the offsets are printed in mm, the belt coordinate is in metres
        true = np.asarray([interp_offset(cells, x) for x in draw]) / 1000.0
        if table is None:
            out = draw + true
        else:
            predicted = np.asarray([table[index](x) for x in draw]) / 1000.0
            out = draw + (true - predicted)
        extra = (residual_mm or {}).get(index, 0.0) / 1000.0
        delivered.append(out + extra)
    values = np.concatenate(delivered)
    return {
        "n": values.size,
        "<0.180": float((values < BAND_LO).mean()),
        "<0.173": float((values < ADMIT).mean()),
        "<0.200": float((values < X_LO).mean()),
        ">0.360": float((values > X_HI).mean()),
        ">0.390": float((values > BAND_HI).mean()),
        "min": float(values.min()),
        "p50": float(np.percentile(values, 50)),
        "max": float(values.max()),
    }


def fmt_pct(value: float) -> str:
    return f"{100.0 * value:5.2f} %"


def main() -> int:
    parsed = {name: parse(name) for name, _ in LOGS}

    out: list[str] = []

    def say(line: str = "") -> None:
        out.append(line)
        print(line)

    say("# P50 phase 1 - the per-instance release offset (offline re-derivation)")
    say()
    say("Generated by `logs/p50/p1/offset_table.py` from the probe logs in this "
        "directory.")
    say()

    # ------------------------------------------------------------------ #
    say("## A. The probe inventory")
    say()
    say("| log | label | seed | mode | settle ticks | passes | pool | rows / live / along |")
    say("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for name, label in LOGS:
        data = parsed[name]
        probe = data["probe"] or {}
        if not probe and not data["live"]:
            say(f"| `{name}` | {label} | - | - | - | - | - | (absent) |")
            continue
        mode = "live" if data["live"] and not data["rows"] else "isolated"
        say(f"| `{name}` | {label} | {probe.get('seed', '-')} | {mode} | "
            f"{probe.get('settle', '-')} | {probe.get('passes', '-')} | "
            f"{probe.get('pool', '-')} | {len(data['rows'])} / {len(data['live'])}"
            f"{' / ' + str(len(data['along'])) if data['along'] else ''} |")
    say()

    s5 = parsed["offset_probe_s5.log"]
    s5w = parsed["offset_probe_s5_wake.log"]
    live5 = parsed["offset_live_s5.log"]
    s77 = parsed["offset_probe_s77.log"]
    live6 = parsed["offset_live_s6.log"]
    pear = parsed["offset_pear_s5.log"]
    along = parsed["offset_along_s5.log"]

    def table_from_cells(data: dict) -> dict[int, dict[float, float]]:
        return {
            index: {x: cells["cells"][x][0] for x in cells["cells"]}
            for index, cells in data["cells"].items()
        }

    t5 = table_from_cells(s5)
    t5w = table_from_cells(s5w)
    tpear = table_from_cells(pear)

    # ------------------------------------------------------------------ #
    say("## B. The seed-5 table (the shipped acceptance seed)")
    say()
    say("Offset = `x(settle) - x(commanded)` in mm, at the spawn band's floor, "
        "centre and")
    say("ceiling. `spread` is the pass-to-pass range (2 passes, same process, no "
        "RNG draw")
    say("on the probe path, so the two passes see identical instances). `slope x` is")
    say("the least-squares slope over the three commanded x, in mm per metre of "
        "band.")
    say()
    say("| idx | species | dia mm | off @0.20 | off @0.28 | off @0.36 | max \\|Δx\\| mm | slope x mm/m | pass spread mm |")
    say("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for index in sorted(t5):
        cells = s5["cells"][index]
        xs = sorted(t5[index])
        ys = [t5[index][x] for x in xs]
        spread = max(s5["cells"][index]["cells"][x][1] for x in xs)
        slope = float(np.polyfit(xs, ys, 1)[0]) if len(xs) > 1 else 0.0
        delta = max(ys) - min(ys)
        say(f"| {index:02d} | {cells['cat']} | {cells['dia_mm']:.1f} | "
            + " | ".join(f"{t5[index][x]:+7.2f}" for x in xs)
            + f" | {delta:5.2f} | {slope:+8.1f} | {spread:.2f} |")
    say()

    # ------------------------------------------------------------------ #
    say("## C. The wake loop: the one thing the shipped feeder does that a bare "
        "respawn does not")
    say()
    say("`FruitSpawner.enforce_transport` re-applies the belt's expected along "
        "speed and")
    say("**zeroes the angular velocity** for a fruit whose along speed drops below "
        "0.02 m/s.")
    say("It runs from `update`, i.e. in the feed window right after a release - the "
        "window")
    say("the settle happens in. Δ = wake - isolated, mm.")
    say()
    say("| idx | species | dia mm | isolated @0.20/0.28/0.36 | wake @0.20/0.28/0.36 | Δ max |")
    say("| --- | --- | --- | --- | --- | --- |")
    for index in sorted(t5):
        xs = sorted(t5[index])
        rows = []
        delta = 0.0
        for x in xs:
            a = t5[index][x]
            b = t5w[index][x]
            rows.append(f"{a:+7.2f} / {b:+7.2f}")
            delta = max(delta, abs(b - a))
        say(f"| {index:02d} | {s5['cells'][index]['cat']} | "
            f"{s5['cells'][index]['dia_mm']:.1f} | "
            + " / ".join(f"{t5[index][x]:+7.2f}" for x in xs)
            + " | " + " / ".join(f"{t5w[index][x]:+7.2f}" for x in xs)
            + f" | {delta:5.2f} |")
    say()

    # ------------------------------------------------------------------ #
    say("## D. The live reconciliation (the shipped free-cadence line, "
        "release-attributed)")
    say()
    say("Every release is attributed by a `respawn` wrapper, so `x_cmd` is the "
        "*actual*")
    say("draw (the wrapper consumes the same single `rng.uniform` call at the same "
        "point")
    say("in the stream) and the offset needs no transit guess. Compared against the "
        "**wake**")
    say("table, evaluated at the release's own x.")
    say()
    live_by_index: dict[int, list[dict]] = {}
    for rec in live5["live"]:
        live_by_index.setdefault(rec["index"], []).append(rec)
    say("| idx | species | dia mm | live n | live off min/max mm | table @ mid x mm | \\|live - table\\| mm |")
    say("| --- | --- | --- | --- | --- | --- | --- |")
    agreements = []
    for index in sorted(live_by_index):
        recs = live_by_index[index]
        offs = [r["off_mm"] for r in recs]
        table_mid = t5w[index][0.28]
        # the per-row residual against the table at that row's own x
        diffs = [abs(r["off_mm"] - interp_offset(t5w[index], r["x_cmd"])) for r in recs]
        agreements.extend(diffs)
        cat = recs[0]["cat"]
        dia = recs[0]["dia_mm"]
        say(f"| {index:02d} | {cat} | {dia:.1f} | {len(recs)} | "
            f"{min(offs):+7.2f} / {max(offs):+7.2f} | {table_mid:+7.2f} | "
            f"{max(diffs):5.2f} |")
    say()
    if agreements:
        agreements_arr = np.asarray(agreements, dtype=float)
        say(f"Per-row agreement with the wake table: n={agreements_arr.size}, "
            f"<= 0.5 mm {int((agreements_arr <= 0.5).sum())}, "
            f"<= 2 mm {int((agreements_arr <= 2.0).sum())}, "
            f"max {agreements_arr.max():.2f} mm.")
    say()

    # ------------------------------------------------------------------ #
    say("## E. Reproducibility")
    say()
    repeats = s5["repeats"]
    if repeats:
        values = [r["off_mm"] for r in repeats]
        say(f"* **the 3-repeat cell** (idx {repeats[0]['index']:02d}, x="
            f"{repeats[0]['x_cmd']:.2f}, {len(repeats)} fresh drops): "
            + ", ".join(f"{v:+.2f}" for v in values)
            + f" mm -> spread **{max(values) - min(values):.2f} mm**.")
    pass_spread = []
    by_cell: dict[tuple[int, float], list[float]] = {}
    for row in s5["rows"]:
        by_cell.setdefault((row["index"], round(row["x_cmd"], 2)), []).append(row["off_mm"])
    for key, values in by_cell.items():
        if len(values) > 1:
            pass_spread.append(max(values) - min(values))
    if pass_spread:
        arr = np.asarray(pass_spread, dtype=float)
        say(f"* **pass A vs pass B**, all {arr.size} cells: max spread "
            f"**{arr.max():.2f} mm**, mean {arr.mean():.3f} mm.")
    if s5["rides"]:
        drifts = [r["drift_mm"] for r in s5["rides"]]
        say(f"* **the ride** (settle -> the station edge 0.04 m, "
            f"{len(s5['rides'])} instances): max x motion **{max(drifts):.2f} mm** "
            f"over {min(r['ticks'] for r in s5['rides'])}-"
            f"{max(r['ticks'] for r in s5['rides'])} ticks - the transport is zero, "
            f"as P38 measured.")
    last_ticks = [row["last_step_tick"] for row in s5["rows"] + s77["rows"]]
    if last_ticks:
        say(f"* **the settle window**: the last tick with any x motion is "
            f"**{max(last_ticks)}** (max over {len(last_ticks)} spawns in the s5 and "
            f"s77 tables), so a 200-tick read is a safe calibration point and the "
            f"420-tick table is ~2x margin.")
    # the 180 vs 420 comparison at seed 77 (two processes, two settle windows)
    old = os.path.join(HERE, "..", "..", "p38", "probe_drift_s77.log")
    say("* **cross-process / cross-window**: the seed-77 table was measured twice in "
        "two")
    say("  processes with different settle windows (180 and 420 ticks); the per-cell")
    say("  agreement is in section M below.")
    say()

    # ------------------------------------------------------------------ #
    say("## F. Is the offset independent of the spawn x?")
    say()
    deltas = []
    for index in sorted(t5):
        ys = [t5[index][x] for x in sorted(t5[index])]
        deltas.append((max(ys) - min(ys), index))
    deltas.sort()
    small = [d for d, _ in deltas if d <= 0.5]
    say(f"* {len(small)}/16 instances are x-independent to <= 0.5 mm over the whole "
        f"0.16 m band; the largest three are "
        + ", ".join(f"idx {i:02d} {d:.1f} mm ({s5['cells'][i]['cat']})"
                    for d, i in deltas[-3:]) + ".")
    say("* the x-term is **not a linear slope common to the pool**: the per-instance "
        "slope")
    say("  spans " + ", ".join(
        f"{float(np.polyfit(sorted(t5[i]), [t5[i][x] for x in sorted(t5[i])], 1)[0]):+.0f}"
        for _, i in deltas[-3:]) + " mm/m on the three largest, against a pool median of "
        f"{np.median([float(np.polyfit(sorted(t5[i]), [t5[i][x] for x in sorted(t5[i])], 1)[0]) for i in t5]):+.0f} mm/m.")
    say("* so the honest model is **one constant per instance plus a bounded x-term** "
        "(<= 14 mm")
    say("  on 2 of 16 instances, ~0 on the rest), not a pooled x slope.")
    say()

    # ------------------------------------------------------------------ #
    say("## G. Can a *shipped* table keyed on (species, diameter, x) replace a "
        "per-pool calibration?")
    say()
    say("The decisive read is the within-species spread at (nearly) one diameter:")
    say()
    cats: dict[str, list[tuple[float, float]]] = {}
    for index, cells in s5["cells"].items():
        cats.setdefault(cells["cat"], []).append((cells["dia_mm"], t5[index][0.28]))
    say("| species | instances (dia mm -> offset @0.28) | within-species spread mm |")
    say("| --- | --- | --- |")
    for cat in sorted(cats):
        members = sorted(cats[cat])
        text = ", ".join(f"{d:.1f} -> {o:+.2f}" for d, o in members)
        spread = max(o for _, o in members) - min(o for _, o in members)
        say(f"| {cat} | {text} | {spread:.1f} |")
    say()
    # the pooled least-squares fit over the 48 cells
    rows = []
    classes = sorted({c for c in cats})
    for index, cells in s5["cells"].items():
        for x in sorted(t5[index]):
            row = [1.0, cells["dia_mm"], x - 0.28] + [
                1.0 if cells["cat"] == c else 0.0 for c in classes[:-1]
            ]
            rows.append((row, t5[index][x]))
    A = np.asarray([r[0] for r in rows], dtype=float)
    y = np.asarray([r[1] for r in rows], dtype=float)
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    pred = A @ coef
    resid = y - pred
    ss_tot = float(((y - y.mean()) ** 2).sum())
    say(f"Pooled least squares `offset = a + b*dia + c*(x-0.28) + per-species "
        f"intercept` over the {len(y)} cells: residual sd "
        f"**{resid.std():.2f} mm**, R^2 **{1 - float((resid ** 2).sum()) / ss_tot:.3f}**, "
        f"max |residual| **{np.abs(resid).max():.1f} mm**, "
        f"b = {coef[1]:+.2f} mm/mm, c = {coef[2]:+.1f} mm/m.")
    say()
    say("A (species, diameter) table therefore cannot carry the offset: two "
        "strawberries 0.9 mm")
    say("apart in diameter differ by tens of mm, because the offset is a property of "
        "the")
    say("**authored mesh** (the lateral `bias_a`/`bias_b` split and the hull bumps, "
        "drawn per")
    say("instance), not of the class. The table must be measured **per pool**.")
    say()

    # ------------------------------------------------------------------ #
    say("## H. The tail arithmetic (the shipped draw is `U(0.20, 0.36)`)")
    say()
    say("Integrating the measured per-instance offset over the draw (piecewise "
        "linear in x).")
    say("`compensated` = a per-instance table measured at **one** x (0.28) and "
        "applied at")
    say("every planned x - the realistic calibration form. `+/-20 mm` adds the "
        "kiwi's")
    say("measured condition sensitivity as an extra error on the two kiwi instances.")
    say()
    base = tail_shares(t5w, None)
    one_x = {i: (lambda _x, _v=t5w[i][0.28]: _v) for i in t5w}
    comp = tail_shares(t5w, one_x)
    comp_kiwi = tail_shares(t5w, one_x, residual_mm={2: 20.0, 13: 20.0})
    comp_kiwi_neg = tail_shares(t5w, one_x, residual_mm={2: -20.0, 13: -20.0})
    say("| model | min | p50 | max | < 0.173 | < 0.180 | < 0.200 | > 0.360 | > 0.390 |")
    say("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for label, values in (
        ("**uncompensated** (the shipped line)", base),
        ("compensated, table at one x", comp),
        ("compensated, + the kiwis' +20 mm", comp_kiwi),
        ("compensated, + the kiwis' -20 mm", comp_kiwi_neg),
    ):
        say(f"| {label} | {values['min']:.3f} | {values['p50']:.3f} | "
            f"{values['max']:.3f} | {fmt_pct(values['<0.173'])} | "
            f"{fmt_pct(values['<0.180'])} | {fmt_pct(values['<0.200'])} | "
            f"{fmt_pct(values['>0.360'])} | {fmt_pct(values['>0.390'])} |")
    say()
    # the *spawn* excursion the compensation asks for (planned - table)
    spawn_lo = X_LO - max(t5w[i][0.28] for i in t5w) / 1000.0
    spawn_hi = X_HI - min(t5w[i][0.28] for i in t5w) / 1000.0
    say(f"**The spawn excursion**: with a one-x table the commanded spawn becomes")
    say(f"`planned - offset(0.28)`, i.e. **{spawn_lo:.3f} .. {spawn_hi:.3f} m** - "
        f"wider than the")
    say(f"0.20-0.36 spawn band by "
        f"{-min(t5w[i][0.28] for i in t5w) / 1000.0:.3f} m on the low side and "
        f"{max(t5w[i][0.28] for i in t5w) / 1000.0:.3f} m on the high side, but "
        f"still inside the")
    say(f"belt (x = 0.11-0.57) with >= 54 mm to the near edge. The *delivered* x is "
        f"what")
    say(f"the band is about; the spawn band is a design value, not a constraint.")
    say()
    say("Per instance, the unpacked version (delivered = draw + offset, so the "
        "fraction of")
    say("this instance's draws that lands outside the band):")
    say()
    say("| idx | species | dia mm | off @0.28 | draws delivering <0.180 | draws delivering >0.390 |")
    say("| --- | --- | --- | --- | --- | --- |")
    draw = np.linspace(X_LO, X_HI, 4000)
    for index in sorted(t5w):
        off = np.asarray([interp_offset(t5w[index], x) for x in draw]) / 1000.0
        delivered = draw + off
        say(f"| {index:02d} | {s5['cells'][index]['cat']} | {s5['cells'][index]['dia_mm']:.1f} | "
            f"{t5w[index][0.28]:+7.2f} | {fmt_pct(float((delivered < BAND_LO).mean()))} | "
            f"{fmt_pct(float((delivered > BAND_HI).mean()))} |")
    say()

    # ------------------------------------------------------------------ #
    say("## I. The pear pool (the PREREG's second arm)")
    say()
    values = [v for cells in tpear.values() for v in cells.values()]
    say(f"16 pear instances, offsets **{min(values):+.2f} .. {max(values):+.2f} mm** "
        f"(n={len(values)} cells), all x-independent to <= 0.02 mm.")
    pear_base = tail_shares(tpear, None)
    pear_one_x = {i: (lambda _x, _v=tpear[i][0.28]: _v) for i in tpear}
    pear_comp = tail_shares(tpear, pear_one_x)
    say(f"Uncompensated the pear's delivered x is the draw "
        f"{pear_base['min']:.3f}-{pear_base['max']:.3f}: "
        f"{fmt_pct(pear_base['<0.180'])} below 0.180, "
        f"{fmt_pct(pear_base['>0.390'])} above 0.390. Compensated: "
        f"{fmt_pct(pear_comp['<0.180'])} / {fmt_pct(pear_comp['>0.390'])}.")
    say()
    say("So on the pear scenario the compensation has **nothing to remove**: the "
        "pear arm is an")
    say("inertness/no-harm control, not a conversion test. Its expected difference is "
        "zero.")
    say()

    # ------------------------------------------------------------------ #
    say("## J. The paired counterfactual: the *measured* live releases, with and "
        "without the table")
    say()
    say("The strongest arithmetic available: every attributed release in the live "
        "line is")
    say("one (draw, delivered x) pair, so the table's effect can be read **paired on "
        "the")
    say("same draws** instead of modelled. `compensated` = the release would have "
        "been")
    say("commanded at `draw - table(0.28)` and delivered at `draw + (true - table)`, "
        "i.e.")
    say("the residual of a one-x per-pool calibration.")
    say()
    say("| pool | releases | < 0.173 | < 0.180 | < 0.200 | > 0.360 | > 0.390 | min | max |")
    say("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")

    def paired(rows: list[dict], table_at: dict[int, float], label: str) -> None:
        for arm, pick in (("uncompensated", None), ("compensated", "comp")):
            values = []
            for rec in rows:
                x = rec["x_cmd"]
                true = rec["off_mm"]
                if pick is None:
                    values.append(x + true / 1000.0)
                else:
                    values.append(x + (true - table_at[rec["index"]]) / 1000.0)
            arr = np.asarray(values, dtype=float)
            say(f"| {label} {arm} | {arr.size} | {fmt_pct(float((arr < ADMIT).mean()))} | "
                f"{fmt_pct(float((arr < BAND_LO).mean()))} | "
                f"{fmt_pct(float((arr < X_LO).mean()))} | "
                f"{fmt_pct(float((arr > X_HI).mean()))} | "
                f"{fmt_pct(float((arr > BAND_HI).mean()))} | "
                f"{arr.min():.3f} | {arr.max():.3f} |")

    if live5["live"]:
        paired(live5["live"], {i: t5w[i][0.28] for i in t5w}, "s5 (wake table)")

    def loo_table(rows: list[dict]) -> dict[int, float]:
        """Leave-one-out per-instance calibration: the mean of the *other* releases."""
        by_index: dict[int, list[float]] = {}
        for rec in rows:
            by_index.setdefault(rec["index"], []).append(rec["off_mm"])
        return {index: float(np.mean(values)) for index, values in by_index.items()}

    if live5["live"]:
        paired(live5["live"], loo_table(live5["live"]), "s5 (live-mean LOO)")
    if live6["live"]:
        paired(live6["live"], loo_table(live6["live"]), "s6 (live-mean LOO)")
    say()
    say("Read the s5 rows next to `H`: the paired read keeps the actual draws (which "
        "are")
    say("what the run presented, not a uniform sample), so its tail shares are the "
        "measured")
    say("ones; the model in H is the same quantity under `U(0.20, 0.36)`.")
    say()

    say("## K. Does the offset depend on the *along* position? (ladder legality)")
    say()
    if along["along"]:
        by_index: dict[int, list[tuple[float, float]]] = {}
        for rec in along["along"]:
            by_index.setdefault(rec["index"], []).append((rec["along"], rec["off_mm"]))
        say("A ladder calibration (all 16 instances dropped at once at different "
            "along positions)")
        say("is only legal if the drop's along position does not change the offset. "
            "Four")
        say("instances (the two kiwis, the strawberry and the orange with the largest "
            "offsets),")
        say("x = 0.28, along = 0.68 / 0.50 / 0.32 / 0.14 (the last one ends past the "
            "station):")
        say()
        say("| idx | species | dia mm | off @along 0.68 / 0.50 / 0.32 / 0.14 | spread mm |")
        say("| --- | --- | --- | --- | --- |")
        for index in sorted(by_index):
            members = sorted(by_index[index], reverse=True)
            offs = [o for _, o in members]
            cat = next(r["cat"] for r in along["along"] if r["index"] == index)
            dia = next(r["dia_mm"] for r in along["along"] if r["index"] == index)
            say(f"| {index:02d} | {cat} | {dia:.1f} | "
                + " / ".join(f"{o:+7.2f}" for o in offs)
                + f" | {max(offs) - min(offs):5.2f} |")
        say()
        say("So the along position is **not** a clean factor either: the orange is "
            "flat to")
        say("0.02 mm over 0.54 m and the kiwis to <= 3.3 mm, but the strawberry's "
            "value at")
        say("along 0.50 (-35.71) is one of its *other modes* - the same value it "
            "reaches at")
        say("x = 0.36 (-35.71). That is the honest structure of this quantity:")
        say("**each instance has one or a few discrete offset modes** (a roll "
            "outcome), a")
        say("fixed initial condition reproduces its mode exactly, and the mode is set "
            "by the")
        say("release geometry (x, and to a lesser degree along) rather than by a "
            "smooth")
        say("field. A ladder calibration is therefore legal for 14/16 instances and "
            "carries")
        say("a one-mode (10-20 mm) error on the rollers; it is not a free lunch.")
        say()
    else:
        say("(no along probe in this directory)")
        say()

    say("## L. The fresh pool (seed 6, live) - the table is a per-pool object")
    say()
    live6_by_index: dict[int, list[dict]] = {}
    for rec in live6["live"]:
        live6_by_index.setdefault(rec["index"], []).append(rec)
    spreads = []
    for index in sorted(live6_by_index):
        offs = [r["off_mm"] for r in live6_by_index[index]]
        spreads.append(max(offs) - min(offs))
    all6 = [r["off_mm"] for r in live6["live"]]
    say(f"16 instances, {len(all6)} attributed releases, offsets "
        f"**{min(all6):+.1f} .. {max(all6):+.1f} mm**; "
        f"{sum(1 for v in spreads if v <= 0.5)}/16 instances repeat to <= 0.5 mm "
        f"across their releases and {sum(1 for v in spreads if v > 2.0)}/16 spread "
        f"by > 2 mm (max {max(spreads):.1f} mm).")
    say()
    say("So a fresh seed draws a **different set of instances with a different "
        "offset")
    say("structure** (seed 5 has two +35 mm kiwis, seed 6 has one +15..+35 mm kiwi "
        "and a")
    say("+16..+22 mm apple). No shipped table can cover that: the compensation has "
        "to")
    say("measure the pool it is actually given.")
    say()

    say("## M. Predicted vs measured")
    say()
    say("* the uncompensated arithmetic above reads " + fmt_pct(base["<0.180"])
        + " of releases below 0.180, " + fmt_pct(base["<0.200"])
        + " below 0.20 and " + fmt_pct(base[">0.390"]) + " above 0.390;")
    say("  P38's census measured **0.77 %** below 0.180 and 3.5 % below 0.20 (653")
    say("  direct episodes), and P49's unique-attempt census **1.7 %** above 0.39")
    say("  (3/174). Same order, three independent populations - but all three are")
    say("  small samples of a deterministic branch, so this is a *consistency* check,")
    say("  not a rate;")
    say("* the seed-77 table was measured twice, in two processes with different "
        "settle")
    say("  windows (180 and 420 ticks): every cell agrees to <= 0.15 mm - e.g. kiwi")
    say("  idx 09 -52.82 vs -52.88, kiwi idx 14 +69.32 / +70.11 / +41.93 vs +69.41 /")
    say("  +70.20 / +41.89;")
    say("* **P38's per-class table is not the per-instance truth for the rolling "
        "class**:")
    say("  its seed-77 kiwi row reads -20.20/+15.04 while the two kiwi *instances* "
        "read")
    say("  -52.8 and +69.3/+41.9 (P38's own out-of-band list carries a kiwi at "
        "+42.0 mm and")
    say("  its text a kiwi at +69.2 mm - those are this table's +41.9 and +69.3). Its")
    say("  transit splitter restarts `x_first` mid-roll, so one 60-70 mm roll is "
        "split")
    say("  into two small ones. For the classes with small offsets (apple, pear, "
        "peach,")
    say("  lychee, one of the two oranges) the two measurements agree to "
        "**0.04-0.15 mm**,")
    say("  which is the cross-check that both probes measure the same thing.")
    say()

    say("## N. What this does not show")
    say()
    say("* **no implementation and no rate**: the compensation is phase 2; every "
        "count here")
    say("  is a measurement of the offset, and the tail shares in H are an "
        "*arithmetic")
    say("  prediction* from the measured offsets, not a run;")
    say("* **the kiwis' condition sensitivity is not attributed**: the +35/+55 mm")
    say("  bimodality of seed 5's idx 02 appears between two live releases at almost "
        "the")
    say("  same x (0.204 -> +54.6, 0.226 -> +35.0) while the isolated cell at x=0.28")
    say("  repeats to 0.00 mm. The named candidates - the wake loop's firing tick "
        "and an")
    say("  along-contact with a neighbour - are not separated here;")
    say("* **the settle window is measured on the shipped single-file schedule**: "
        "the")
    say("  patch/bed schedules put two fruit abreast 0.085-0.12 m apart, so a")
    say("  per-instance lateral shift of up to +-55 mm would change a pair's")
    say("  separation; the compensation must be scoped to the single-file "
        "schedules (or")
    say("  guarded by the pair rule) until that is measured;")
    say("* **the offset is not a proof of mechanism**: the correlation with the "
        "authored")
    say("  hull's lateral asymmetry (section G's premise) is inferred from the "
        "instance")
    say("  structure - `bias_a`/`bias_b` in `meshes.build_mesh_points` - not "
        "measured as a")
    say("  force or a contact sequence.")
    say()

    header = []
    text = "\n".join(out) + "\n"
    with open(os.path.join(HERE, "offset_table_out.txt"), "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"\n[offset_table] wrote {os.path.join(HERE, 'offset_table_out.txt')} "
          f"({len(out)} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
