#!/usr/bin/env python3
"""P111 algebra - does per-pad compliance turn the ring into a self-centring chuck?

Offline.  The owner's hypothesis (P110's item 1): the ring's four pads are
*force-capped position* drives, so a payload offset by `delta` has its near pad
commanded `s + delta` inside its surface and its far pad `s - delta` short of
contact; the far pad therefore reaches only at `delta < s`, the line delivers
6-20 mm, and the closure launches the payload (`bat` 27-82 mm) instead of
pushing it to the centre.  The claim to test: **a compliant pad (low k) yields
`cap/k` of travel instead of 0.049 mm, so the ring absorbs the offset and the
four pads balance at the ring's centre.**

This script settles the static question before any simulator cell is spent:

1. The **static equilibrium** and the **centring condition** - the offset at
   which the four pads' forces balance - for a ladder of stiffnesses and caps.
2. The **predictions** the registration needs: (a) the maximum offset each k can
   centre, (b) the centring force and whether it crushes, (c) the time to centre
   against the ring's own close clock, (d) the bat.
3. The **chosen (k, c, cap, hold)** and the falsifiers.

Everything is read from the tree's own numbers: the pool table from
`logs/p110/fixture.txt` (16 fruits, d/m/mu, `mu_pair(belt)`), the ring from
`cage_hand.py` (4 pads at 4x90 deg, plate 26 x 60 mm, `mu` 2.0, `DISTAL_Z`
80.5 mm, lip 10.5 mm), the close from `tasks.py` (`FRUIT_GRIPPER_SQUEEZE` 0.98
and the live clamp's 0.97, `FRUIT_DYNAMIC_CLOSE_FAST` 24 + `_LOAD` 60 ticks,
`FRUIT_DYNAMIC_CONTACT_FORCE` 0.5 N over 3 ticks, `pinch_width` = the widest
horizontal extent), the measured pad-payload friction from `logs/p104`
(`mu_app` 1.05-1.45) and the measured close-time offset from `logs/p108`
(8.8 mm lateral / 20.2 mm along).

Usage:
    python3 logs/p111/algebra.py              # the report
    python3 logs/p111/algebra.py --check      # asserts the inputs are present
"""

from __future__ import annotations

import argparse
import math
import re

# --------------------------------------------------------------------------- #
# The tree's constants (each names its source).
# --------------------------------------------------------------------------- #
DT = 1.0 / 120.0          # `common.CONTROL_DT` at 120 Hz
PAD_MASS = 0.020          # `cage_hand.PAD_MASS`
PAD_MU = 2.0              # `cage_hand.PAD_MU` (the finger material)
CAP = 4.90                # `cage_hand.PAD_FORCE` = P41's per-face 9.8/2 N
K_SHIPPED = 1.0e5         # `cage_hand.PAD_STIFFNESS`
C_SHIPPED = 100.0         # `cage_hand.PAD_DAMPING`
SQUEEZE = 0.98            # `FRUIT_GRIPPER_SQUEEZE`
LIVE_SQUEEZE = 0.97       # `FRUIT_DYNAMIC_CLOSE_LIVE`
FAST_TICKS = 24           # `FRUIT_DYNAMIC_CLOSE_FAST`
LOAD_TICKS = 60           # `FRUIT_DYNAMIC_CLOSE_LOAD`
TRIGGER_N = 0.5           # `FRUIT_DYNAMIC_CONTACT_FORCE`
TRIGGER_TICKS = 3         # `FRUIT_DYNAMIC_CONTACT_TICKS`
OPEN_GAP = 0.120          # the cage's `open_gap` (`2 * HOME_FACE_R`)
LIP = 0.0105              # `cage_hand.LIP`
BELT_SPEED = 0.12         # the shipped belt
#: The measured pad-payload friction (`logs/p104/RESULTS.md` section 2:
#: `mu_app = F_exit / (n*N)` = 1.05-1.45 on every fixture form).  PhysX combines a
#: pair by averaging, so the *pair* value is `(PAD_MU + fruit_mu)/2`.
MU_APP_LO, MU_APP_HI = 1.05, 1.45
#: P108's close-time aim census (726 traced attempts): 8.8 mm lateral, 20.2 mm
#: along-belt.  The registration uses the smaller (the *lateral* axis) so the
#: prediction cannot be accused of taking the easy axis.
DELTA0 = 0.0088

