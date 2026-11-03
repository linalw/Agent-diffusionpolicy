#!/usr/bin/env python3
"""P108 census - decompose the approach error and score candidate apertures.

Reads per-tick `FRUIT_FRUIT_TRACE` cells (`ftrace_*.json`, one file per attempt,
`FRUIT_FRUIT_TRACE_ARM=1` so every row carries the arm's jaw centre) and answers
the three questions this phase's geometry depends on, in **world** coordinates
(the belt runs along -y, so `dy > 0` is *upstream*, `dx` is across the belt).

Why the window is what it is
----------------------------
A 4-pad cage's plate spans `z = -80.5 .. -20.5 mm` below the jaw centre
(`cage_hand`: `DISTAL_Z` 80.5 - the shipped lip; the plate is 60 mm long) and the
payload's equator sits at `-70.0 mm`.  A payload sphere of radius `r` therefore
overlaps the plate's axial band whenever `dz = fruit_z - jaw_z` is inside
`[-80.5 - r, -20.5 + r]` - a **~130 mm** band, i.e. almost the whole 55-60 mm
descent.  The window scored below is exactly those ticks, from the attempt's
start up to the close (the close is *meant* to interpenetrate: the pads are the
gripping faces, so it is excluded, as in `tasks._cage_probe_tick`).

Reads
-----
1. **The split**: `dy` (along-belt) and `|dx|` (lateral) of the payload relative
   to the tool axis over the window, at p50/p90/p95/max, plus the close-time aim
   (the number P107's 24 mm is *not*).
2. **The aperture per axis**: a pad face normal to an axis at `A/2` clears a
   sphere at offset `o` by `A/2 - (o + r)`, so `A = 2 (o + r)`; reported at the
   percentiles so a percentile decides, never the max alone.
3. **The neighbours and the required spacing**: a pad reaches
   `A/2 + 10 mm` (plate thickness) from the axis along its normal, so an
   upstream neighbour at gap `g` is fouled when
   `g < A/2 + 10 mm + r_nb + margin`.  The offsets are the trace's own `nb`
   rows (live fruit within 0.15 m), i.e. *this* supply's delivery, not the
   schedule's bounds.

Candidates are scored on the real trajectory (`CANDIDATES`), and the last
section prints the spacing each one demands against the delivered gaps.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from dataclasses import dataclass

import numpy as np

# Cage geometry (`cage_hand`): the plate's axial span and the payload's equator.
PLATE_DISTAL = 0.0805
PLATE_LENGTH = 0.060
PLATE_WIDTH = 0.026
PLATE_THICK = 0.010
MARGIN = 0.004  # +4 mm design margin on every clearance clause
#: Attempts skipped because the trace carried no cycle marks (see `attempt`).
SKIPPED: list = []


@dataclass(frozen=True)
class Candidate:
    name: str
    ax: float        # lateral (cross-belt) half aperture [m]
    ay_up: float     # upstream (arrival-side) half aperture [m]
    ay_dn: float     # downstream half aperture [m]
    note: str = ""

    @property
    def y_half(self) -> float:
        return max(self.ay_up, self.ay_dn)


CANDIDATES = (
    Candidate("cage120 (P107)", 0.060, 0.060, 0.060, "the shipped retrofit"),
    Candidate("round160", 0.080, 0.080, 0.080, "+40 mm"),
    Candidate("round210", 0.105, 0.105, 0.105, "2*(70+35), the measured need"),
    Candidate("oblong 86x210", 0.043, 0.105, 0.105, "narrow lateral, wide along"),
    Candidate("oblong 86x160", 0.043, 0.080, 0.080, "narrow lateral, +40 along"),
    Candidate("asym 86x120/60", 0.043, 0.060, 0.030, "wide upstream only"),
)


def _box_distance(point: np.ndarray, half: np.ndarray) -> float:
    rel = np.abs(point) - half
    outside = np.maximum(rel, 0.0)
    inside = min(float(np.max(rel)), 0.0)
    return float(np.linalg.norm(outside) + inside)


def pads_for(c: Candidate) -> tuple[np.ndarray, np.ndarray]:
    """Pad centres (4x3) and half extents (4x3) in the world/belt frame [m].

    Pad 0 = +x, 1 = +y (upstream), 2 = -x, 3 = -y (downstream).  Faces are
    normal to x / y; the plate's *width* spans the tangential axis, so the
    `pad_width <= aperture` rule (P107 iteration 1) is a property of the
    *closed* aperture, not of these open ones.
    """
    hw, ht, hl = PLATE_WIDTH / 2.0, PLATE_THICK / 2.0, PLATE_LENGTH / 2.0
    zc = -(PLATE_DISTAL - hl)
    centres = np.array(
        [
            [+(c.ax + ht), 0.0, zc],
            [0.0, +(c.ay_up + ht), zc],
            [-(c.ax + ht), 0.0, zc],
            [0.0, -(c.ay_dn + ht), zc],
        ]
    )
    half = np.array(
        [[ht, hw, hl], [hw, ht, hl], [ht, hw, hl], [hw, ht, hl]]
    )
    return centres, half


def clearance(c: Candidate, offset: np.ndarray, radius: float) -> tuple[float, int]:
    centres, half = pads_for(c)
    best, best_k = float("inf"), -1
    for k in range(4):
        gap = _box_distance(np.asarray(offset) - centres[k], half[k]) - radius
        if gap < best:
            best, best_k = gap, k
    return best, best_k


def load(trace_dir: str) -> list[dict]:
    out = []
    for path in sorted(glob.glob(os.path.join(trace_dir, "ftrace_*.json"))):
        with open(path) as fh:
            d = json.load(fh)
        rows = d.get("rows") or []
        if not rows or rows[0] is None:
            continue
        out.append(d)
    return out


def offsets(d: dict) -> list[dict]:
    """Per tick: the phase, the payload offset (world) and the jaw's z."""
    arm = d.get("arm") or "right"
    out = []
    for row in d["rows"]:
        if row is None:
            continue
        arms = row.get("arm") or {}
        a = arms.get(arm) or (list(arms.values())[0] if arms else None)
        if a is None:
            continue
        jaw = np.asarray(a["jaw"], dtype=float)
        out.append(
            {
                "phase": row.get("phase", ""),
                "off": np.asarray(row["p"], dtype=float) - jaw,
                "jaw_z": float(jaw[2]),
                "nb": row.get("nb") or [],
            }
        )
    return out


