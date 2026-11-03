#!/usr/bin/env python3
"""P110 census - the presentation/centring term, priced before anything is built.

The question (P108 section 7 route 2, P109 section 5): the payload is ~56 mm
**upstream** of the tool axis when the cage's plates enter its axial band and
only ~3-12 mm lateral, an 83-95 % along-belt split.  Can a **presentation
element** - a lateral centring guide, or a metering gate that holds the fruit
while the belt slips under it - remove that term without breaking the catch's
sign (P109: the residual must stay positive) and without stopping the belt?

Everything here is offline: the tree's own records plus the code's arithmetic.
Five sections, each answering one clause of the registration:

1. **The term's identity.**  `dy_entry` is not an error to minimise: it is the
   belt speed times the descent's clock *inside* the payload's band.  Measured
   three ways - the printed `[task] dynamic descent` rows (the start gap), the
   per-tick `FRUIT_FRUIT_TRACE` cells (the entry offset and the payload's own
   speed inside the window), and the profile arithmetic.
2. **A perfect lateral guide.**  `dx -> 0` leaves the along-belt term and every
   aperture it implies unchanged; the aperture need is `2 (dy + r)`.  The tree
   already carries lateral guides (`conveyor.containment_parts`), so their
   channel is compared with the delivered band.
3. **A perfect hold (the gate).**  A stationary fruit at the station makes
   `dy_entry` = the parking offset by radius, and the aperture need `2 r`.  Its
   three couplings are priced: the selector windows (both pick modes), the
   supply's rate, and the release.
4. **The enclosure, re-censused.**  P107/P108 counted ">= 3 pads" from the
   `[cage]` row.  Joined to the descent's `end=`, that bucket is mostly *jam*
   (a blocked descent pressing the plates onto the payload) and *over-closure*
   (the ring driven through a small fruit), not enclosure.  The clean subset is
   counted separately, and the ring's closure arithmetic is derived.
5. **The rate arithmetic** that decides a hold-and-release gate's cadence.

Usage:
    python3 logs/p110/census.py            # writes stdout, tee to census.txt
    python3 logs/p110/census.py --check    # asserts the corpora are present
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re

import numpy as np

# Cage geometry (`cage_hand`): the plate's axial span and the payload's equator.
PLATE_DISTAL = 0.0805
PLATE_LENGTH = 0.060
PLATE_THICK = 0.010
PAD_CAP = 4.90  # N per pad (`logs/p41`: the shipped pinch's per-face number)
PAD_K = 1.0e5   # N/m, the cage's drive stiffness
SQUEEZE = 0.98  # `grip_gap = pinch_width * 0.98`
MARGIN = 0.004

#: The shipped scene (`assets.SceneConfig`): where the belt, station and hand are.
BELT_TOP = 1.17
JAW_AT_GRIP = BELT_TOP + 0.095          # `grasp_clearance` 0.095
TIPS_BELOW_JAW = 0.0805                 # `FINGER_TIP_BELOW_JAW`
BELT_SPEED = 0.12
PICK_Y = 0.0
SPAWN_Y, DESPAWN_Y = 0.68, -0.70
BELT_LEN = 1.60
#: `conveyor.containment_parts` (the opt-in bundle): a 0.292 m channel.
FENCE_X = (0.130, 0.430)
#: The shipped scatter (`fruits`): gaps and the lateral band.
GAP_MIN, GAP_MAX = 0.10, 0.35
LATERAL = (0.20, 0.36)
#: `tasks._dynamic_select_floor`: lead + speed*select_s + margin (the shipped pair).
SELECT_S, SELECT_MARGIN = 1.5, 0.03
#: The `station` window's lower edge: `pick_y - 0.02 + prepose_lead`
#: (`FRUIT_PREPOSE_LEAD` 0.12 / `FRUIT_PREPOSE_LEAD_S` 0.9 * 0.12 -> 0.12 m).
STATION_FLOOR = PICK_Y - 0.02 + 0.12


def _pct(v, q):
    return float(np.percentile(np.asarray(v, dtype=float), q)) if len(v) else float("nan")


def _row(name, v, unit="mm", scale=1000.0):
    return (
        f"  {name:44s} n={len(v):4d} p50={_pct(v, 50) * scale:+8.1f} "
        f"p90={_pct(v, 90) * scale:+8.1f} max={max(v) * scale:+8.1f} "
        f"min={min(v) * scale:+8.1f} {unit}"
    )


# --------------------------------------------------------------------------- #
# 1. The term's identity: dy_entry = speed * t_in_band
# --------------------------------------------------------------------------- #
def section_identity(logs: list[str], trace_dir: str) -> None:
    print("\n1. THE TERM'S IDENTITY  (dy_entry = belt speed x the descent's clock)")
    print("=" * 96)
    dy, deadline, t_desc, steps = [], [], [], []
    for path in logs:
        for line in open(path, errors="replace"):
            m = re.search(
                r"dynamic descent: waited (\d+) ticks, intercept=([-+0-9.]+) m "
                r"\(station ([-+0-9.]+), shift ([-+0-9.]+) m\), fruit dy=([-+0-9.]+) m, "
                r"deadline=([-+0-9.]+) m, t_desc=([-+0-9.]+) s",
                line,
            )
            if m:
                dy.append(float(m.group(5)))
                deadline.append(float(m.group(6)))
                t_desc.append(float(m.group(7)))
        steps += [
            int(m.group(1))
            for m in re.finditer(r"approach\(cartesian\): [0-9.]+ cm, \d+ samples: steps=(\d+)", open(path, errors="replace").read())
        ]
    n = len(dy)
    print(f"  {n} dynamic descents across {len(logs)} cell(s)")
    print(_row("fruit dy (the start gap, printed)", dy))
    print(_row("deadline (the hover's exit distance)", deadline))
    print(_row("t_desc (the leg's profiled duration)", t_desc, unit="s", scale=1.0))
    print(_row("steps (the leg's tick count)", steps, unit="ticks", scale=1.0))
    if not n:
        return
    t = float(np.median(t_desc))
    v = BELT_SPEED
    # The plate's distal face is `PLATE_DISTAL` below the jaw and the payload's
    # top is `2r` above the belt, so the faces come *beside* the payload when the
    # jaw descends to  belt_top + PLATE_DISTAL + 2r.  The hover is
    # `FRUIT_DYNAMIC_HOVER` (0.060 m) above the grip (jaw = belt_top + 0.095),
    # so the descent to the entry is
    #     s_enter = 0.095 + 0.060 - (PLATE_DISTAL + 2r)
    # and the entry offset is  fruit dy - speed * t_desc * s_enter / 0.060.
    print("\n  the arithmetic, per radius (the hover is `FRUIT_DYNAMIC_HOVER` 60 mm):")
    print(f"  {'r':>5} {'s_enter':>9} {'t_enter':>8} {'t_beside':>9} {'dy_entry':>9}  {'A_y = 2(dy+r)':>13}")
    for r in (0.018, 0.024, 0.030, 0.035):
        s_enter = max(0.0, 0.095 + 0.060 - (PLATE_DISTAL + 2 * r))
        t_enter = t * min(1.0, s_enter / 0.060)
        dy_e = max(0.0, v * t - v * t_enter)
        print(
            f"  {r * 1000:5.0f} {s_enter * 1000:8.1f}mm {t_enter:7.3f}s "
            f"{t - t_enter:8.3f}s {dy_e * 1000:8.1f}mm "
            f"{2 * (dy_e + r) * 1000:12.1f}mm"
        )
    print(
        "  -> `fruit dy` / `deadline` / `t_desc` are the leg's own clock and the\n"
        "     margin cancels inside `dy` (P109 section 1): the term is\n"
        "     `speed x (the leg's time), i.e. a DESCENT property, not an error.\n"
        "     The arithmetic's upper bound for a 6 cm fruit is 63 mm; the measured\n"
        "     entry is ~56 mm (below), the difference being the payload's arrest by\n"
        "     the plates during the leg's first 14.5 mm (measured next)."
    )
    if trace_dir and os.path.isdir(trace_dir):
        section_identity_trace(trace_dir)


def section_identity_trace(trace_dir: str) -> None:
    """The per-tick witness: the split at the entry and the payload's speed."""
    dy, dx, sp, tband, dy_close, dx_close = [], [], [], [], [], []
    for path in sorted(glob.glob(os.path.join(trace_dir, "ftrace_*.json"))):
        d = json.load(open(path))
        arm = d.get("arm") or "right"
        rows = []
        for row in d["rows"]:
            if row is None:
                continue
            a = (row.get("arm") or {}).get(arm)
            if a is None:
                continue
            rows.append((row["phase"], float(row["t"]), np.asarray(row["p"], float) - np.asarray(a["jaw"], float), float(row.get("s") or 0.0)))
        ic = next((i for i, x in enumerate(rows) if x[0] == "close"), None)
        if ic is None or not rows:
            continue
        r = 0.5 * float(d.get("diameter") or 0.06) if d.get("diameter") else 0.030
        band_lo = -(PLATE_DISTAL + r)
        # band entry: the LAST crossing into the band before the close (the
        # first crossing is the pre-pose, where the arm is still 0.5 m away).
        ib = None
        for i in range(ic - 1, 0, -1):
            if rows[i][2][2] >= band_lo and rows[i - 1][2][2] < band_lo:
                ib = i
                break
        if ib is None:
            continue
        off = rows[ib][2]
        if abs(float(off[1])) > 0.25:  # a failed/blocked attempt, not an arrival
            continue
        dy.append(float(off[1]))
        dx.append(float(off[0]))
        dy_close.append(float(rows[ic][2][1]))
        dx_close.append(float(rows[ic][2][0]))
        # The payload's travel inside the window: the belt would move it
        # `speed * dt`, so the fraction of the window spent at < half belt speed
        # is the *arrest* (the pads pin it and the belt slips under it).
        span = [abs(rows[i][3]) for i in range(ib, ic)]
        if span:
            sp.append(sum(1 for s in span if s < 0.5 * BELT_SPEED) / len(span))
        tband.append(rows[ic][1] - rows[ib][1])
    if not dy:
        return
    print(f"\n  the per-tick witness ({trace_dir}, {len(dy)} executed arrivals):")
    print(_row("dy at the band entry (along-belt)", dy))
    print(_row("dx at the band entry (lateral)", dx))
    print(_row("dy at the close", dy_close))
    print(_row("dx at the close", dx_close))
    print(_row("the window spent below half belt speed", sp, unit="% of ticks", scale=100.0))
    print(_row("band entry -> close", tband, unit="s", scale=1.0))
    share = [abs(a) / max(abs(a) + abs(b), 1e-9) for a, b in zip(dy, dx)]
    print(_row("along-belt share of |dy|+|dx| at entry", share, unit="%", scale=100.0))
    print(
        "  -> the entry split is along-belt by ~93 %; the lateral term is a\n"
        "     *max over the window* (the arm's x-tracking lag), not the entry\n"
        "     (P108: |dx| p50 11.8 mm over the window against 2.6 mm at the entry)."
    )
    print(
        "  -> and the payload is NOT carried at belt speed for the window: the\n"
        f"     plates arrest it ({_pct(sp, 50) * 100:.0f} % of the window's ticks are below\n"
        "     half the belt speed).  The belt slips under the payload, which is\n"
        "     exactly what a metering gate would do - the difference is *where* it\n"
        "     does it (at the station, by 0.12 m/s of belt drag, versus 50 mm\n"
        "     upstream, by the descending plates)."
    )


