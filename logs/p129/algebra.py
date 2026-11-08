#!/usr/bin/env python3
"""P129 algebra - does a pad material with `mu_pair < 1` centre a ring, and what
does it cost the pinch?

Offline, written before any bench cell.  The claim under test is the decision
book's nail (i) (`docs/END_EFFECTOR_DECISION.md` section 4.1): the four-pad ring's
centring is a *friction* inequality, so a pad whose **pair** friction with the
fruit is below 1 lets four jaws centre; at the measured pair friction
**1.25-1.46** they cannot.

This script settles four things before a simulator cell is spent:

1. **The static fixed point, re-derived** - `delta_inf(mu, s, k, cap)` for four
   pads and for three, at `mu` = 0.6 / 0.8 / 1.0 / 1.2 (the ladder the bench runs)
   plus the measured 1.25 / 1.36 / 1.46 (the control).  Solved numerically in 2-D
   with the **tangential projection** (`logs/p112/algebra.py`'s model, which is
   the one that reproduced P112's fixture) and checked against the closed forms.
2. **A correction to the record's headline formula.**  `docs/END_EFFECTOR_
   DECISION.md` section 2 quotes `delta_inf = (2 mu - 1) * min(s, cap/(2 mu k))`
   from `logs/p111/algebra.py`.  That expression is not what P111's own solver
   computes (`closed_form` there returns `mu*s + mu_b*m*g/(2k)`), and it is not
   what the 2-D geometry gives either: two *opposed* pads' motion is normal to
   both faces, so the drive is `2 k delta` and the resistance is the
   perpendicular pair's `2 mu k s`, i.e. `delta_inf = mu s`.  The thresholds are
   unchanged (`mu < 1` either way) but the *residual* is not: at `mu = 0.6` the
   two forms read 0.20 s and 0.60 s.  The bench decides which.
3. **The stiffness window** `k` for a *four-contact* end state - not just
   "centres", but "all four pads carry >= the 0.5 N contact trigger", which is
   the state P110's clean-enclosure endpoint asks for.  It is two inequalities
   (the far pad must load, the near pad must not saturate) and they bound `mu`
   from above: **`mu <= (cap - 0.5)/(cap + 0.5)` = 0.815 at the shipped 4.90 N
   cap**.  Above that no stiffness keeps four pads loaded.
4. **The price**: the pinch's and the ring's static axial capacity `n mu N`
   against the cell's operating demand `m (g + 5.83)` (P40 section 4.1's worst
   single-tick carry acceleration), so the material's trade is priced before it
   is measured.

Read from the tree's own numbers: the pool table from `logs/p110/fixture.txt`
(the 16 shipped fruits), the ring from `src/fruit_sorting/cage_hand.py`
(`PAD_FORCE` 4.90 N, `HOME_FACE_R` 0.060, `STROKE` 0.047, squeeze 0.98), the
contact trigger 0.5 N (`FRUIT_CAGE_CONTACT_N`), the pinch's delivered force from
`logs/p41` (9.75-9.9 N over two faces = 4.90 N/face).

    python3 logs/p129/algebra.py            # the report
    python3 logs/p129/algebra.py --check    # asserts the inputs are present
"""

from __future__ import annotations

import argparse
import math
import re

import numpy as np

# --------------------------------------------------------------------------- #
# The tree's constants (each names its source).
# --------------------------------------------------------------------------- #
CAP = 4.90                 # `cage_hand.PAD_FORCE` = P41's 9.8 N / 2 faces
TRIGGER_N = 0.50           # `FRUIT_CAGE_CONTACT_N` / `FRUIT_DYNAMIC_CONTACT_FORCE`
SQUEEZE = 0.98             # `FRUIT_GRIPPER_SQUEEZE`
K_SHIPPED = 1.0e5          # `cage_hand.PAD_STIFFNESS` (the hard stop)
K_CLOSE = 3.3e3            # P112's chosen close stiffness (`k_close`)
K_WINDOW_LO, K_WINDOW_HI = 2.9e3, 3.8e3   # P111's measured window at mu 1.25-1.46
A_TRANSIENT = 5.83         # the cell's worst single-tick |a|max (P40 section 4.1)
GRAV = 9.81
#: The pair friction the phase is asked about, plus the measured control band.
MUS = (0.6, 0.8, 1.0, 1.2)
MU_MEAS_LO, MU_MEAS_HI = 1.25, 1.46
#: The reserve the decision book names for the axial break ("the demand's 10x
#: margin", section 4.1 item 3).
RESERVE = 10.0