def descent_start(ticks: list[dict], close_at: int) -> int:
    """Index where the *final* approach window starts.

    The `descent` cycle mark lands at the leg's **end** (P95's note) and the
    leg itself lives at the tail of the `hover` phase, so the window cannot be
    found from the phase labels alone - and the raw z walk is fooled by the
    hover hold's sub-millimetre jitter.  What does separate the two regimes is
    the payload's distance: the ~5 s hover *wait* (and the pre-pose before it)
    has the payload 0.19-0.72 m upstream, while the descent starts at ~0.083 m
    (`[task] dynamic descent: fruit dy=+0.083`, 3963 attempts).  Start at the
    last tick whose along-belt offset is outside 0.25 m.
    """
    start = 0
    for i in range(min(close_at, len(ticks))):
        if abs(float(ticks[i]["off"][1])) > 0.25:
            start = i + 1
    return start


def attempt(d: dict) -> dict | None:
    """One attempt's arrival window, split, and per-candidate clearances."""
    r = 0.5 * float(d.get("diameter") or 0.06)
    band_lo = -(PLATE_DISTAL + r)
    ticks = offsets(d)
    if not ticks:
        return None
    close_at = next((i for i, t in enumerate(ticks) if t["phase"] == "close"), None)
    if close_at is None:
        # No cycle marks: `FRUIT_CYCLE_REPORT=1` was not set, so the trace has no
        # phase labels and the close cannot be located.  Reading the window anyway
        # would fold the carry/place legs (|dx| hundreds of mm) into the arrival
        # census - refuse instead of lying (`--check` turns this into an error).
        SKIPPED.append(d.get("attempt"))
        return None
    end = close_at
    start = descent_start(ticks, end)
    win = [t["off"] for t in ticks[start:end] if t["off"][2] >= band_lo]
    close = [t["off"] for t in ticks[end:] if t["phase"] == "close"]
    if not win:
        return None
    off = np.asarray(win, dtype=float)
    wait_min = min((t["off"][2] for t in ticks[:start]), default=float("inf"))
    out = {
        "attempt": d.get("attempt"),
        "arm": d.get("arm") or "right",
        "category": d.get("category", ""),
        "dia_mm": 2 * r * 1000.0,
        "placed": bool(d.get("placed")),
        "n_win": len(win),
        "dy": float(off[:, 1].max()),
        "dy_first": float(off[0, 1]),
        "dx_abs": float(np.abs(off[:, 0]).max()),
        "radial": float(np.hypot(off[:, 0], off[:, 1]).max()),
        "hover_z": wait_min,
        #: The descent *executed*: the pads reached the grip depth (the payload's
        #: equator sits 70 mm below the jaw, so a leg that stops 30-40 mm above
        #: it never put the pads beside the payload).  The blocked-descent
        #: attempts are a separate failure class and are not an aperture datum.
        "descent_ok": bool(float(off[:, 2].max()) >= -0.088),
        "z_end": float(off[:, 2].max()),
    }
    for c in CANDIDATES:
        cl = [clearance(c, o, r)[0] for o in off]
        out[f"clr:{c.name}"] = min(cl)
    if close:
        c = np.asarray(close, dtype=float)
        out["close_dx"] = float(np.abs(c[:, 0]).max())
        out["close_dy"] = float(np.abs(c[:, 1]).max())
        out["close_radial"] = float(np.hypot(c[:, 0], c[:, 1]).max())
    return out