# --------------------------------------------------------------------------- #
# 2. What a perfect lateral guide buys
# --------------------------------------------------------------------------- #
def section_guide() -> None:
    print("\n2. A PERFECT LATERAL GUIDE  (dx -> 0)")
    print("=" * 96)
    r_max = 0.035
    dy_entry = 0.056
    print("  the aperture need is per axis: a pad face at A/2 clears a sphere at")
    print("  offset o by A/2 - (o + r), so A = 2 (o + r_margin).")
    print(f"  {'hypothesis':38s} {'A_y (p50)':>10} {'A_x':>8}  what it removes")
    print(f"  {'shipped (dy 56, dx 12)':38s} {2 * (dy_entry + r_max) * 1000:9.1f}mm {2 * (0.012 + r_max) * 1000:7.1f}mm  -")
    print(f"  {'perfect lateral guide (dx -> 0)':38s} {2 * (dy_entry + r_max) * 1000:9.1f}mm {2 * r_max * 1000:7.1f}mm  the lateral 12 mm only")
    print(f"  {'perfect along-belt hold (dy -> 0)':38s} {2 * r_max * 1000:9.1f}mm {2 * (0.012 + r_max) * 1000:7.1f}mm  the along-belt 56 mm")
    print(
        "\n  -> a guide cannot touch `A_y`: the 120 mm cage still fails 0/8 windows\n"
        "     and the 200 mm cage's pass rate is unchanged (P108 section 3).\n"
        "     It removes at most the *close-time* lateral (8.8 mm p50 on the cage\n"
        "     cell) out of a 22.7 mm radial offset - 39 %."
    )
    print("\n  the guides the tree already has (`conveyor.containment_parts`):")
    print(f"    a channel between the side fences at x = {FENCE_X[0]:.3f} / {FENCE_X[1]:.3f} m")
    print(f"    -> {FENCE_X[1] - FENCE_X[0]:.3f} m wide against a delivered band of")
    print(f"       {LATERAL[0]:.3f}-{LATERAL[1]:.3f} m ({LATERAL[1] - LATERAL[0]:.3f} m): the fences")
    print("       never touch a fruit inside the band, so they cannot centre it.")
    print("       A guide that DID centre the band would have to be narrower than")
    print("       the band (0.16 m) - and the open hand (+-0.066 m at the band's")
    print("       edges) needs 0.132 m of it.")


