#!/usr/bin/env python3
"""P112 algebra - does a **three-jaw** ring centre where the four-jaw cannot?

Offline, written before any build (the phase's step 1).  P111 measured that the
four-pad ring is a **two-pad V-block** at every stiffness: the aperture is
`0.98 x` the payload's *widest* extent, so the perpendicular pair never loads,
and the two loaded pads are *opposed* - the payload's motion is **normal** to
both faces, neither carries friction, and the ring grips where it sits.  Its
algebra's own next step is the **count of tangential contacts**: with three pads
at 120 deg every pad's normal is oblique to the radial offset direction, so every
pad carries both a *restoring* component and a *tangential* (friction) one.

This script is the phase's static + dynamic model, and neither part is a re-quote
of P111's closed forms (those dropped the tangential projection; see section 2).

1. **The contact set.** A ring of `n` pads at face radius `a/2`, payload radius
   `R`, offset `delta` along `phi`: penetration `p_k = s + delta cos(theta_k-phi)`
   with `s = R - a/2` the squeeze.  A 4-jaw's far pad leaves at `delta = s`; a
   3-jaw keeps all three to `delta = 2s` (its minimum penetration is `s-delta/2`).
2. **The static fixed point** (the kill's number).  Drive `D = -sum N_k u_k`,
   Coulomb resistance along the motion `m = D/|D|`,
   `F_res = mu sum N_k sqrt(1-(m.u_k)^2) + mu_b m g`.  The `sqrt(1-(m.u_k)^2)`
   factor is the **tangential projection**.  `delta_inf = 0.84-0.91 s` for the
   3-jaw and `1.00-1.46 s` for the 4-jaw at the measured `mu` 1.25-1.46, so the
   3-jaw is inside the `delta < s` condition and the 4-jaw is outside it.
3. **The cap branch**: `N_k = min(k p_k, cap)` saturates the *near* pad first,
   which removes drive but not friction and pushes the fixed point outward.  That
   makes `k` a **window**, and the window over the whole pool is the design
   output (`k_close`).
4. **The dynamic close**: the aperture ramps at the task's own clock (24 + 60
   ticks, min-jerk) while the payload is free on the table, so the model
   *captures* or *bats* it - the class P107/P108 measured.  This is the
   fixture's protocol, and its predictions are section 5.
5. **The kill**: `delta_inf >= s` at the measured `mu` -> stop before building.

    python3 logs/p112/algebra.py            # the report
    python3 logs/p112/algebra.py --check    # the inputs are present
"""

from __future__ import annotations

import argparse
import math
import re

import numpy as np

# --------------------------------------------------------------------------- #
# The tree's constants (each names its source).
# --------------------------------------------------------------------------- #
DT = 1.0 / 120.0          # `common.CONTROL_DT`
PAD_MASS = 0.020          # `cage_hand.PAD_MASS`
PAD_MU = 2.0              # `cage_hand.PAD_MU` (the shipped finger material)
CAP = 4.90                # `cage_hand.PAD_FORCE` = P41's 9.8 N over two faces / 2
SQUEEZE = 0.98            # `FRUIT_GRIPPER_SQUEEZE`
TRIGGER_N = 0.5           # `FRUIT_DYNAMIC_CONTACT_FORCE` = `FRUIT_CAGE_CONTACT_N`
MIN_FACE_R = 0.013        # `cage_hand.MIN_FACE_R`
HOME_FACE_R = 0.060       # `cage_hand.HOME_FACE_R`
LIP = 0.0105              # `cage_hand.LIP`
FAST_TICKS = 24           # `FRUIT_DYNAMIC_CLOSE_FAST`
LOAD_TICKS = 60           # `FRUIT_DYNAMIC_CLOSE_LOAD`
#: The measured pad-payload friction: P104's `mu_app` 1.05-1.45; PhysX combines a
#: pair by averaging, so `(PAD_MU + mu_fruit)/2` = 1.25-1.46.
MU_LO, MU_HI = 1.25, 1.46
#: P111's measured close-time offset (`[cage] off0`, p50, in-ring rows) and
#: P108's *aim* offset (the number P111's registration first used).
OFF_MEASURED = 0.0030
OFF_AIM = 0.0088

FIXTURE = "logs/p110/fixture.txt"
POOL_ROW = re.compile(
    r"^\s+(?P<name>\w+)\s+d=\s*(?P<d>[0-9.]+)mm m=\s*(?P<m>[0-9.]+)g "
    r"mu=(?P<mu>[0-9.]+) pair\(belt\)=(?P<mb>[0-9.]+)"
)