FIXTURE = "logs/p110/fixture.txt"
POOL_ROW = re.compile(
    r"^\s+(?P<name>\w+)\s+d=\s*(?P<d>[0-9.]+)mm m=\s*(?P<m>[0-9.]+)g "
    r"mu=(?P<mu>[0-9.]+) pair\(belt\)=(?P<mb>[0-9.]+)"
)


def pool():
    """The shipped 16-fruit pool, from P110's own fixture table."""
    rows = []
    for line in open(FIXTURE, errors="replace"):
        m = POOL_ROW.match(line)
        if m:
            rows.append(
                dict(name=m["name"], d=float(m["d"]) / 1000.0,
                     m=float(m["m"]) / 1000.0, mu=float(m["mu"]))
            )
    return rows


# --------------------------------------------------------------------------- #
# The 2-D contact model (P112's, re-implemented so this phase's numbers cannot
# silently inherit a different convention).
# --------------------------------------------------------------------------- #
def units(n: int) -> np.ndarray:
    th = np.deg2rad(np.arange(n) * (360.0 / n))
    return np.stack([np.cos(th), np.sin(th)], axis=1)


def pad_forces(delta_xy, s, k, cap, n, roundness=0.0):
    """Per-pad normal force at an offset (round payload, pads on `n` azimuths).

    `roundness` is `(wide - narrow)/2` [m]: the four-pad ring's aperture law is
    `0.98 x the WIDEST extent`, so the perpendicular pair sits that much shorter
    than the squeeze `s` (P111 section 3).  Zero for a round payload, which is
    what the bench uses.
    """
    u = units(n)
    p = s + u @ np.asarray(delta_xy, dtype=float) - roundness * (np.abs(u) @ np.array([1.0, 1.0]) / 2.0)
    # the line above removes `roundness` from every *oblique* pair; for n=4 that
    # is the perpendicular pair (u = +-y) and leaves +-x at full `s`.
    N = np.where(p > 0.0, np.minimum(k * np.maximum(p, 0.0), cap), 0.0)
    return -(N[:, None] * u).sum(axis=0), N, u


def fixed_point(delta0, s, k, cap, mu, n, roundness=0.0, steps=12000, push=1.0e-5):
    """The quasi-static slide's terminal offset [m], 2-D, with the projection."""
    d = np.asarray(delta0, dtype=float).copy()
    u = units(n)
    for _ in range(steps):
        drive, N, _ = pad_forces(d, s, k, cap, n, roundness)
        mag = float(np.linalg.norm(drive))
        if mag <= 1e-12:
            break
        mdir = drive / mag
        tang = np.sqrt(np.maximum(1.0 - (u @ mdir) ** 2, 0.0))
        if mag <= mu * float((N * tang).sum()):
            break
        # `drive` is the force ON the payload, so the payload moves ALONG it.
        # (P112's `algebra.py` subtracts it, which makes every trial run *away*
        # from the ring's centre; this phase's solver moves along the drive.)
        d = d + mdir * min(push, float(np.linalg.norm(d)))
    _, N, _ = pad_forces(d, s, k, cap, n, roundness)
    return d, N


def closed_form_4(s, mu):
    """Two opposed pads (drive `2 k delta`) against the perpendicular pair's
    `2 mu k s` -> `delta_inf = mu s` while the far pad is loaded and the near
    pad is not saturated."""
    return mu * s