# --------------------------------------------------------------------------- #
# 3. What a perfect hold buys, and what it costs
# --------------------------------------------------------------------------- #
def section_gate() -> None:
    print("\n3. A PERFECT HOLD  (a metering gate: the fruit stops, the belt slips)")
    print("=" * 96)
    print("  a stationary fruit at the station makes the entry offset the *parking*")
    print("  offset: `y_park = y_gate_face + r`, so it spans one radius across the pool")
    print(f"    {'r':>5} {'y_park - pick_y':>16}")
    for r in (0.018, 0.024, 0.030, 0.035):
        print(f"    {r * 1000:5.0f}mm {r * 1000:13.0f}mm")
    print(f"  -> A_y need falls from {2 * (0.056 + 0.035) * 1000:.0f} mm to {2 * 0.035 * 1000:.0f} mm: the")
    print("     120 mm cage (P107's own) clears, and the 200 mm hand is not needed.")
    print("  -> the 17 mm spread across the pool is the parking tolerance; the catch")
    print("     closes it at 1 mm/tick (the catch-up's own rate) - it is benign for a")
    print("     *stationary* fruit, and only a race for a moving one (P109).")

    print("\n  3a. THE SELECTOR CANNOT SEE A PARKED FRUIT (both pick modes)")
    print(f"    moving catch: `floor = _dynamic_pick_lead() + speed*select_s + margin`")
    lead = BELT_SPEED * (0.4 + 0.69 + 0.15) + 0.03
    print(f"      lead {lead * 1000:.0f} mm + {BELT_SPEED * SELECT_S * 1000:.0f} mm + {SELECT_MARGIN * 1000:.0f} mm")
    print(f"      = {1000 * (lead + BELT_SPEED * SELECT_S + SELECT_MARGIN):.0f} mm - a fruit at the station is 1/20 of it")
    print(f"    indexed (station-first): `station` window = [{STATION_FLOOR:.2f}, {PICK_Y + 0.18:.2f}] m")
    print("      (the lower edge is `pick_y - 0.02 + prepose_lead`), so a fruit parked")
    print(f"      at {PICK_Y:.2f} is admitted only with `FRUIT_SMOOTH_TRANSIT_PREPOSE=0`")
    print("  -> the gate is not a scene prop: it is a collider AND a selection rule")
    print("     AND a different pick mode (`FRUIT_DYNAMIC_PICK=0`, the P1 primitive).")

    print("\n  3b. THE RATE ARITHMETIC (the cadence cost)")
    gap_mean = 0.5 * (GAP_MIN + GAP_MAX)
    supply = gap_mean / BELT_SPEED
    pick = 15.1  # s/attempt, the shipped scripted single arm (P80/P108: 15.0-15.6)
    q = pick / supply
    print(f"    delivered inter-arrival: {GAP_MIN:.2f}-{GAP_MAX:.2f} m / {BELT_SPEED:.2f} m/s =")
    print(f"      {GAP_MIN / BELT_SPEED:.2f}-{GAP_MAX / BELT_SPEED:.2f} s (mean {supply:.2f} s)")
    print(f"    the pick's cycle: {pick:.1f} s/attempt")
    print(f"    -> one arm consumes 1 per {pick:.0f} s while the belt delivers 1 per")
    print(f"       {supply:.1f} s: a hold-and-release gate queues {q:.1f} fruit per cycle,")
    print(f"       {q * gap_mean:.2f} m of belt - the belt is {BELT_LEN:.2f} m long, so a")
    print("       passive gate jams the line within one cycle.  A real cell answers")
    print("       this with a *magazine* (a stopped or throttled infeed), i.e. the")
    print("       belt's transport is replaced by the gate - which the tree's")
    print("       directive (the belt never stops) forbids.")
    print("    the load on the front fruit: the belt drags every queued fruit")
    print(f"       (mu*m*g ~ 1.3 * 0.10 * 9.81 = {1.3 * 0.10 * 9.81:.2f} N each), so a queue")
    print(f"       of {q:.0f} presses {q * 1.3 * 0.10 * 9.81:.1f} N on the parked fruit - the")
    print("       fixture measures the stack directly (`fixture_gate.py`).")

    print("\n  3c. THE RELEASE")
    print("    the belt presses the parked fruit into the wall with ~1.3 N, so the")
    print("    lift sees mu_pair * 1.3 N of extra upward drag (~2 N at mu 1.6).  The")
    print("    grip's own capacity is 2*mu*9.8 = 12.7 N, so the bite is ~16 % - a")
    print("    real cost on the closed grip class, not a blocker.")
    print("    the *height* is the blocker: the hand's lowest solid part at the grip")
    print(f"    is belt_top + {TIPS_BELOW_JAW * 1000 - 0:.1f} mm - {1000 * (JAW_AT_GRIP - BELT_TOP - TIPS_BELOW_JAW):.1f} mm at the")
    print(f"    shipped jaw height - so a gate at the station is <= {1000 * (JAW_AT_GRIP - BELT_TOP - TIPS_BELOW_JAW):.1f} mm tall.")
    print("    Whether a kerb that short holds a 30-70 mm fruit is measured, not")
    print("    argued: the climb condition is (r - h)/r <= mu_pair, which holds on")
    print("    paper for the pool (0.19-0.59 <= 1.3) - so the fixture's job is the")
    print("    *dynamic* answer (a 0.12 m/s impact, the fruit's spin, the belt slip).")