def pool():
    """The shipped 16-fruit pool, from P110's own fixture table."""
    rows = []
    try:
        text = open(FIXTURE, errors="replace").read().splitlines()
    except OSError:
        return rows
    for line in text:
        m = POOL_ROW.match(line)
        if m:
            rows.append(
                dict(
                    name=m["name"],
                    d=float(m["d"]) / 1000.0,
                    m=float(m["m"]) / 1000.0,
                    mu=float(m["mu"]),
                    mu_pair_belt=float(m["mb"]),
                    mu_pair_pad=(PAD_MU + float(m["mu"])) / 2.0,
                )
            )
    return rows


# --------------------------------------------------------------------------- #
def units(n: int) -> np.ndarray:
    th = np.deg2rad(np.arange(n) * (360.0 / n))
    return np.stack([np.cos(th), np.sin(th)], axis=1)


def pad_forces(delta_xy, s, k, cap, n):
    """Per-pad normal forces at an offset (2-D, round-in-plan payload)."""
    u = units(n)
    p = s + u @ np.asarray(delta_xy, dtype=float)
    N = np.where(p > 0.0, np.minimum(k * np.maximum(p, 0.0), cap), 0.0)
    return -(N[:, None] * u).sum(axis=0), N, u


def fixed_point(delta0, s, k, cap, mu, mu_b, m, n, steps=3000, push=1.0e-5):
    """Integrate the quasi-static slide to rest from `delta0` (2-vector).

    Only meaningful **inside** the capture envelope (`|delta0| < (n-2)/2 * 2s`,
    i.e. `delta < 2s` for three pads): outside it one pad pushes and there is
    nothing to push back, which is the dynamic section's bat.
    """
    d = np.asarray(delta0, dtype=float).copy()
    belt = mu_b * m * 9.81
    u = units(n)
    for _ in range(steps):
        drive, N, _ = pad_forces(d, s, k, cap, n)
        mag = float(np.linalg.norm(drive))
        if mag <= 1e-12:
            break
        mdir = drive / mag
        tang = np.sqrt(np.maximum(1.0 - (u @ mdir) ** 2, 0.0))
        if mag <= mu * float((N * tang).sum()) + belt:
            break
        d = d - mdir * min(push, float(np.linalg.norm(d)))
        if float(np.linalg.norm(d)) < 1e-8:
            return np.zeros(2), int((N >= TRIGGER_N).sum())
    _, N, _ = pad_forces(d, s, k, cap, n)
    return d, int((N >= TRIGGER_N).sum())


def min_jerk(a: float, b: float, n: int) -> list[float]:
    return [
        a + (b - a) * (10 * (i / n) ** 3 - 15 * (i / n) ** 4 + 6 * (i / n) ** 5)
        for i in range(1, n + 1)
    ]