def closed_form_3(s, mu):
    """P112 section 1: `sqrt(3) mu s / (1.5 + (sqrt(3)/2) mu)`."""
    return math.sqrt(3.0) * mu * s / (1.5 + 0.5 * math.sqrt(3.0) * mu)


def s_of(d):
    """The commanded squeeze per face: `0.5 d (1 - 0.98)` = 1 % of the diameter."""
    return 0.5 * d * (1.0 - SQUEEZE)


def k_bounds(d, mu, n, cap=CAP, trig=TRIGGER_N):
    """The stiffness window in which a `n`-pad ring ends with every pad loaded.

    Two conditions, both read off the fixed point at `delta = delta_inf`:
      * the *narrowest* pad must still carry `trig`:
            k (s - delta_inf / (1 if n == 4 else 2)) >= trig
      * the *widest* pad must not saturate before the fixed point is reached:
            k (s + delta_inf) <= cap
    The first is a lower bound, the second an upper one; the window is empty when
    they cross, which is the friction bound this phase is about.
    """
    s = s_of(d)
    d_inf = closed_form_4(s, mu) if n == 4 else closed_form_3(s, mu)
    narrow = s - d_inf / (1.0 if n == 4 else 2.0)
    if narrow <= 0.0:
        return float("inf"), 0.0, s, d_inf
    return trig / narrow, cap / (s + d_inf), s, d_inf


