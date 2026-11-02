#!/usr/bin/env python3
"""P104 analytic frame: the critical axial force of each grasp form, offline.

Pure python - no simulator, no USD, no numpy. Every input is either the tree's
own measured number or the fixture's (`logs/p104/fixture.txt`, read by
`p104_report.py`).

    python3 logs/p104/analytic.py > logs/p104/analytic.txt

**Model, stated so it can be refuted** (Coulomb, independent contacts, no peel):

* The payload is held by `n` *point* contacts. Each contact carries a normal
  force `N_c` along its own surface normal and can supply at most `mu * N_c` of
  friction in the tangent plane.
* The seat geometry puts every contact normal **perpendicular to the tool axis**:
  the pads' faces are parallel to the tool axis (`logs/p66/COLLIDER_READ.md`) and
  a pad clamps where the payload's surface is tangent to that face, i.e. at the
  payload's widest ring (`logs/p42/SEAT_CENSUS.md` §0: the pads' midpoint is
  1.4-4.7 mm from the payload's centre, so the grip is at the equator, not on a
  cap). An axial pull is therefore **tangential at every contact**, and the
  critical axial force is pure friction:

      F_crit = n * mu * N_c                                  (tangential mode)

* The mode ignores peel, assumes the contacts stay loaded and independent, and
  assumes the payload is rigid. All three are wrong at the margin - which is why
  the fixture, not this file, decides (`logs/p104/RESULTS.md` §0).
* One geometric case breaks the tangential assumption: a **distal lip**. If a
  surface sits under the payload, the pull is resisted by a *normal* force, so the
  axial degree of freedom is blocked rather than friction-limited:

      F_crit(lip) = min(F_lip, F_jaw)   ->  not a mu-quantity
                                                              (normal mode)

  In the ideal rigid model it is unbounded; in the fixture it is the ramp cap.

**Inputs** (measured, this tree):

  N_c   = 4.90 N   the delivered pinch's per-face force (`logs/p41/P3_RESULTS.md`:
                   9.75-9.9 N total over two faces, at the 10 N/joint drive cap)
  mu    0.45       the motion budget's `mu_eff = FRUIT_MU_SAFETY 0.6 x mu 0.75`
                   - the *conservative* value the tree's cone arithmetic uses
  mu    1.13-1.45  the pair friction **implied by the fixture's break-away**
                   (`mu_app = F_break / (n * N_c)`); consistent with PhysX's
                   default *average* combine of the pad's 2.0 with the fruit's
                   own 0.52-0.81 draw (1.26-1.41), not with the *minimum*.
  m     15.5-110 g the pool's strawberry / pear / orange (`fixture.txt`)
  a     1.0 m/s^2  the shipped lift's `a_max` (`FRUIT_LIFT_AMAX`), 1.089 place

**What the bar is.** `docs/PLATFORM_SURVEY.md` §3.3: a hand must beat the pinch
by **>= 1.5x** in the axial direction, or the hypothesis is dead.
"""

from __future__ import annotations

N_C = 4.90
MU_BUDGET = 0.45
MU_MEASURED = (1.13, 1.45)
MASSES_G = {"strawberry": 15.5, "pear": 83.9, "orange": 110.2}
ACCEL = 1.089
G = 9.81
BAR = 1.5


def f_crit(n: int, mu: float, n_c: float = N_C) -> float:
    return n * mu * n_c


def main() -> int:
    print("P104 analytic critical axial force - Coulomb, independent contacts, no peel")
    print(f"  N_c = {N_C:.2f} N per contact   (measured pinch, P41)")
    print(f"  a   = {ACCEL:.3f} m/s^2           (shipped lift/place cap)")
    print()

    print("== (1) the tangential mode: F_crit = n * mu * N_c ==")
    print()
    head = f"{'form':22s} {'n':>2s} "
    for mu in (MU_BUDGET,) + MU_MEASURED:
        head += f"{'F('+format(mu,'.2f')+')':>9s} {'ratio':>6s} "
    print(head)
    print("-" * len(head))
    for label, n in (
        ("(a) two-pad pinch", 2),
        ("(b) 3-contact tripod", 3),
        ("(c) 4-contact", 4),
    ):
        line = f"{label:22s} {n:2d} "
        for mu in (MU_BUDGET,) + MU_MEASURED:
            f = f_crit(n, mu)
            line += f"{f:9.2f} {n/2.0:6.2f} "
        print(line)
    print()
    print("  ratios are mu-free: 3 contacts = 1.50x, 4 contacts = 2.00x, by arithmetic.")
    print(f"  the {BAR:.1f}x bar is therefore cleared by (b) exactly at its letter and by (c)")
    print("  with a 0.5x margin - in *this* model, for *any* mu.")
    print()

    print("== (2) the normal mode: a distal lip ==")
    print()
    print("  (d) two-pad pinch + distal ledge: the pull is carried by a contact")
    print("      normal anti-parallel to it, so the axial capacity is the lip's own")
    print("      strength (or the jaw's), not mu * N. Ideal ratio: unbounded.")
    print()

    print("== (3) the load the cell actually applies, beside those capacities ==")
    print()
    print(f"{'fruit':12s} {'m[g]':>6s} {'m(g+a)[N]':>10s} {'pinch F_crit[N]':>16s} {'capacity/demand':>16s}")
    for fruit, mass_g in MASSES_G.items():
        demand = mass_g / 1000.0 * (G + ACCEL)
        cap = f_crit(2, MU_BUDGET)
        print(f"{fruit:12s} {mass_g:6.1f} {demand:10.3f} {cap:16.2f} {cap/demand:15.1f}x")
    print()
    print("  The measured pinch is 11.0-14.2 N (fixture), i.e. 10-20x the demand, and")
    print("  the cell still loses the payload - so the *static axial capacity* is not")
    print("  the binding term. That is what the fixture's creep column is for.")
    print()

    print("== (4) the predicted ratio vs the measured (fixture, mean of 3) ==")
    print()
    measured = {
        ("tripod", "pear"): 1.62, ("tripod", "orange"): 1.45, ("tripod", "strawberry"): 1.51,
        ("quad", "pear"): 1.95, ("quad", "orange"): 2.04, ("quad", "strawberry"): 1.99,
    }
    print(f"{'form':10s} {'fruit':12s} {'predicted':>10s} {'measured':>9s} {'delta':>7s}")
    for (form, fruit), value in measured.items():
        pred = 1.5 if form == "tripod" else 2.0
        print(f"{form:10s} {fruit:12s} {pred:10.2f} {value:9.2f} {value-pred:+7.2f}")
    print()
    print("  read: the arithmetic's rank and magnitude hold within 10 %; the 3-contact")
    print("  shortfall on the orange (-0.05) and the 4-contact excess on the orange")
    print("  (+0.04) are the lobed-fruit seat, not a different mechanism.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