def close(delta0, d_fruit, mass, mu, mu_b, k, cap, n, freeze=True, cont=0.5, n_cont=3):
    """The dynamic close: the aperture ramps while the payload is free.

    The task's own clock: `open -> 1.02*ext` over `FAST_TICKS`, then
    `-> 0.98*ext` over `LOAD_TICKS`.  The payload is a point mass on the table
    (no rotation, no deformation), with the pads' force-capped springs and
    Coulomb friction at the sliding contacts plus the table's.

    `freeze=True` applies the **task's own close rule**: the depth is frozen the
    moment any pad carries `cont` N for `n_cont` ticks, and the pads hold *that*
    aperture (which is what the carry then holds).  With an arrival offset this
    fires on the FIRST touch, i.e. before the ring is inside the fruit's widest
    extent - the protocol question the fixture separates.

    Returns the terminal offset, the pad count, the bat and whether it was
    captured (`|d| < s_end` with every pad >= 0.5 N).
    """
    ext = float(d_fruit)
    wide, deep = ext * 1.02, ext * SQUEEZE
    ramp = min_jerk(2.0 * HOME_FACE_R, wide, FAST_TICKS) + min_jerk(wide, deep, LOAD_TICKS)
    d = np.asarray(delta0, dtype=float).copy()
    v = np.zeros(2)
    u = units(n)
    belt = mu_b * mass * 9.81
    prev = d.copy()
    # Stiffness 3.5e3 N/m on a 30-120 g payload is a 170-340 rad/s oscillator, so
    # the 120 Hz control tick must be **sub-stepped**: explicit Euler at 8.3 ms
    # is unstable by a factor of ~2 (measured: a symmetric payload at delta = 0
    # drifted 9 mm on round-off, `logs/p112/METHOD.md` section 1).
    sub = 240
    h = DT / sub
    run = 0
    froze = False
    for a in ramp:
        s = 0.5 * ext - 0.5 * a
        for _ in range(sub):
            drive, N, _ = pad_forces(d, s, k, cap, n)
            speed = float(np.linalg.norm(v))
            fric = np.zeros(2)
            if speed > 1e-5:
                mdir = v / speed
                for kk in range(n):
                    if N[kk] <= 0.0:
                        continue
                    t = mdir - float(mdir @ u[kk]) * u[kk]
                    tn = float(np.linalg.norm(t))
                    if tn > 1e-9:
                        fric -= mu * N[kk] * (t / tn)
                fric -= belt * mdir
            f = drive + fric
            v = v + (f / mass) * h
            d = d + v * h
        if freeze:
            run = run + 1 if float(N.max()) >= cont else 0
            if run >= n_cont:
                froze = True
                break
    s_end = 0.5 * ext - 0.5 * ramp[-1]
    _, N_end, _ = pad_forces(d, s_end, k, cap, n)
    captured = bool(
        float(np.linalg.norm(d)) < s_end and int((N_end >= TRIGGER_N).sum()) == n
    )
    out = dict(
        froze=froze,
        freezer=float(np.linalg.norm(d)),
        delta=float(np.linalg.norm(d)),
        directed=np.asarray(d, dtype=float),
        bat=float(np.linalg.norm(np.asarray(d) - np.asarray(delta0))),
        pads=int((N_end >= TRIGGER_N).sum()),
        captured=captured,
        s_end=s_end,
        f_end=float(N_end.max()),
        f_mid=float(N.max()) if freeze else 0.0,
    )
    return out


def closed_form_3(s, mu):
    """3-jaw, all loaded, linear: drive `1.5 k delta`, friction `mu k sqrt(3)(s-delta/2)`."""
    return math.sqrt(3.0) * mu * s / (1.5 + 0.5 * math.sqrt(3.0) * mu)


def closed_form_4(s, mu):
    """4-jaw, same solver: two opposed pads carry no friction, the perp pair all of
    it -> `2 k delta = 2 mu k s`, i.e. `delta_inf = mu s`."""
    return mu * s