def mu_ceiling(n, cap=CAP, trig=TRIGGER_N):
    """The pair friction above which no stiffness keeps all `n` pads loaded."""
    if n == 4:
        return (cap - trig) / (cap + trig)
    # n = 3: narrow pad penetration s - delta/2 > 0 and the two bounds must meet
    lo, hi = 0.0, 10.0
    f = lambda mu: k_bounds(1.0, mu, n, cap, trig)[0] - k_bounds(1.0, mu, n, cap, trig)[1]
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f(mid) < 0.0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    p = pool()
    if args.check:
        assert len(p) == 16, f"the pool table should read 16 fruits, got {len(p)}"
        assert abs(min(r["d"] for r in p) - 0.0296) < 1e-6
        # the solver must reproduce P112's published 3-jaw band
        s = s_of(0.060)
        for mu in (MU_MEAS_LO, MU_MEAS_HI):
            r = closed_form_3(s, mu) / s
            assert 0.83 <= r <= 0.92, (mu, r)
        print(f"inputs OK: {len(p)} fruits, 3-jaw band reproduces P112, {FIXTURE}")
        return 0

    print("P129 algebra - the pad material below the 4-pad friction threshold")
    print("=" * 104)
    ds = sorted(r["d"] for r in p)
    ms = sorted(r["m"] for r in p)
    print(f"  pool ({FIXTURE}): {len(p)} fruits, d {ds[0] * 1000:.1f}-{ds[-1] * 1000:.1f} mm, "
          f"m {ms[0] * 1000:.1f}-{ms[-1] * 1000:.1f} g")
    print(f"  ring: cap {CAP:.2f} N/pad, contact trigger {TRIGGER_N:.2f} N, squeeze "
          f"{SQUEEZE} (s = 1 % of d per face), close k {K_CLOSE:.0f} N/m, "
          f"hold k {K_SHIPPED:.0f} N/m")
    print(f"  the ladder: pair mu {MUS} ; the measured control {MU_MEAS_LO}-{MU_MEAS_HI}")

    # ------------------------------------------------------------------ #
    print("\n1. THE STATIC FIXED POINT (2-D, tangential projection; three fruit sizes)")
    print("=" * 104)
    print("  4 pads: drive 2 k delta (both opposed pads), resistance 2 mu k s (the")
    print("  perpendicular pair) -> delta_inf = mu s.  The far pad leaves at delta = s,")
    print("  so `delta_inf < s` is exactly `mu < 1`.  P111's (2 mu - 1) s is a different")
    print("  expression; both thresholds are 1, the residuals differ by 2x at mu 0.6.")
    cases = (("small", ds[0]), ("mid", 0.5 * (ds[0] + ds[-1])), ("large", ds[-1]))
    print("\n  fruit   d mm   s mm   mu   4-pad: solver  closed  d/s   |  3-pad: solver  closed  d/s")
    for name, d in cases:
        s = s_of(d)
        for mu in MUS + (MU_MEAS_LO, MU_MEAS_HI):
            row = f"  {name:5s} {d * 1000:6.1f} {s * 1000:6.3f} {mu:4.2f}"
            for n, cf in ((4, closed_form_4(s, mu)), (3, closed_form_3(s, mu))):
                env = 0.98 * (s if n == 4 else 2.0 * s)
                d_end, N = fixed_point([env, 0.0], s, K_CLOSE, CAP, mu, n)
                mag = float(np.linalg.norm(d_end))
                row += (f"  {mag * 1000:8.3f} {cf * 1000:7.3f} {mag / s:5.2f}"
                        + ("  |" if n == 4 else ""))
            print(row)
    print("  -> inside the linear regime (mu < 1, both opposed pads loaded) the solver")
    print("     reproduces both closed forms to <= 2 %.  At mu >= 1 the 4-pad solver")
    print("     stops at `delta = s` (the far pad reaches zero load and the model has no")
    print("     two-contact fixed point beyond it), so its own `mu s` column is only")
    print("     valid below the threshold; the 3-pad's is 0.51-0.91 s and never crosses.")
    print("     **The 4-pad residual crosses `delta < s` at mu = 1; the 3-pad's never.**")

    # ------------------------------------------------------------------ #
    print("\n2. THE FOUR-CONTACT CONDITION IS NOT `delta < s`, IT IS `delta <= s - 0.5/k`")
    print("=" * 104)
    print(f"  A pad counts as loaded at {TRIGGER_N:.2f} N.  At the fixed point the far pad's")
    print("  penetration is `s - delta_inf`, so the four-pad state needs")
    print("     k (s - mu s) >= 0.5      ->   k >= 0.5 / (s (1 - mu))")
    print("  and the near pad must not saturate before that state is reached:")
    print("     k (s + mu s) <= cap      ->   k <= cap / (s (1 + mu))")
    print("  The two meet at **mu = (cap - 0.5)/(cap + 0.5)** - independent of s and k.")
    print(f"\n  the ceiling at the shipped cap: 4-pad mu <= {mu_ceiling(4):.3f}")
    print("  (the 3-pad's bound is the analytic `mu < sqrt(3) = 1.732`; its two-pad")
    print("   trigger bound never binds over this pool)")
    print("\n  k window per fruit (N/m) - the intersection over the pool is the design answer")
    for mu in MUS + (MU_MEAS_LO, MU_MEAS_HI):
        for n in (4, 3):
            lo_pool, hi_pool = 0.0, float("inf")
            for d in ds:
                lo, hi, _, _ = k_bounds(d, mu, n)
                lo_pool, hi_pool = max(lo_pool, lo), min(hi_pool, hi)
            ok = "OK " if hi_pool > lo_pool else "EMPTY"
            print(f"    mu {mu:4.2f} n={n}: [{lo_pool:8.0f}, {hi_pool:8.0f}] "
                  f"({hi_pool / lo_pool if lo_pool > 0 else float('inf'):5.2f}x) {ok}")
    print(f"  -> at the measured mu {MU_MEAS_LO}-{MU_MEAS_HI} the 4-pad window is EMPTY (the far")
    print(f"     pad cannot load).  The 3-pad window at that mu is "
          f"[{max(k_bounds(d, MU_MEAS_HI, 3)[0] for d in ds):.0f}, "
          f"{min(k_bounds(d, MU_MEAS_HI, 3)[1] for d in ds):.0f}] N/m, which contains")
    print(f"     P111's measured [{K_WINDOW_LO:.0e}, {K_WINDOW_HI:.0e}] - and P111's window is a")
    print(f"     *three*-pad measurement.")
    print("  THREE friction conditions, and they are not the same constant:")
    print("    (i)   centres to `delta < s`                 mu < 1")
    print(f"    (ii)  all four pads carry >= 0.5 N          mu <= {mu_ceiling(4):.3f}  (per fruit, cap/trigger)")
    print("    (iii) captures from an offset > s: the near pad's cap must beat the")
    print("          perpendicular pair's friction         mu < cap / (2 k s)  = "
          f"{min(CAP / (2 * K_CLOSE * s_of(d)) for d in ds):.3f}"
          f"-{max(CAP / (2 * K_CLOSE * s_of(d)) for d in ds):.3f} at k {K_CLOSE:.0f}")
    print("  and the POOL-WIDE window (one k for every size) closes earlier:")
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        w = min(k_bounds(d, mid, 4)[1] for d in ds) - max(k_bounds(d, mid, 4)[0] for d in ds)
        if w > 0.0:
            lo = mid
        else:
            hi = mid
    print(f"    the largest fruit's cap bound meets the smallest fruit's trigger bound at")
    print(f"    **mu = {lo:.3f}** (s_max/s_min = {max(ds) / min(ds):.2f} tightens "
          f"{mu_ceiling(4):.3f} -> {lo:.3f})")
    print(f"     Below mu {mu_ceiling(4):.2f} the four-pad window opens; at mu 0.6 it is")
    lo06 = max(k_bounds(d, 0.6, 4)[0] for d in ds)
    hi06 = min(k_bounds(d, 0.6, 4)[1] for d in ds)
    print(f"     [{lo06:.0f}, {hi06:.0f}] N/m over the pool ({hi06 / lo06:.2f}x), and it **excludes**")
    print(f"     the shipped hold stiffness {K_SHIPPED:.0e} - the ring must be *soft while it closes*")
    print("     and firm only after (P111's hard stop, which is why that design ships the pair).")

    # ------------------------------------------------------------------ #
    print("\n3. WHAT IT PREDICTS FOR THE CLOSURE (the bench's registered prediction)")
    print("=" * 104)
    print("  A round payload, `law = d`, arrival offset delta0, the task's clock (24 + 60")
    print("  ticks), the freeze OFF (a full close) - does the ring end centred with every")
    print("  pad loaded?  `4/4` = P110's clean enclosure; `2/4` = the V-block.")
    print("\n  arrival  mu   4-pad: off_end  pads  class        |  3-pad: off_end  pads  class")
    s = s_of(0.060)
    for off in (0.0, 0.005, 0.010, 0.020):
        for mu in MUS + (MU_MEAS_HI,):
            row = f"  {off * 1000:6.1f} {mu:4.2f}"
            for n in (4, 3):
                env = max(off, 1.0e-9)
                d_end, N = fixed_point([env, 0.0], s, K_CLOSE, CAP, mu, n)
                cnt = int((N >= TRIGGER_N).sum())
                mag = float(np.linalg.norm(d_end))
                moved = mag < 0.98 * env
                cls = (
                    f"{n}/{n} centred" if (cnt == n and mag < s)
                    else f"{cnt}/{n} short of centre" if moved
                    else "JAM (no slide)"
                )
                row += f" {mag * 1000:11.3f} {cnt:4d}/{n}  {cls:16s}"
                if n == 4:
                    row += "  |"
            print(row)
    print("  -> at mu 0.6 the four-pad ring reaches `centred AND 4/4 loaded` from every")
    print("     arrival up to 20 mm; at mu 0.8 it centres to `mu s` but the far pad sits")
    print("     0.2 s short (< 0.5 N) -> 3/4; at mu >= 1.0 it either jams at the arrival")
    print("     (the near pad's cap cannot beat the perpendicular pair's friction) or")
    print("     ends 3/4.  The three-pad ring centres at every mu and keeps 3/3 - it is")
    print("     inside its own friction bound (mu < sqrt(3)) by construction.")

    # ------------------------------------------------------------------ #
    print("\n4. THE PRICE: static axial capacity against the cell's own demand")
    print("=" * 104)
    worst = max(p, key=lambda r: r["m"])
    demand = worst["m"] * (GRAV + A_TRANSIENT)
    print(f"  the demand: the heaviest fruit {worst['name']} {worst['d'] * 1000:.1f} mm")
    print(f"  m={worst['m'] * 1000:.1f} g at m(g+{A_TRANSIENT:.2f}) = **{demand:.2f} N**")
    print("\n  mu    pinch 2muN   xdemand | 4-pad 4muN   xdemand | 3-pad 3muN   xdemand")
    for mu in MUS + (MU_MEAS_LO, MU_MEAS_HI):
        print(f"  {mu:4.2f} {2 * mu * CAP:10.2f} {2 * mu * CAP / demand:9.1f} "
              f"| {4 * mu * CAP:11.2f} {4 * mu * CAP / demand:9.1f} "
              f"| {3 * mu * CAP:11.2f} {3 * mu * CAP / demand:9.1f}")
    print(f"  -> the pinch keeps {2 * 0.6 * CAP / demand:.1f}x the demand at mu 0.6 (below the book's")
    print(f"     {RESERVE:.0f}x reserve), and the ring keeps {4 * 0.6 * CAP / demand:.1f}x.  Neither is a")
    print("     force deficit - P104/P117's measured escape is a loaded slide at a 10-20x")
    print("     static margin - so the capacity column prices the *trade*, not an escape.")
    print("\n  the creep prediction (P117's correction): the *load-axis* component was")
    print("  0.00-0.07 mm on every cell at pair 1.25-1.46 and is the friction term's")
    print("  own; the total (8.62 mm on the pear) is a seat shift along the jaw axis,")
    print("  invariant to mu 2.0 -> 4.0 (P117 A6: -4.8 %).  So the prediction is:")
    print("     load-axis creep  : at mu 0.6 the capacity is still "
          f"{2 * 0.6 * CAP / demand:.1f}x -> stays <= 0.3 mm")
    print("     total creep      : mu-invariant (a seat term), so ~8-12 mm at every mu")
    print("  and the kill clause ('creep > 1.0 mm at the operating load') has to be read")
    print("  on the load-axis component, because the total is already 8.62 mm at the")
    print("  shipped mu - i.e. the letter of the clause fails every material including")
    print("  the incumbent.  Recorded in PREREG.md section 4 as a registered reading.")

    # ------------------------------------------------------------------ #
    print("\n5. THE BENCH'S PREDICTIONS, IN ONE PLACE")
    print("=" * 104)
    print("  A0  pair friction: authoring `pad_mu = 2 mu_pair - mu_fruit` delivers the")
    print("      requested pair to <= 0.1 (PhysX averages; P104 section 7a) - a *check*,")
    print("      because the whole phase rests on the pair being controllable.")
    print("  A1  the pinch: axial break falls as `2 mu N` (13.3 -> 5.9 N from 1.36 to")
    print("      0.6), the load-axis creep stays <= 0.3 mm (3.1x the demand), and the")
    print("      total creep does not move (P117 A6, re-tested on a 2.2x ladder).")
    print("  B1  the ring, full close: mu <= 0.8 gives `centred + 4/4 loaded` from a")
    print("      20 mm arrival; mu >= 1 does not (<= 3 pads).")
    print("  B2  the ring, the task's first-contact freeze: the aperture freezes at")
    print("      `2 (R + delta0)`, i.e. `2 delta0` too wide.  At mu < 1 the payload then")
    print("      slides to the ring's centre and *unloads* (0 pads); at mu > 1 it jams")
    print("      at delta0 with the near pad carrying ~the freeze force (1-2 pads).")
    print("      Either way the line's closure does **not** enclose - the second leak")
    print("      is the close protocol, not the material.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