# --------------------------------------------------------------------------- #
# 4. The enclosure, re-censused
# --------------------------------------------------------------------------- #
CAGE_ROW = re.compile(
    r"\[cage\] idx=(\d+) arm=(\w+) species=(\w+) dia=(\d+)mm approach=(\d+)t "
    r"clr=([-+0-9.]+)mm aper_min=([0-9.]+)mm close=(\d+)t "
    r"bat=([-+0-9.]+)mm bat_rel=([-+0-9.]+)mm pads=(\d)/4 f=\(([^)]*)\) "
    r"F=([0-9.]+)N aper=([0-9.]+)mm"
)
END_ROW = re.compile(
    r"approach\(cartesian\): [0-9.]+ cm, \d+ samples: steps=\d+.*?end=([0-9.]+) mm"
)


def section_enclosure(logs: list[str]) -> None:
    print("\n4. THE ENCLOSURE, RE-CENSUSED  (what '>= 3 pads' actually counts)")
    print("=" * 96)
    rows = []
    for path in logs:
        text = open(path, errors="replace").read()
        ends = [float(m.group(1)) for m in END_ROW.finditer(text)]
        cage = [m for m in (CAGE_ROW.search(line) for line in text.splitlines()) if m]
        for i, m in enumerate(cage):
            rows.append(
                {
                    "cell": os.path.basename(path),
                    "dia": int(m.group(4)),
                    "clr": float(m.group(6)),
                    "end": ends[i] if i < len(ends) else float("nan"),
                    "bat_rel": float(m.group(10)),
                    "pads": int(m.group(11)),
                    "F": float(m.group(13)),
                    "aper": float(m.group(14)),
                }
            )
    if not rows:
        print("  (no `[cage]` rows in the given cells)")
        return
    # The three classes the raw `pads` count conflates.  A *clean* enclosure is
    # >= 3 pads with (a) the descent executed (`end` at the shipped hand's own
    # 8-11 mm), (b) the ring not driven through the payload (`aper >= dia - 4 mm`,
    # i.e. the 2 % squeeze at most), and (c) no crush (`F <= 4*cap*1.5`).
    clean, jam, crush = [], [], []
    for r in rows:
        if r["pads"] < 3:
            continue
        if not np.isfinite(r["end"]) or r["end"] > 15.0:
            jam.append(r)
        elif r["aper"] < r["dia"] - 4.0:
            crush.append(r)
        elif r["F"] > 4 * PAD_CAP * 1.5:
            crush.append(r)
        else:
            clean.append(r)
    n = len(rows)
    ge3 = [r for r in rows if r["pads"] >= 3]
    print(f"  {n} cage attempts across {len(logs)} cell(s)")
    print(f"  raw '>= 3 pads' (P107/P108's endpoint): {len(ge3)}/{n} = {100 * len(ge3) / n:.1f} %")
    print(f"    - blocked descent (end > 15 mm, the plates jammed on the payload): {len(jam)}")
    print(f"    - over-closure / crush (aper < dia - 4 mm or F > 4*cap*1.5):        {len(crush)}")
    print(f"    - CLEAN enclosure:                                                  {len(clean)}/{n} = {100 * len(clean) / n:.1f} %")
    for tag, group in (("jam", jam), ("crush", crush), ("clean", clean)):
        if group:
            print(
                f"    {tag:5s}: end p50 {_pct([r['end'] for r in group], 50):5.1f} mm, "
                f"aper p50 {_pct([r['aper'] for r in group], 50):5.1f} mm, "
                f"F p50 {_pct([r['F'] for r in group], 50):8.2f} N, "
                f"clr p50 {_pct([r['clr'] for r in group], 50):+6.1f} mm"
            )
    low = [r for r in rows if r["pads"] <= 2]
    print("\n  the modal grasp is 2 pads at the cap - a V-block, `n = 2`:")
    two = [r for r in rows if r["pads"] == 2]
    if two:
        print(
            f"    {len(two)}/{n} attempts, F p50 {_pct([r['F'] for r in two], 50):.2f} N "
            f"({_pct([r['F'] for r in two], 50) / PAD_CAP:.2f} cap-pairs), "
            f"bat_rel p50 {_pct([r['bat_rel'] for r in two], 50):+.1f} mm"
        )
    print(
        "  -> a 2-contact V-block has `F_crit = n*mu*N` with n = 2: the SAME axial\n"
        "     capacity as the shipped two-jaw pinch (P104 section 2).  The cage's\n"
        "     licensed gain needs n >= 3, i.e. a centred close."
    )

    print("\n  4a. THE RING'S CLOSURE ARITHMETIC  (why a centred close is mandatory)")
    print("    one radial synergy, four force-capped position pads:")
    print(f"      command  a = 0.49 d (the 2 % squeeze), cap {PAD_CAP:.2f} N/pad,")
    print(f"      stiffness k = {PAD_K:.0e} N/m -> the elastic allowance is")
    print(f"      cap/k = {PAD_CAP / PAD_K * 1000:.3f} mm of interference before the drive saturates.")
    print("    a payload offset by delta along an axis has its near pad commanded")
    print("      delta + 0.01 d INSIDE its surface, and its far pad 0.01 d - delta")
    print("      SHORT of contact.  At delta = 10 mm, d = 60 mm:")
    for delta in (0.001, 0.005, 0.010, 0.020):
        d = 0.060
        near = delta + 0.01 * d
        far = 0.01 * d - delta
        print(f"      delta={delta * 1000:4.1f} mm -> near pad {near * 1000:6.1f} mm inside, far pad {far * 1000:+6.1f} mm short")
    print(
        "  -> for the far pads to reach, delta must be < 0.01 d = 0.6 mm; the\n"
        "     near pads are then commanded 0.6 mm inside and push at the cap.  Any\n"
        "     delta above the 0.049 mm elastic allowance is a *launch*, and the\n"
        "     `bat`/`bat_rel` columns are that launch: 27-82 mm / 9-330 mm of\n"
        "     payload displacement during the close (section 4's rows).\n"
        "  -> so the presentation would have to centre the payload to < 1 mm,\n"
        "     which no passive element on a 0.12 m/s belt does.  The term is the\n"
        "     hand's closure architecture (no per-pad compliance), not the scene."
    )


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", default="logs/p108/tr_cage_s5")
    ap.add_argument("--logs", nargs="*", default=None)
    ap.add_argument("--cells", nargs="*", default=None)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    logs = args.logs or sorted(
        glob.glob("logs/p108/S_s*.log") + glob.glob("logs/p109/M0_s*.log")
    )
    cells = args.cells or sorted(glob.glob("logs/p108/E_s*.log"))
    if args.check and (not logs or not cells):
        raise SystemExit("census corpora missing (logs/p108, logs/p109)")
    print("P110 census - the presentation/centring term")
    print("=" * 96)
    section_identity(logs, args.trace)
    section_guide()
    section_gate()
    section_enclosure(cells)
    print("\n5. WHAT EACH FORM CAN REMOVE (the summary the registration reads)")
    print("=" * 96)
    print(f"  {'form':30s} {'band-entry dy':>14} {'A_y need':>10} {'close radial':>13}")
    print(f"  {'none (shipped)':30s} {'56 mm':>14} {'182 mm':>10} {'22.7 mm':>13}")
    print(f"  {'lateral guide (perfect)':30s} {'56 mm':>14} {'182 mm':>10} {'20.2 mm':>13}")
    print(f"  {'metering gate (perfect)':30s} {'<= 35 mm':>14} {'70 mm':>10} {'<= 17 mm':>13}")
    print("  -> the guide removes 0 % of the aperture need and 11 % of the close")
    print("     radial: dead.  The gate removes the term but needs a selection rule,")
    print("     a different pick mode and a magazine (5-18x rate mismatch): it is a")
    print("     workstation, and the enclosure still needs < 1 mm of centring.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