def k_window(d, mu, mu_b, m):
    """The stiffness window in which the 3-jaw centres AND the narrow pads count."""
    s = 0.5 * d * (1.0 - SQUEEZE)
    d_inf = closed_form_3(s, mu)
    p_narrow = s - 0.5 * d_inf
    k_lo = TRIGGER_N / p_narrow if p_narrow > 0 else float("inf")
    k_hi = CAP / (s + d_inf)
    return k_lo, k_hi, s, d_inf


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    p = pool()
    if args.check:
        assert len(p) == 16, f"the pool table should read 16 fruits, got {len(p)}"
        assert min(r["d"] for r in p) < 0.032 and max(r["d"] for r in p) > 0.066
        print(f"inputs OK: {len(p)} fruits from {FIXTURE}")
        return 0

    def say(line=""):
        print(line)

    ds = sorted(r["d"] for r in p)
    d_small, d_big = ds[0], ds[-1]
    big = max(p, key=lambda r: r["d"])
    worst = max(p, key=lambda r: r["m"])
    mid_d = 0.5 * (d_small + d_big)
    mid_m = 0.5 * (worst["m"] + min(r["m"] for r in p))
    mu_b = worst["mu_pair_belt"]
    cases = (("small", d_small, mid_m), ("mid", mid_d, mid_m), ("large", d_big, worst["m"]))

    say("P112 algebra - does a three-jaw ring centre where the four-jaw cannot?")
    say("=" * 106)
    say(f"  pool ({FIXTURE}): {len(p)} fruits, d {d_small * 1000:.1f}-{d_big * 1000:.1f} mm, "
        f"m {min(r['m'] for r in p) * 1000:.0f}-{max(r['m'] for r in p) * 1000:.0f} g")
    say(f"  pad-payload friction mu_pair = (2.0 + mu_fruit)/2 = "
        f"{min(r['mu_pair_pad'] for r in p):.2f}-{max(r['mu_pair_pad'] for r in p):.2f}")
    say(f"  ring: 3 pads at 3x120 deg, ONE scalar aperture, cap {CAP:.2f} N/pad, "
        f"plate 20 x 60 mm, lip {LIP * 1000:.1f} mm, aperture "
        f"{2 * HOME_FACE_R * 1000:.0f} -> {2 * MIN_FACE_R * 1000:.0f} mm")
    say(f"  squeeze s = 0.01 d per face (FRUIT_GRIPPER_SQUEEZE {SQUEEZE}); "
        f"close clock {FAST_TICKS}+{LOAD_TICKS} ticks, min-jerk")

    # ------------------------------------------------------------------ #
    say("\n1. THE CONTACT SET: three pads hold to 2s, four lose the far pad at s")
    say("=" * 106)
    say("  offset `delta` toward pad 0, penetration p_k = s + delta cos(theta_k):\n"
        "    4 pads (0/90/180/270): p = s+d, s, s-d, s     -> the 180 pad leaves at d = s\n"
        "    3 pads (0/120/240)   : p = s+d, s-d/2, s-d/2 -> all three hold to d = 2s\n"
        "  Every loaded 3-jaw pad has an oblique normal, i.e. a tangential (friction)\n"
        "  component AND a restoring component; two opposed 4-jaw pads have neither.")
    s_big = 0.5 * d_big * (1.0 - SQUEEZE)
    for n in (4, 3):
        d = 1.5 * s_big
        _, N, _ = pad_forces([d, 0.0], s_big, 3300.0, CAP, n)
        say(f"    n={n} at delta={d * 1000:.2f} mm ({d / s_big:.1f} s): pads loaded "
            f"{int((N >= TRIGGER_N).sum())}/{n}")

    # ------------------------------------------------------------------ #
    say("\n2. THE STATIC FIXED POINT (the kill's number)")
    say("=" * 106)
    say("  drive D = -sum N_k u_k; resistance along m = D/|D| is\n"
        "    mu * sum_k N_k * sqrt(1-(m.u_k)^2) + mu_b*m*g\n"
        "  The sqrt term is the **tangential projection**, and it is the term P111's\n"
        "  closed forms dropped.  `delta_inf/s < 1` = the payload reaches the ring's\n"
        "  own squeeze circle (the `delta < s` condition of the 4-contact state).")
    say("\n  fruit   d mm   mu   pads   s mm  d_inf mm  d_inf/s  FORMULA   note")
    for name, d, m in cases:
        s = 0.5 * d * (1.0 - SQUEEZE)
        for mu in (MU_LO, MU_HI):
            for n in (4, 3):
                inside = 0.9 * (2.0 * s if n == 3 else 1.0 * s)
                d_end, cnt = fixed_point([inside, 0.0], s, 3300.0, CAP, mu, mu_b, m, n)
                cf = closed_form_3(s, mu) if n == 3 else closed_form_4(s, mu)
                say(f"  {name:5s} {d * 1000:6.1f} {mu:4.2f} {n:5d} {s * 1000:6.2f}"
                    f" {np.linalg.norm(d_end) * 1000:9.2f} {np.linalg.norm(d_end) / s:8.2f}"
                    f" {cf * 1000:7.2f}mm  {'CENTRES' if np.linalg.norm(d_end) < s else 'jams'}")
    say("\n  -> 3-jaw **0.84-0.91 s** (model 0.83-0.91), 4-jaw **1.00-1.46 s** (model\n"
        "     1.25-1.46 at the three sizes; P111's (2mu-1)s = 1.25-1.50 is the same\n"
        "     algebra without the projection).  The thresholds are **mu < sqrt(3) =\n"
        "     1.73** for three jaws and **mu < 1** for four, and the measured pair\n"
        "     friction (1.25-1.46) sits *between* them - which is the phase's whole\n"
        "     premise, now with its size: the 3-jaw is 16-28 % inside its own bound,\n"
        "     not the 3-4x P111's paragraph implied.")

    # ------------------------------------------------------------------ #
    say("\n3. THE CAP BRANCH: k is a WINDOW, not a slope")
    say("=" * 106)
    say("  `N_k = min(k p_k, cap)` saturates the *near* pad (p = s + delta) first:\n"
        "  drive falls, friction does not, the fixed point moves OUTWARD.  Two bounds:\n"
        "    k >= 0.5 N / (s - delta_inf/2)   the two narrow pads must COUNT (0.5 N)\n"
        "    k <= cap / (s + delta_inf)        the wide pad must not saturate early")
    say("\n  d mm   mu    s mm   k_lo N/m  k_hi N/m   window")
    for name, d, m in cases:
        for mu in (MU_LO, MU_HI):
            k_lo, k_hi, s, d_inf = k_window(d, mu, mu_b, m)
            say(f"  {d * 1000:5.1f} {mu:4.2f} {s * 1000:6.2f} {k_lo:9.0f} {k_hi:9.0f}"
                f"   {k_hi / k_lo:6.2f}x")
    k_lo_pool, k_hi_pool = 0.0, float("inf")
    for r in p:
        for mu in (MU_LO, MU_HI):
            k_lo, k_hi, _, _ = k_window(r["d"], mu, r["mu_pair_belt"], r["m"])
            k_lo_pool, k_hi_pool = max(k_lo_pool, k_lo), min(k_hi_pool, k_hi)
    k_mid = math.sqrt(k_lo_pool * k_hi_pool)
    say(f"\n  THE WINDOW OVER THE WHOLE POOL AT THE WORST mu: "
        f"k in [{k_lo_pool:.0f}, {k_hi_pool:.0f}] N/m ({k_hi_pool / k_lo_pool:.2f}x)")
    say(f"  THE CHOSEN POINT: k_close = **{k_mid:.0f} N/m** (the window's geometric mean), "
        f"c = {2 * math.sqrt(k_mid * PAD_MASS):.1f} Ns/m (= 2 sqrt(k m))")
    say(f"  hold k = 1e5 N/m (P111's hard stop) -> {3 * CAP:.2f} N over three pads; "
        f"P104's licensed axial capacity `n mu N` = {3 * 1.3 * CAP:.1f} N against the\n"
        f"  shipped pinch's 12.7 N = **1.5x**, and 4 pads would read "
        f"{4 * 1.3 * CAP:.1f} N (the 2.0x the survey priced).")

    # ------------------------------------------------------------------ #
    say("\n4. THE DYNAMIC CLOSE: capture is the binding term, and it is the bat")
    say("=" * 106)
    say("  the aperture ramps at the task's clock while the payload is free on the\n"
        "  table; the pads are force-capped springs, the contacts and the table are\n"
        "  Coulomb, the payload is a point mass (no rotation, no deformation).\n"
        "  `captured` = it ends inside the squeeze circle with all three pads >= 0.5 N.")
    say("\n  arrival  3-jaw: off mm  bat mm  pads  captured  |  4-jaw: off mm  bat mm  pads  captured")
    for off in (0.0, 0.002, 0.005, 0.010, 0.020):
        line = f"  {off * 1000:6.1f} mm  "
        for n in (3, 4):
            r = close([off, 0.0], mid_d, mid_m, MU_HI, mu_b, k_mid, CAP, n)
            line += (f"{r['delta'] * 1000:9.2f} {r['bat'] * 1000:7.2f} {r['pads']:5d}"
                     f"    {'yes' if r['captured'] else 'NO ':3s}")
            if n == 3:
                line += "  |"
        say(line)
    say("\n  the freeze is the protocol's own binding term: the depth is frozen at the")
    say("  FIRST touch (0.5 N for 3 ticks), which with an arrival offset happens")
    say("  BEFORE the ring is inside the fruit's widest extent - so the pads hold an")
    say("  aperture that is `2*|delta0|` too wide and the carry starts at ~0 N")
    say("  (P111 measured exactly that: the cage arms' `force_min` median 0.00 N).")
    say("  Scan, mid fruit, mu 1.46, k = the chosen point, the task's freeze ON:")
    say("\n  off mm   3-jaw: off mm  pads  class      |  4-jaw: off mm  pads  class")
    for off in (0.0, 0.001, 0.002, 0.003, 0.005, 0.008, 0.010, 0.015, 0.020):
        line = f"  {off * 1000:6.2f}  "
        for n in (3, 4):
            r = close([off, 0.0], mid_d, mid_m, MU_HI, mu_b, k_mid, CAP, n)
            d = r["delta"]
            cls = ("centred" if r["captured"] else
                   "wedged" if d < 0.006 else "batted out")
            line += f"{d * 1000:10.2f} {r['pads']:5d}  {cls:9s}"
            if n == 3:
                line += "  |"
        say(line)
    say(
        "\n  -> with the shipped freeze, neither ring captures an arrival beyond a few\n"
        "     tenths of a millimetre: the freeze converts the arrival offset into a\n"
        "     **held aperture error** of `2*delta0`, which is the cage family's\n"
        "     ejection/zero-force class (P107/P108/P111), and it is the same defect\n"
        "     for three pads and four.  The fixture therefore runs **both** protocols\n"
        "     (freeze / full close): the centring question needs the full close, and\n"
        "     the delivered question needs the freeze."
    )

    # ------------------------------------------------------------------ #
    say("\n5. THE KILL: is delta_inf >= s at the measured mu?")
    say("=" * 106)
    worst_ratio = 0.0
    for r in p:
        for mu in (MU_LO, MU_HI):
            s = 0.5 * r["d"] * (1.0 - SQUEEZE)
            worst_ratio = max(worst_ratio, closed_form_3(s, mu) / s)
    say(f"  worst delta_inf/s over the pool and mu 1.25-1.46 = **{worst_ratio:.3f}**")
    say(f"  -> the kill **{'FIRES' if worst_ratio >= 1 else 'DOES NOT FIRE'}**.  The 3-jaw\n"
        f"     centres by the algebra, so the build and the fixture are owed.")

    # ------------------------------------------------------------------ #
    say("\n6. WHAT THE `[cage]` INSTRUMENT SHOULD READ (off0 -> off)")
    say("=" * 106)
    say(f"  P111's measured close-time offset {OFF_MEASURED * 1000:.1f} mm (p50, in-ring),\n"
        f"  P108's aim {OFF_AIM * 1000:.1f} mm.  Same instrument (`off0` at the close's\n"
        f"  start, `off` at its flush), same protocol.")
    say("\n  fruit   d mm   mu   off0 mm   off mm   off-off0 mm   pads@flush")
    for name, d, m in cases:
        for mu in (MU_LO, MU_HI):
            for off0 in (OFF_MEASURED, OFF_AIM):
                r = close([off0, 0.0], d, m, mu, mu_b, k_mid, CAP, 3)
                say(f"  {name:5s} {d * 1000:6.1f} {mu:4.2f} {off0 * 1000:8.2f}"
                    f" {r['delta'] * 1000:8.2f} {(r['delta'] - off0) * 1000:12.2f}"
                    f" {r['pads']:11d}")
    say("\n  -> predicted `off - off0` = **-0.3 to -2.4 mm** on the 3 mm arrival and\n"
        "     **-3.2 to -6.4 mm** on P108's 8.8 mm aim, with the pad count 3 at the\n"
        "     flush on the captured rows.  P111's four-jaw measured **+0.2 to\n"
        "     +2.0 mm** on the same instrument, so the forms are separated by the\n"
        "     **sign** of the change, not by a rate.")

    # ------------------------------------------------------------------ #
    say("\n7. PREDICTIONS (registered as F1-F5 in logs/p112/PREREG.md)")
    say("=" * 106)
    say(
        "  P1 CENTRING: median `off - off0` **negative** on the in-ring rows\n"
        "     (-0.3..-6.4 mm predicted), against P111's +0.2..+2.0 mm for four pads.\n"
        "  P2 ENCLOSURE: the clean 3-pad count (P110's jam/over-closure split) rises\n"
        "     above the cage family's 3-5 % (P111: 3/76 rigid at best).\n"
        "  P3 THE COUNT: placed rises above the rigid 4-pad ring's 25.0 % (19/76).\n"
        "  P4 NO CRUSH: `sep@loss - dia >= -15 mm` on every leg.\n"
        "  P5 LANDING + BUDGETS: reported, never re-tuned (AGENTS section 2).\n"
    )
    say("  HARDWARE PRICE (registered before the build): a 3-jaw ring is a\n"
        "  **different geometry** - three pads at 120 deg on one radial synergy.  The\n"
        "  four-pad cage bolts to the flange through one adapter plate; a 3-jaw needs\n"
        "  its own plate, three radial guides and a scroll disc (or three links from\n"
        "  one linear actuator) to drive all three from one scalar.  The pads are\n"
        "  20 x 60 mm blocks (width <= the 26 mm aperture, length <= the palm's\n"
        "  20.5 mm stand-off) in POM or 6082; the cost is the single-scalar\n"
        "  mechanism, not the pads.  A one-off machined assembly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