FIXTURE = "logs/p110/fixture.txt"
POOL_ROW = re.compile(
    r"^\s+(?P<name>\w+)\s+d=\s*(?P<d>[0-9.]+)mm m=\s*(?P<m>[0-9.]+)g "
    r"mu=(?P<mu>[0-9.]+) pair\(belt\)=(?P<mb>[0-9.]+)"
)


def pool():
    """The shipped 16-fruit pool, read from the P110 fixture's own table."""
    rows = []
    for line in open(FIXTURE, errors="replace"):
        m = POOL_ROW.match(line)
        if m:
            rows.append(
                {
                    "name": m["name"],
                    "d": float(m["d"]) / 1000.0,
                    "m": float(m["m"]) / 1000.0,
                    "mu": float(m["mu"]),
                    "mu_pair_belt": float(m["mb"]),
                    "mu_pair_pad": (PAD_MU + float(m["mu"])) / 2.0,
                }
            )
    return rows


# --------------------------------------------------------------------------- #
# The static model
# --------------------------------------------------------------------------- #
def pads(delta, s, k, cap, mu, mu_b, m, roundness=0.0):
    """The four pads' forces at an offset `delta` along one jaw axis.

    `s` is the nominal squeeze per face (`R - a/2`: how far the commanded
    aperture sits inside the payload's *widest* extent); `roundness` is
    `(wide - narrow)/2` in metres, so the perpendicular pair sits that much
    shorter than `s`.

    Penetrations, with the payload offset along the theta=0 axis:
      near (theta = 0)    p = s + delta
      far  (theta = 180)  p = s - delta   (contact only while delta < s)
      perp (theta = 90/270) p = s - roundness

    The payload's motion along `delta` is **normal** to the near/far faces (no
    friction there) and **tangential** to the perpendicular pair, so the Coulomb
    resistance is the perpendicular pair's alone, plus the belt's lateral
    friction `mu_b*m*g`.

    Returns `near`, `far`, `perp` (per-pad forces, `min(k*p, cap)` and 0 below
    contact), `drive` = near - far (the net centring force) and `fric`.
    """
    near = max(0.0, min(k * (s + delta), cap))
    far = max(0.0, min(k * (s - delta), cap))
    perp = max(0.0, min(k * (s - roundness), cap))
    return {
        "near": near,
        "far": far,
        "perp": perp,
        "drive": near - far,
        "fric": 2.0 * mu * perp + mu_b * m * 9.81,
    }


def terminal_offset(d0, s, k, cap, mu, mu_b, m, roundness=0.0, steps=200000):
    """Where the quasi-static push-and-slide stops [m].

    The pads close (the squeeze ramps in as the ring travels) and the payload
    slides while `drive > fric`.  The slide is monotone in `delta` (the drive
    decays, the friction is constant within a regime), so the terminal state is
    the fixed point `drive(delta) = fric(delta)` - found here by marching, which
    also handles the two saturation regimes and the far-pad pickup.

    Returns `(delta_inf, loaded_pads)`, `loaded_pads` being what the `[cage]`
    row counts (a pad is loaded at >= 0.5 N).
    """
    delta = float(d0)
    for i in range(steps):
        si = s * (i + 1) / steps
        st = pads(delta, si, k, cap, mu, mu_b, m, roundness=roundness)
        if st["drive"] <= st["fric"]:
            continue
        # the payload advances toward the centre by a small fraction of the
        # *available* gap (the pads close on it as it moves; a spring's slide is
        # fast compared with the close's 120 Hz clock, so the step is bounded by
        # the gap it has to make up, not by an acceleration)
        gap = max(delta - 0.0, 0.0)
        delta = max(0.0, delta - min(gap, 1.0e-4))
    st = pads(delta, s, k, cap, mu, mu_b, m, roundness=roundness)
    n = (
        int(st["near"] >= TRIGGER_N)
        + int(st["far"] >= TRIGGER_N)
        + 2 * int(st["perp"] >= TRIGGER_N)
    )
    return delta, n