def neighbours(d: dict) -> list[dict]:
    """The window's neighbour offsets (world, relative to the payload) [m]."""
    arm = d.get("arm") or "right"
    r = 0.5 * float(d.get("diameter") or 0.06)
    band_lo = -(PLATE_DISTAL + r)
    out, seen = [], set()
    for row in d["rows"]:
        if row is None:
            continue
        arms = row.get("arm") or {}
        a = arms.get(arm) or (list(arms.values())[0] if arms else None)
        if a is None:
            continue
        off = np.asarray(row["p"], dtype=float) - np.asarray(a["jaw"], dtype=float)
        if row.get("phase") == "close":
            break
        if off[2] < band_lo:
            continue
        for nb in row.get("nb") or []:
            if nb["i"] in seen:
                continue
            seen.add(nb["i"])
            out.append(
                {
                    "i": nb["i"],
                    "cat": nb.get("cat", ""),
                    "dia": float(nb.get("dia", 0.06)),
                    "d": np.asarray(nb["d"], dtype=float) / 1000.0,
                }
            )
    return out


def pct(v, q: float) -> float:
    return float(np.percentile(np.asarray(v, dtype=float), q)) if len(v) else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    rows, nbs = [], []
    for d in args.dirs:
        atts = load(d)
        print(f"## {d}: {len(atts)} attempts")
        if args.check and not atts:
            raise SystemExit(f"no usable ftrace rows under {d}")
        for a in atts:
            t = attempt(a)
            if t is not None:
                rows.append(t)
            nbs.extend(neighbours(a))
    if SKIPPED:
        print(f"\n  WARNING: {len(SKIPPED)} attempt(s) skipped - no `close` phase row "
              f"(run with FRUIT_CYCLE_REPORT=1): {SKIPPED}")
    if not rows:
        raise SystemExit("no window rows: run with FRUIT_FRUIT_TRACE_ARM=1 "
                         "and FRUIT_CYCLE_REPORT=1")

    print(f"\nP108 aim census {args.label}".rstrip())
    print("=" * 96)
    print("per attempt (window = the ticks whose axial band overlaps the payload, up to the close)")
    print(f"{'att':>4} {'arm':5s} {'species':11s} {'dia':>5} {'dy_first':>9} {'dy_max':>7} "
          f"{'|dx|':>6} {'clr120':>7} {'hover_z':>8}  placed")
    for t in rows:
        print(
            f"{t['attempt']:>4} {t['arm']:5s} {t['category']:11s} {t['dia_mm']:5.1f} "
            f"{t['dy_first'] * 1000:+9.1f} {t['dy'] * 1000:+7.1f} {t['dx_abs'] * 1000:6.1f} "
            f"{t['clr:cage120 (P107)'] * 1000:+7.1f} {t['z_end'] * 1000:+7.1f}  "
            f"{int(bool(t.get('descent_ok')))}   {t['placed']}"
        )

    clean = [t for t in rows if t.get("descent_ok")]
    print(f"  attempts whose descent executed: {len(clean)} / {len(rows)} "
          f"(the rest stopped {abs(min(t['z_end'] for t in rows)) * 1000:.0f} mm above the equator)")
    dy = [t["dy"] for t in clean]
    dy0 = [t["dy_first"] for t in clean]
    dx = [t["dx_abs"] for t in clean]
    share = [abs(t["dy"]) / max(abs(t["dy"]) + abs(t["dx_abs"]), 1e-9) for t in clean]

    print("\n1. THE ARRIVAL SPLIT  (the payload against the tool axis, in the band)")
    print(f"  n = {len(clean)} attempts with an executed descent")
    for name, v in (
        ("dy at the band's first tick", dy0),
        ("dy max in the window (along-belt)", dy),
        ("|dx| max in the window (lateral)", dx),
    ):
        print(
            f"  {name:36s} p50={pct(v, 50) * 1000:7.1f} p90={pct(v, 90) * 1000:7.1f} "
            f"p95={pct(v, 95) * 1000:7.1f} max={max(v) * 1000:7.1f} mm"
        )
    print(f"  along-belt share of |dy|+|dx|:     p50={pct(share, 50) * 100:5.1f}% "
          f"p90={pct(share, 90) * 100:5.1f}%")
    print("  close-time aim (what P107's 24 mm is *not*):")
    for key, name in (("close_dx", "|dx|"), ("close_dy", "|dy|"), ("close_radial", "radial")):
        v = [t[key] for t in clean if key in t]
        if v:
            print(f"    {name:8s} p50={pct(v, 50) * 1000:6.1f} p95={pct(v, 95) * 1000:6.1f} "
                  f"max={max(v) * 1000:6.1f} mm  (n={len(v)})")

    print("\n2. THE APERTURE NEEDED PER AXIS  (A = 2 (offset + r))")
    rmax = 0.5 * max(t["dia_mm"] for t in clean) / 1000.0
    print(f"  r_max = {rmax * 1000:.1f} mm")
    for q in (50, 90, 95, 100):
        print(
            f"  at p{q:<3d}: along-belt A_y = {2 * (pct(dy, q) + rmax) * 1000:6.1f} mm   "
            f"lateral A_x = {2 * (pct(dx, q) + rmax) * 1000:6.1f} mm"
        )

    print("\n3. CANDIDATE SCREEN  (min pad-to-payload clearance over the window)")
    print(f"  a candidate passes an attempt when its minimum is >= +{MARGIN * 1000:.0f} mm")
    for c in CANDIDATES:
        v = [t[f"clr:{c.name}"] for t in clean]
        ok = sum(1 for x in v if x >= MARGIN)
        print(
            f"  {c.name:16s} ax={c.ax * 2000:4.0f} ay={c.y_half * 2000:4.0f} mm  "
            f"pass={ok:3d}/{len(v):<3d} ({100.0 * ok / len(v):5.1f}%)  "
            f"min={min(v) * 1000:+6.1f} p50={pct(v, 50) * 1000:+6.1f} mm   {c.note}"
        )

    print("\n4. THE NEIGHBOURS AND THE REQUIRED SPACING")
    up = [n for n in nbs if float(n["d"][1]) > 0]
    if not up:
        print("  (no upstream neighbour rows)")
        return 0
    gaps = [float(n["d"][1]) for n in up]
    ndia = [float(n["dia"]) for n in up]
    print(f"  upstream neighbour pairs seen in the window: {len(up)}")
    print(f"  delivered gap: p10={pct(gaps, 10) * 1000:6.1f} p50={pct(gaps, 50) * 1000:6.1f} "
          f"min={min(gaps) * 1000:6.1f} mm;  neighbour dia p50={pct(ndia, 50) * 1000:.1f} mm")
    for c in CANDIDATES:
        need = c.ay_up + PLATE_THICK + pct(ndia, 50) / 2.0 + MARGIN
        fouled = [
            n for n in up
            if float(n["d"][1]) < c.ay_up + PLATE_THICK + float(n["dia"]) / 2.0 + MARGIN
            and abs(float(n["d"][0])) < c.ax + PLATE_THICK + float(n["dia"]) / 2.0 + MARGIN
        ]
        print(
            f"  {c.name:16s} needs gap >= {need * 1000:6.1f} mm   "
            f"fouls {len(fouled):3d}/{len(up):<3d} upstream pairs "
            f"({100.0 * len(fouled) / len(up):5.1f}%)"
        )
    print("\n  delivered gaps below each candidate's requirement (the shipped schedule):")
    for c in CANDIDATES:
        need = c.ay_up + PLATE_THICK + pct(ndia, 50) / 2.0 + MARGIN
        bad = sum(1 for g in gaps if g < need)
        print(f"  {c.name:16s} {bad:3d}/{len(gaps):<3d} below {need * 1000:.0f} mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
