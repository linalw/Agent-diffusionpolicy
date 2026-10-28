"""P58 phase 2 (offline): the catchable segment's lever table, from the code.

Every number is `_dynamic_pick_lead()` (tasks.py:6065-6086) +
`_dynamic_select_floor()` (tasks.py:5971-6004) + the scenario constants
(assets.py:236-244, 214-218) evaluated with the shipped values, and the descent
duration from the repo's own jerk-limited profile (`_approach_duration`,
tasks.py:6097-6106). No simulator.

    python3 logs/p58/lever_table.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fruit_sorting.motion import TrajectoryLimits, jerk_limited  # noqa: E402

TICK = 1.0 / 120.0
PICK_Y = 0.0      # assets.py:244
SPAWN_Y = 0.68    # assets.py:236
DESPAWN_Y = -0.70  # assets.py:240
BELT_EDGE = 0.80  # belt_center y 0.0 + belt_size y 1.60/2 (assets.py:201/205)
OVERHEAD = 0.4    # FRUIT_DYNAMIC_OVERHEAD_S (tasks.py:6076)
HOVER = 0.06      # FRUIT_DYNAMIC_HOVER / FRUIT_HOVER (tasks.py:6077)
V_APPROACH = 0.15  # FRUIT_DYNAMIC_APPROACH_VMAX / FRUIT_APPROACH_VMAX (6078)
DESCEND_MARGIN = 0.15  # FRUIT_DYNAMIC_DESCEND_MARGIN (6083)
LEAD_MARGIN = 0.03     # FRUIT_DYNAMIC_LEAD_MARGIN (6080)
SETUP = 1.5            # FRUIT_DYNAMIC_SELECT_S (5998)
SELECT_MARGIN = 0.03   # FRUIT_DYNAMIC_SELECT_MARGIN (6003)
LEAD_CAP = 0.80        # tasks.py:6086


def t_desc(v_app: float = V_APPROACH, hover: float = HOVER) -> tuple[int, float]:
    lim = TrajectoryLimits.from_env(TICK)
    lim.v_max = float(v_app)
    pos, _, _ = jerk_limited(max(float(hover), 1e-3), lim)
    return len(pos), len(pos) * TICK


def lead(v: float, v_app: float = V_APPROACH, margin: float = LEAD_MARGIN) -> float:
    _, td = t_desc(v_app)
    return min(v * (OVERHEAD + td + DESCEND_MARGIN) + margin, LEAD_CAP)


def floor(v: float, setup: float = SETUP, margin: float = SELECT_MARGIN,
          lead_margin: float = LEAD_MARGIN) -> float:
    return lead(v, margin=lead_margin) + v * setup + margin


def segment(v: float, spawn: float = SPAWN_Y, pick: float = PICK_Y, **kw) -> float:
    return spawn - pick - floor(v, **kw)


def row(name: str, v: float, spawn: float = SPAWN_Y, pick: float = PICK_Y,
        **kw) -> str:
    f = floor(v, **kw)
    L = segment(v, spawn, pick, **kw)
    # resident bodies at the design spacings and the resulting duty cycle
    return (f"{name:<42s} v={v:.3f} spawn={spawn:+.3f} pick={pick:+.3f} "
            f"floor={f:.3f} L={L:.4f} T={L / v:.2f}s")


def main() -> None:
    n, td = t_desc()
    out = []
    out.append("P58 phase 2 lever table - every term evaluated from the code, no simulator")
    out.append(f"descent profile for hover {HOVER:.3f} m at v_max {V_APPROACH:.2f}: "
               f"{n} ticks = {td:.4f} s (jerk-limited, TrajectoryLimits.from_env)")
    out.append(f"floor = lead + v*setup + margin, lead = min(v*({OVERHEAD} + {td:.4f} + "
               f"{DESCEND_MARGIN}) + {LEAD_MARGIN}, {LEAD_CAP})")
    out.append("")
    base = row("0 baseline (all shipped)", 0.12)
    out.append(base)
    L0 = segment(0.12)
    out.append("")
    out.append("-- one line per lever/value; dL vs the baseline, and the residence time T = L/v")
    cases = [
        ("A pick_y -0.10 (station downstream, WITH the arm)", dict(pick=-0.10), 0.12),
        ("A' pick_y -0.05", dict(pick=-0.05), 0.12),
        ("B spawn_y 0.72 (belt edge 0.80)", dict(spawn=0.72), 0.12),
        ("B' spawn_y 0.74", dict(spawn=0.74), 0.12),
        ("B'' spawn_y 0.80 (the measured fall-off edge)", dict(spawn=0.80), 0.12),
        ("C belt 0.09 m/s (slower)", {}, 0.09),
        ("C' belt 0.06 m/s (the old P1 feed speed)", {}, 0.06),
        ("C'' belt 0.15 m/s (R3's measured point)", {}, 0.15),
        ("C''' belt 0.18 m/s (R3's starvation point)", {}, 0.18),
    ]
    for name, kw, v in cases:
        s = row(name, v, **kw)
        L = segment(v, **kw)
        out.append(f"{s}  dL={L - L0:+.4f} m  dT={L / v - L0 / 0.12:+.2f} s")
    # setup / margin family at the shipped belt
    for name, kw in (
        ("D setup 1.4 s (R3's inert two-line value)", dict(setup=1.4)),
        ("D' setup 1.0 s (R3's tight probe)", dict(setup=1.0)),
        ("D'' setup 0.0 s (the floor's whole setup term)", dict(setup=0.0)),
        ("E margin 0.02 (lead margin 0.02 too)", dict(margin=0.02, lead_margin=0.02)),
        ("E' margin 0.00", dict(margin=0.0, lead_margin=0.0)),
    ):
        f = floor(0.12, **kw)
        L = segment(0.12, **kw)
        out.append(f"{name:<42s} v=0.120 floor={f:.3f} L={L:.4f} T={L / 0.12:.2f}s"
                   f"  dL={L - L0:+.4f} m")
    # descent duration family
    f0 = []
    for v_app in (0.15, 0.22, 0.30):
        n2, td2 = t_desc(v_app)
        f = lead(0.12, v_app=v_app) + 0.12 * SETUP + SELECT_MARGIN
        L = SPAWN_Y - f
        out.append(f"{'F descent v_max ' + str(v_app):<42s} v=0.120 tdesc={td2:.3f}s "
                   f"floor={f:.3f} L={L:.4f} T={L / 0.12:.2f}s  dL={L - L0:+.4f} m")
        f0.append(v_app)
    out.append("")
    out.append("-- the floor's decomposition at the shipped values")
    l = lead(0.12)
    parts = {
        "overhead v*0.4": 0.12 * OVERHEAD,
        f"descent v*{td:.3f}": 0.12 * td,
        "descend margin v*0.15": 0.12 * DESCEND_MARGIN,
        "lead margin": LEAD_MARGIN,
        "selection setup v*1.5": 0.12 * SETUP,
        "select margin": SELECT_MARGIN,
    }
    for k, val in parts.items():
        out.append(f"   {k:<24s} {val:.4f} m  {100 * val / (l + 0.12 * SETUP + SELECT_MARGIN):.0f}% of the floor")
    out.append(f"   {'floor':<24s} {l:.4f} m   (lead {lead(0.12):.3f} + "
               f"{0.12 * SETUP:.3f} + {SELECT_MARGIN:.3f})")
    out.append("")
    out.append("-- the required release interval (spacing <= L) and the design spacings")
    L = L0
    out.append(f"   required interval <= L/v = {L / 0.12:.3f} s  (spacing <= {L:.3f} m)")
    out.append(f"   patch sheet slice 0.14-0.22 m -> {0.14 / 0.12:.2f}-{0.22 / 0.12:.2f} s"
               f"  (inside: 0.22 < {L:.3f})")
    out.append(f"   scatter gaps 0.10-0.35 m -> {0.10 / 0.12:.2f}-{0.35 / 0.12:.2f} s"
               f"  (the 0.35 end is {0.35 - L:+.3f} m OVER L)")
    out.append(f"   interlock cap 3 over the counted band [0.35, 0.73] = 0.38 m ->"
               f" spacing {0.38 / 3:.3f} m -> {L / (0.38 / 3):.2f} bodies in the segment")
    out.append(f"   a 15 s pick consumes {15 * 0.12:.2f} m of belt; the segment holds"
               f" {L:.2f} m = {L / (15 * 0.12):.2f} pick-consumptions")
    out.append("")
    out.append("-- belt-length limits for the station term")
    out.append(f"   belt spans y = {BELT_EDGE:+.2f} .. {-BELT_EDGE:+.2f} (center 0 +- 0.80);"
               f" spawn_y {SPAWN_Y:.2f} leaves {BELT_EDGE - SPAWN_Y:.3f} m to the upstream edge")
    out.append(f"   pick_y to despawn_y headroom {PICK_Y - -0.70:.2f} m (the station can move"
               f" downstream by at most that before the end-of-line zone)")
    print("\n".join(out))


if __name__ == "__main__":
    main()