def closed_form(s, k, cap, mu, mu_b, m, d0, roundness=0.0):
    """The same answer analytically, plus the regimes it is valid in.

    Two saturations must be told apart, and P110's arithmetic conflated them:
      * the *near* pad saturates at `cap/k` of penetration (the drive's yield);
      * the *perpendicular pair* saturates at the same `cap/k`, and **that** is
        what sets the friction.
    """
    f_b = mu_b * m * 9.81
    perp_p = s - roundness
    perp_sat = k * perp_p >= cap
    fric = 2.0 * mu * min(k * perp_p, cap) + f_b
    if perp_sat:
        # friction = 2*mu*cap >= cap for mu > 0.5: the drive can never win
        return {
            "delta": d0,
            "fric": fric,
            "perp_sat": True,
            "note": "no slide (perp pair at the cap)",
        }
    # linear perp regime: friction = 2*mu*k*perp_p + f_b (constant in delta)
    # slide while drive > fric; the terminal state is
    #   delta >= s : drive = min(k(s+delta), cap)
    #   delta <  s : drive = 2 k delta
    if fric >= cap:
        return {"delta": d0, "fric": fric, "perp_sat": False,
                "note": "no slide (friction above the cap)"}
    # the last valid branch: the payload stops at the smaller of the two roots
    d_hi = fric / k - s            # from k(s+delta) = fric, valid if >= s
    d_lo = fric / (2.0 * k)        # from 2 k delta = fric, valid if < s
    d_star = d_lo if d_lo < s else d_hi
    return {
        "delta": min(d0, max(d_star, 0.0)),
        "fric": fric,
        "perp_sat": False,
        "note": f"slides to {d_star * 1000:.2f} mm",
    }


# --------------------------------------------------------------------------- #
# The dynamic model (the close's own clock)
# --------------------------------------------------------------------------- #
def min_jerk(a, b, n):
    return [
        a + (b - a) * (10 * (i / n) ** 3 - 15 * (i / n) ** 4 + 6 * (i / n) ** 5)
        for i in range(1, n + 1)
    ]


def simulate(d, m, mu, mu_b, k, c, cap, delta0, roundness_frac=0.10):
    """The close, integrated at 120 Hz: the freeze, the delivered force, the bat.

    A **1-D reduction** along the offset's own axis (the real cell is 2-D), with
    no ring exit: the bat is an order-of-magnitude number and the cells are the
    measurement.  The pads are spring-dashpot drives with a force cap whose faces
    track the commanded aperture; the payload is a disc on the belt.  The close
    freezes on the task's own rule (`>= 0.5 N` sustained 3 ticks).
    """
    R = 0.5 * d
    wide = d * 1.02                 # `wide = max(pinch_width*1.02, d*1.02)`
    live = wide * LIVE_SQUEEZE      # the live clamp `live_extent - interference`
    ramp = min_jerk(OPEN_GAP, wide, FAST_TICKS) + min_jerk(wide, live, LOAD_TICKS)
    roundness = roundness_frac * R
    delta, vel, run, freeze, force, n = float(delta0), 0.0, 0, None, 0.0, 0
    for i, aperture in enumerate(ramp):
        s = R - aperture / 2.0
        ds = ((R - ramp[i - 1] / 2.0) - s) / DT if i else 0.0
        near_p, far_p, perp_p = s + delta, s - delta, s - roundness
        near = min(k * max(near_p, 0.0) + (c * (ds - vel) if near_p > 0 else 0.0), cap)
        far = min(k * max(far_p, 0.0) + (c * (ds + vel) if far_p > 0 else 0.0), cap)
        perp = min(k * max(perp_p, 0.0), cap)
        near, far, perp = max(near, 0.0), max(far, 0.0), max(perp, 0.0)
        net = (near - far) - (2.0 * mu * perp + mu_b * m * 9.81)
        a = net / m if net > 0 else 0.0
        vel = max(0.0, vel + a * DT) if net > 0 else 0.0
        delta = max(0.0, delta - vel * DT)
        force = near
        n = int(near >= TRIGGER_N) + int(far >= TRIGGER_N) + 2 * int(perp >= TRIGGER_N)
        run = run + 1 if sum((near, far, 2 * perp)) >= TRIGGER_N else 0
        if run >= TRIGGER_TICKS:
            freeze = i + 1
            break
    return {
        "force": force,
        "n": n,
        "aperture": ramp[freeze - 1] if freeze else ramp[-1],
        "delta_end": delta,
        "bat": abs(delta0 - delta),
        "ticks": freeze or len(ramp),
        "freeze": freeze is not None,
    }


# --------------------------------------------------------------------------- #
def _tab(rows, header, fmt):
    print(header)
    for r in rows:
        print(fmt.format(*r))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    p = pool()
    if args.check:
        assert len(p) == 16, f"the pool table should read 16 fruits, got {len(p)}"
        assert 1.0 < p[0]["mu_pair_pad"] < 1.5, p[0]
        print(f"inputs OK: {len(p)} fruits, {FIXTURE}")
        return 0

    print("P111 algebra - does per-pad compliance centre the ring?")
    print("=" * 100)
    print(f"  the pool ({FIXTURE}): {len(p)} fruits, "
          f"d {min(r['d'] for r in p) * 1000:.1f}-{max(r['d'] for r in p) * 1000:.1f} mm, "
          f"m {min(r['m'] for r in p) * 1000:.0f}-{max(r['m'] for r in p) * 1000:.0f} g")
    print(f"  pad-payload friction: mu_pair = (2.0 + mu_fruit)/2 = "
          f"{min(r['mu_pair_pad'] for r in p):.2f}-{max(r['mu_pair_pad'] for r in p):.2f} "
          f"(P104 measured mu_app {MU_APP_LO:.2f}-{MU_APP_HI:.2f})")
    print(f"  ring: 4 pads at 4x90 deg, one radial synergy, cap {CAP:.2f} N/pad, "
          f"shipped k {K_SHIPPED:.0e}")
    print(f"  close: {FAST_TICKS} ticks to `wide = 1.02 d`, then {LOAD_TICKS} to the live "
          f"clamp; freeze at {TRIGGER_N} N for {TRIGGER_TICKS} ticks")

    worst = max(p, key=lambda r: r["m"])
    small = min(p, key=lambda r: r["m"])
    s = 0.5 * worst["d"] * (1.0 - SQUEEZE)      # 1 % per face on the widest axis

    # ------------------------------------------------------------------ #
    print("\n1. THE CENTRING CONDITION")
    print("=" * 100)
    print(
        "  Penetrations at an offset `delta` along one jaw axis:\n"
        "    near (0 deg)      p = s + delta\n"
        "    far  (180 deg)    p = s - delta   (contact only while delta < s)\n"
        "    perp (90/270 deg) p = s - roundness\n"
        "  Force = min(k*p, cap).  The payload's motion is NORMAL to the near/far\n"
        "  faces (no friction there) and TANGENTIAL to the perpendicular pair, so\n"
        "    drive  = near - far\n"
        "    fric   = 2*mu*perp + mu_belt*m*g        (the perpendicular pair + belt)\n"
        "  The payload slides while drive > fric and stops where they balance.\n"
        "\n  TWO saturations, and P110's arithmetic conflated them:\n"
        "    (i) the *near* pad saturates at cap/k of penetration - the drive yields;\n"
        "    (ii) the *perpendicular pair* saturates at the same cap/k - and THAT is\n"
        "         what sets the friction.  A low k helps twice: the drive is a spring\n"
        "         (so it does not launch) AND the perpendicular pair is a spring (so\n"
        "         its Coulomb resistance is small).\n"
    )
    print("  the closed form, per regime (s = %.2f mm on a %.0f mm fruit):" %
          (s * 1000, worst["d"] * 1000))
    for mu in (MU_APP_LO, 1.30, MU_APP_HI):
        for k in (K_SHIPPED, 1.0e4, 1.0e3, 5.0e2, 2.0e2, 1.0e2):
            cf = closed_form(s, k, CAP, mu, worst["mu_pair_belt"], worst["m"], DELTA0)
            print(f"    mu={mu:4.2f} k={k:8.0f}: {cf['note']:32s} "
                  f"(fric {cf['fric']:5.2f} N)")
        print()
    print(
        "  -> the STATIC fixed point (given unlimited time) is\n"
        "       delta_inf = (2*mu - 1) * min(s, cap/(2*mu*k))\n"
        "     The first branch (the close finishes before the friction catches the\n"
        "     drive, `cap/(2 mu k) > s`) gives (2mu-1) s = 1.1-1.9 s: a 5-8x centring,\n"
        "     short of the 4-contact threshold `s - 0.5/k` by the residual (2mu-2)s.\n"
        "     The second branch (`cap/(2 mu k) < s`, i.e. k > 2.7e3 on this fruit)\n"
        "     stops the payload EARLY, at (2mu-1)cap/(2 mu k) - and that can be\n"
        "     BELOW s: the stiffness window for a static 4-contact state is\n"
        "       k > (2mu-1) cap/(2 mu s) = 1.7e3 N/m.\n"
        "     **So the static algebra actually favours a middling stiffness, not the\n"
        "     softest one** - and the shipped k = 1e5 has the perpendicular pair at\n"
        "     the cap (2*mu*cap = 12.8 N > cap = 4.9 N), so at that rung nothing\n"
        "     moves at all: the rigid ring grips where it sits (P110's measurement).\n"
        "     The dynamics below decides whether either branch is reachable in the\n"
        "     close's 84 ticks: the launch is the term the static model cannot see."
    )
    print("\n  the same algebra for a THREE-jaw ring (120 deg), for contrast:")
    three = 2.0 * MU_APP_LO / (1.5 + MU_APP_LO)
    print(f"    drive = 1.5 k delta, friction = 2 mu k s -> delta_inf = "
          f"{three:.2f} s  ->  {'CENTRES (delta_inf < s)' if three < 1 else 'JAMS'}\n"
          f"    so a 3-jaw chuck closes the last millimetre at this mu and a 4-jaw\n"
          f"    does not: the count of tangential contacts is the lever, not k.")

    # ------------------------------------------------------------------ #
    print("\n2. THE STIFFNESS LADDER (cap 4.90 N, and the reduced 2.00 N)")
    print("=" * 100)
    print(f"  worst case: {worst['name']} d={worst['d'] * 1000:.1f} mm "
          f"m={worst['m'] * 1000:.0f} g mu_pair={worst['mu_pair_pad']:.2f}; "
          f"arrival delta0 = {DELTA0 * 1000:.1f} mm (P108)")
    rows = []
    for k in (1.0e5, 1.0e4, 5.0e3, 2.0e3, 1.0e3, 5.0e2, 2.0e2, 1.0e2):
        for cap in (CAP, 2.0):
            cf = closed_form(s, k, cap, worst["mu_pair_pad"], worst["mu_pair_belt"],
                             worst["m"], DELTA0)
            c = 2.0 * math.sqrt(k * PAD_MASS)
            dyn = simulate(
                worst["d"], worst["m"], worst["mu_pair_pad"],
                worst["mu_pair_belt"], k, c, cap, DELTA0,
                roundness_frac=0.0,
            )
            F = min(k * s, cap)
            need = TRIGGER_N / k
            rows.append(
                (
                    f"{k:8.0f}",
                    f"{cap:4.2f}",
                    f"{cap / k * 1000:7.2f}",
                    f"{F:6.2f}",
                    f"{cf['delta'] * 1000:7.2f}",
                    f"{dyn['delta_end'] * 1000:7.2f}",
                    f"{dyn['bat'] * 1000:6.2f}",
                    f"{s * 1000:5.2f}",
                    "yes" if dyn["delta_end"] < s - need else "no",
                    f"{dyn['n']}",
                    f"{F:6.2f}",
                )
            )
    _tab(
        rows,
        "\n  k N/m    cap N   cap/k mm  static   dynamic   bat mm   s mm  4-pad  n   F/pad",
        "  {:>8} {:>6} {:>10} {:>8} {:>9} {:>8} {:>6} {:>6} {:>2} {:>7}",
    )
    print(
        "  -> the ladder has a KNEE, not a slope.  Above k* = (cap - mu_b*m*g) /\n"
        "     (2 mu s) ~ 2.2e3 N/m the perpendicular pair is at the cap, the friction\n"
        "     is 2*mu*cap and nothing slides; below it the payload slides to\n"
        "     (2mu-1)s + mu_b*m*g/k, i.e. 1.1-1.9 s.  So compliance converts a\n"
        "     *stuck* payload into a *nearly centred* one, and every rung below the\n"
        "     knee lands within 0.3-0.6 mm of the 4-contact threshold - never on it.\n"
        "  -> the cap column is the ladder's negative control: lowering the cap\n"
        "     lowers the friction (the perp pair leaves its cap) but also lowers the\n"
        "     grip.  With cap 2.0 the knee moves to ~0.9e3, so the caps agree in\n"
        "     *geometry* and differ in *capacity* (the 2-grip column halves)."
    )

    # ------------------------------------------------------------------ #
    print("\n3. THE GEOMETRIC BRANCH: is the perpendicular pair loaded at all?")
    print("=" * 100)
    print(
        "  The aperture is `0.98 x the WIDEST horizontal extent` (the live clamp\n"
        "  0.97), so a fruit whose narrow axis is `2*roundness` smaller leaves the\n"
        "  perpendicular pair short by `roundness - s`:\n"
        "    roundness > s  -> the pair is FREE -> the friction is the belt's alone\n"
        "                      -> the ring centres, and the `[cage]` count is <= 2;\n"
        "    roundness < s  -> the pair is LOADED -> section 1's friction applies\n"
        "                      -> the ring jams at (2mu-1)s, off-centre.\n"
        "  The pool's roundness is 0.02-0.20 d and s is 0.005-0.015 d, so most of\n"
        "  the pool is in the second branch: **the registered `pads >= 3` endpoint\n"
        "  and the centring mechanism are in tension** - a ring that centres on a\n"
        "  round fruit cannot also read 3 pads at this squeeze, and a ring that reads\n"
        "  3-4 pads is one whose perpendicular pair is jammed."
    )
    rows = []
    for rr in (0.005, 0.010, 0.015, 0.05, 0.10, 0.20):
        rp = rr * worst["d"]
        cf = closed_form(s, 1.0e3, CAP, worst["mu_pair_pad"],
                         worst["mu_pair_belt"], worst["m"], DELTA0,
                         roundness=rp)
        st = pads(DELTA0, s, 1.0e3, CAP, worst["mu_pair_pad"],
                  worst["mu_pair_belt"], worst["m"], roundness=rp)
        n = 2 if st["perp"] >= TRIGGER_N else 2
        rows.append(
            (
                f"{rr:5.3f}",
                f"{(s - rp) * 1000:+7.2f}",
                f"{st['perp']:6.2f}",
                f"{st['fric']:6.2f}",
                f"{cf['delta'] * 1000:7.2f}",
                "centres" if rp > s else "jams",
                f"{n}",
            )
        )
    _tab(
        rows,
        "\n  roundness/d  perp pen mm  perp N  friction N  d_inf mm   branch   count",
        "  {:>11} {:>11} {:>7} {:>11} {:>9} {:>9} {:>6}",
    )

    # ------------------------------------------------------------------ #
    print("\n4. THE BAT AND THE DELIVERED FORCE (the close, integrated at 120 Hz)")
    print("=" * 100)
    print(
        "  the shipped close profile + the task's freeze rule, the payload's own\n"
        "  mass, the belt's lateral friction.  `F@frz` is the near pad at the freeze,\n"
        "  `bat` the payload's displacement over the close, `n` the pad count the\n"
        "  `[cage]` row would print.  CAVEAT: a 1-D reduction, no ring exit - the\n"
        "  bat is an order of magnitude, the cells are the measurement\n"
        "  (`off0`/`off` in the `[cage]` row is the phase's own instrument)."
    )
    rows = []
    for k, cap in ((1.0e5, CAP), (5.0e3, CAP), (1.0e3, CAP), (5.0e2, CAP),
                   (2.0e2, CAP), (1.0e3, 2.0), (2.0e2, 2.0)):
        c = 2.0 * math.sqrt(k * PAD_MASS)
        for name, f in (("lychee", small), ("apple", worst)):
            r = simulate(
                f["d"], f["m"], f["mu_pair_pad"], f["mu_pair_belt"], k, c, cap,
                DELTA0,
            )
            rows.append(
                (
                    f"{k:8.0f}",
                    f"{cap:4.2f}",
                    f"{c:7.1f}",
                    f"{name:8s}",
                    f"{r['force']:6.2f}",
                    f"{r['n']}",
                    f"{r['bat'] * 1000:6.2f}",
                    f"{r['delta_end'] * 1000:6.2f}",
                    f"{r['ticks']:4d}",
                    f"{r['aperture'] * 1000:6.1f}",
                )
            )
    _tab(
        rows,
        "\n  k N/m    cap N   c Ns/m   fruit     F@frz  n   bat mm  d_end mm  ticks  aper mm",
        "  {:>8} {:>6} {:>8} {:>8} {:>6} {:>2} {:>8} {:>9} {:>6} {:>8}",
    )
    print(
        "  -> the delivered force falls monotonically with k (4.90 -> 0.08-1.8 N) and\n"
        "     the freeze fires EARLIER (17-18 ticks at k <= 1e3 against 62 at the\n"
        "     shipped drive): the 0.5 N trigger is reached at a smaller penetration,\n"
        "     so a compliant ring is a *gentler and shallower* close.  The depth is\n"
        "     the thing to watch in the cells: `aper` at the freeze."
    )

    # ------------------------------------------------------------------ #
    print("\n5. THE GRIP (what compliance costs the hold)")
    print("=" * 100)
    print(
        "  a compliant pad's delivered force is min(k*s, cap), so a soft ring is a\n"
        "  weaker hand.  The capacity that matters is P104's `n * mu * N`; the\n"
        "  shipped pinch is 2*1.3*9.8 = 12.7 N."
    )
    rows = []
    for k in (1.0e5, 1.0e4, 1.0e3, 5.0e2, 2.0e2, 1.0e2):
        for name, f in (("lychee", small), ("apple", worst)):
            s_f = 0.5 * f["d"] * (1.0 - SQUEEZE)
            F = min(k * s_f, CAP)
            rows.append(
                (
                    f"{k:8.0f}",
                    f"{name:8s}",
                    f"{F:6.2f}",
                    f"{2 * f['mu_pair_pad'] * F:7.2f}",
                    f"{4 * f['mu_pair_pad'] * F:7.2f}",
                    f"{f['d'] * 1000:5.1f}",
                )
            )
    _tab(
        rows,
        "\n  k N/m    fruit     F/pad  2-pad cap N  4-pad cap N   dia mm",
        "  {:>8} {:>8} {:>7} {:>12} {:>12} {:>8}",
    )
    print(
        "  -> at k = 1e3 the ring's own grip is 1.8-3.6 N, i.e. **4-7x weaker than\n"
        "     the shipped pinch** (12.7 N) and 4-3.5x weaker than the rigid ring.\n"
        "     A pure-soft arm therefore cannot answer the *delivered* question: it\n"
        "     would lose placements for a grip reason, not a centring one.  That is\n"
        "     why the registration ships the **hard stop** with the soft close."
    )

    # ------------------------------------------------------------------ #
    print("\n6. PREDICTIONS AND THE CHOSEN POINT")
    print("=" * 100)
    print(
        f"  s = {s * 1000:.2f} mm (1 % per face, a {worst['d'] * 1000:.0f} mm fruit), "
        f"delta0 = {DELTA0 * 1000:.1f} mm\n"
        f"  mu_pair = {worst['mu_pair_pad']:.2f} -> delta_inf = (2mu-1)s = "
        f"{(2 * worst['mu_pair_pad'] - 1) * s * 1000:.2f} mm\n"
        f"  the 4-pad state needs delta < s - 0.5/k = {(s - 0.5 / 1.0e3) * 1000:.2f} mm: "
        f"MISSED by {(2 * worst['mu_pair_pad'] - 2) * s * 1000 + 0.5:.2f} mm"
    )
    print(
        "\n  (a) the maximum offset each k can centre (from any d0 >= the knee):\n"
        "      the *terminal* offset is the bound, not the arrival - so every rung\n"
        "      below the knee centres an arbitrarily large arrival to 1.1-1.9 s.\n"
        "      That is the chuck behaviour, and it is what the cells' `off` measures."
    )
    print("  (b) the centring force, and the crush question:")
    st = pads(DELTA0, s, 1.0e3, CAP, worst["mu_pair_pad"], worst["mu_pair_belt"],
              worst["m"])
    print(f"      at delta = {DELTA0 * 1000:.1f} mm, k = 1e3: drive {st['drive']:.2f} N vs "
          f"friction {st['fric']:.2f} N -> it slides (the rigid ring's {CAP:.2f} N vs\n"
          f"      12.8 N does not).  The force is bounded by the cap by construction;\n"
          f"      a soft pad delivers k*s = {min(1.0e3 * s, CAP):.2f} N at the squeeze,\n"
          f"      i.e. a LIGHTER touch than the shipped 4.90 N - compliance cannot\n"
          f"      crush, it under-grips.")
    print("  (c) the time to centre: the slide is a spring against Coulomb friction,\n"
          "      i.e. a few ticks at the 120 Hz clock (the drive accelerates a 0.1 kg\n"
          "      payload at ~40 m/s^2); the close's 84 ticks are not the binding term\n"
          "      and the cells cannot resolve it.  What they CAN resolve is whether\n"
          "      the offset shrinks at all (`off0 -> off`).")
    print("  (d) the bat, 1-D:")
    for k in (1.0e5, 1.0e3, 2.0e2):
        c = 2.0 * math.sqrt(k * PAD_MASS)
        r = simulate(worst["d"], worst["m"], worst["mu_pair_pad"],
                     worst["mu_pair_belt"], k, c, CAP, DELTA0)
        print(f"      k={k:8.0f} c={c:5.1f} -> F@freeze {r['force']:5.2f} N, n={r['n']}, "
              f"bat {r['bat'] * 1000:5.2f} mm, d_end {r['delta_end'] * 1000:5.2f} mm, "
              f"freeze at {r['aperture'] * 1000:.1f} mm")

    k = 1.0e3
    c = 2.0 * math.sqrt(k * PAD_MASS)
    print("\n  THE CHOSEN POINT (pinned by the registration):")
    print(
        f"    k_close = {k:.0f} N/m  (cap/k = {CAP / k * 1000:.2f} mm, "
        f"{CAP / k / 0.049e-3:.0f}x the shipped 0.049 mm)\n"
        f"    c_close = {c:.1f} Ns/m  (= 2 sqrt(k m), P104's own near-critical pair)\n"
        f"    cap     = {CAP:.2f} N/pad  (NOT lowered: the ladder's geometry is\n"
        f"              cap-free below the knee and a lower cap only lightens the grip)\n"
        f"    k_hold  = {K_SHIPPED:.0f} N/m  (the hard stop: the drive stiffens when the\n"
        f"              close freezes, so the carry keeps the shipped grip - a spring-\n"
        f"              loaded pad bottoms out, which is what a real compliant finger is)"
    )
    print(
        "\n  PREDICTIONS (each is a registered falsifier):\n"
        f"    P1  CENTRING: yes.  `off` falls from ~{DELTA0 * 1000:.1f} mm at the close's\n"
        f"        start to ~{(2 * worst['mu_pair_pad'] - 1) * s * 1000:.1f} mm, "
        f"i.e. the offset shrinks 7-8x.\n"
        "    P2  THE COUNTED ENCLOSURE: no rise.  The residual (2mu-2)s keeps the far\n"
        "        pad below the 0.5 N counting threshold, and the perpendicular pair is\n"
        "        short by the fruit's roundness anyway.  Predicted 0-10 % clean.\n"
        "    P3  THE BAT: falls (the force at the freeze is 0.1-1.8 N against 4.90),\n"
        "        so the no-contact/ejection class improves.\n"
        "    P4  THE PLACED COUNT: no rise.  With the hard stop the grip is the shipped\n"
        "        ring's, so the count is P108's E (16/57 = 28 %).\n"
        "    P5  NO CRUSH: the force is <= the cap by construction.\n"
        "\n  IF P1 holds and P2/P4 do not, the phase's answer is: **compliance is a\n"
        "  real self-centring mechanism, and the ring still cannot close the last\n"
        "  millimetre because mu > 1 at the pads.**  The levers below the ring, in\n"
        "  the order this algebra prices them: a pad material with mu < 1 (then the\n"
        "  4-jaw centres to mu*s < s), a 3-jaw ring (delta_inf = 0.82 s < s), and a\n"
        "  positioning change (P110's 0.6 mm, which no passive element delivers).\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
