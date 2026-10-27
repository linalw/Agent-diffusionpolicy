#!/usr/bin/env python3
"""P45 phase 1 - the mass census, offline.

Reads no stage and imports no `pxr`: every number is either the shipped table in
`src/fruit_sorting/meshes.py` (copied here, with the site cited), the mass
formula at `fruits.py:977`, or a measured reading from a committed log named in
the print. Run:

    python3 logs/p45/mass_census.py --write     # ~0.1 s

Sections: (A) the shipped mass table, (B) the real-mass table under
`FRUIT_PHYSICS_REAL_MASS=1`, (C) the inertia the physics uses, (D) the slip
ratio at 1x/0.5x/0.25x, (E) the fling `v = J/m`, (F) the implied density and
the hollow-shell wall, (G) the measured anchors, (H) the knob register.
"""

from __future__ import annotations

import argparse
import math
import sys

# --------------------------------------------------------------------------- #
# The shipped table (meshes.py:261-310, FRUIT_SHAPES) and the dimension table
# (assets.py:439-456, SceneConfig.fruit_dimensions). Copied, with sites.
# --------------------------------------------------------------------------- #
#: name -> (diameter lo, diameter hi) [m], assets.py:447-455
DIMENSIONS = {
    "strawberry": (0.030, 0.045),
    "lychee": (0.028, 0.038),
    "kiwi": (0.050, 0.068),
    "tomato": (0.050, 0.068),
    "apple": (0.062, 0.070),
    "orange": (0.060, 0.070),
    "peach": (0.058, 0.070),
    "pear": (0.058, 0.070),
}

#: name -> (shipped density, real density, friction lo, friction hi) [kg/m^3, -]
#: `density` and `friction` are the shipped `FruitShape` fields; `density_real`
#: is the P12-A value only read when `physics_real_mass()` is on
#: (meshes.py:399-410).
SHAPES = {
    "strawberry": (700.0, 950.0, 0.55, 0.85),
    "lychee": (850.0, 1000.0, 0.55, 0.85),
    "kiwi": (900.0, 1050.0, 0.75, 1.05),
    "tomato": (780.0, 960.0, 0.50, 0.75),
    "apple": (850.0, 840.0, 0.45, 0.70),
    "orange": (900.0, 1000.0, 0.70, 1.00),
    "peach": (820.0, 1000.0, 0.55, 0.85),
    "pear": (880.0, 950.0, 0.45, 0.70),
}

#: fruits.py:977 - the shipped mass formula (the 0.82 is the "sphere-shape
#: discount", unchanged by P12-A: `fruits.py:974-977`).
SPHERE_SHAPE = 0.82

G = 9.81

#: The shipped grip, P41: the finger drive k=1e5 / c=2000 delivers 9.75-9.9 N
#: (`control.py:218-236`, `logs/p41/P2_RESULTS.md`). The P40 arithmetic used the
#: pre-P41 4.42 N pinch; both are carried because every margin number in the
#: record is quoted against one of the two.
PINCH_P41 = 9.85  # N, midpoint of 9.75-9.90
PINCH_P40 = 4.42  # N, the pre-P41 delivered pinch


def mass(diameter: float, density: float) -> float:
    """The shipped mass [kg] - `fruits.py:977` verbatim."""
    return density * (4.0 / 3.0) * math.pi * (diameter / 2.0) ** 3 * SPHERE_SHAPE


def volume(diameter: float) -> float:
    """The bounding-sphere volume [m^3] (no 0.82 discount)."""
    return (4.0 / 3.0) * math.pi * (diameter / 2.0) ** 3


def section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def table_a() -> None:
    section("A. The shipped mass table (density x 4/3 pi r^3 x 0.82, fruits.py:977)")
    print(f"{'class':<11}{'d lo':>6}{'d hi':>7}{'rho':>7}"
          f"{'m@lo':>9}{'m@mid':>9}{'m@hi':>9}{'2x m@mid':>10}   mu range")
    print(f"{'':11}{'cm':>6}{'cm':>7}{'kg/m3':>7}{'g':>9}{'g':>9}{'g':>9}{'g':>10}")
    lo_all, hi_all = 1e9, 0.0
    for name, (lo, hi) in DIMENSIONS.items():
        rho, _rho_real, mu_lo, mu_hi = SHAPES[name]
        m_lo, m_mid, m_hi = (mass(d, rho) for d in (lo, (lo + hi) / 2.0, hi))
        lo_all, hi_all = min(lo_all, m_lo), max(hi_all, m_hi)
        print(f"{name:<11}{lo*100:>6.1f}{hi*100:>7.1f}{rho:>7.0f}"
              f"{m_lo*1e3:>9.1f}{m_mid*1e3:>9.1f}{m_hi*1e3:>9.1f}"
              f"{2*m_mid*1e3:>10.1f}   {mu_lo:.2f}-{mu_hi:.2f}")
    print(f"\n  pool range (16 fruit, 2 of each class, sizes drawn uniformly): "
          f"{lo_all*1e3:.1f} g .. {hi_all*1e3:.1f} g")
    print("  The P45 sketch's '~20-200 g' is WRONG at both ends (8.0 / 132.5 g).")
    print("  The P40 arithmetic's 0.106 kg is right - it is the orange at its mid")
    print("  diameter (logs/p40/GRIP_CENSUS.md 4.1).")


def table_b() -> None:
    section("B. The real-mass table (FRUIT_PHYSICS_REAL_MASS=1, meshes.py:399-410)")
    print(f"{'class':<11}{'rho ship':>9}{'rho real':>9}{'m@mid ship':>12}"
          f"{'m@mid real':>12}{'delta':>8}")
    lo_all, hi_all = 1e9, 0.0
    for name, (lo, hi) in DIMENSIONS.items():
        rho, rho_real, _mu_lo, _mu_hi = SHAPES[name]
        mid = (lo + hi) / 2.0
        ms, mr = mass(mid, rho), mass(mid, rho_real)
        lo_all, hi_all = min(lo_all, mass(lo, rho_real)), max(hi_all, mass(hi, rho_real))
        print(f"{name:<11}{rho:>9.0f}{rho_real:>9.0f}{ms*1e3:>12.1f}"
              f"{mr*1e3:>12.1f}{(mr/ms-1)*100:>+7.1f}%")
    print(f"\n  real-mass pool range: {lo_all*1e3:.1f} g .. {hi_all*1e3:.1f} g")
    print("  The formula, the 0.82 discount and every diameter are unchanged -")
    print("  only the per-class density switches. The knob is read ONCE at import")
    print("  (meshes.py:355-358), so it cannot change mid-run.")


def table_c() -> None:
    section("C. The inertia the physics actually uses")
    print("  No `physics:diagonalInertia` is authored anywhere on a fruit:")
    print("    fruits.py:980-981  UsdPhysics.MassAPI.Apply(prim)")
    print("                       .CreateMassAttr().Set(mass)      <- mass ONLY")
    print("    fruits.py:1063     the same line on the rescale path")
    print("  (grep: the only `physics:diagonalInertia` in the tree is on the")
    print("   openarm links, assets/openarm_flat/openarm_flat_deinst.usda:4166 et al.)")
    print("  -> PhysX computes the tensor from the *collider's* volume at the")
    print("     authored mass, i.e. a uniform-density solid hull. For a sphere")
    print("     that is I = 2/5 m R^2 on all three diagonal entries.")
    print()
    print(f"{'class':<11}{'d mid':>7}{'m':>9}{'R':>8}{'I = 2/5 m R^2':>16}"
          f"{'I/m':>11}")
    print(f"{'':11}{'cm':>7}{'g':>9}{'mm':>8}{'kg m^2':>16}{'m^2':>11}")
    for name, (lo, hi) in DIMENSIONS.items():
        rho = SHAPES[name][0]
        mid = (lo + hi) / 2.0
        m = mass(mid, rho)
        r = mid / 2.0
        inertia = 0.4 * m * r * r
        print(f"{name:<11}{mid*100:>7.1f}{m*1e3:>9.1f}{r*1e3:>8.1f}"
              f"{inertia:>16.3e}{inertia/m:>11.3e}")
    print()
    print("  Consequence for the design: because I is derived from the mass, a")
    print("  `mass *= s` knob scales the inertia by exactly s for free. There is")
    print("  no second attribute to keep in sync - 'mass + inertia' is one line.")


def ratio(m_kg: float, accel: float, mu: float, pinch: float,
          g_share: float = 1.0) -> float:
    """r = m |a - g| / (mu N); `accel` is the |a| added to gravity.

    `g_share` is the share of g that the FRICTION must carry (1.0 = P40's
    conservative scalar sum; ~0.54 = the measured pad-axis tilt's tangential
    share, section D).
    """
    return m_kg * (g_share * G + accel) / (mu * pinch)


def table_d() -> None:
    section("D. The slip ratio r = m|a+g| / (mu N) - does a lighter fruit change it?")
    print("  N is GRIP-SET, not weight-set. Verified in the code:")
    print("    * the shipped dynamic grip's force comes from the finger drive's")
    print("      position target: k=1e5, c=2000 N s/m, c/k=0.02, Fsat 10 N/joint")
    print("      (control.py:218-236) against a close depth from the GEOMETRY")
    print("      (`pinch_width * 0.98`, tasks.py:9768-9771);")
    print("    * the hold servo's reference is the MEASURED tactile median capped")
    print("      at `FRUIT_DYNAMIC_FORCE_REF_MAX = 4.0 N` (tasks.py:2705-2710),")
    print("      not m*g;")
    print("    * the only two mass sites in the control path are the INDEXED /")
    print("      policy close budget `clip(m*g*100, 25, 60) N` and")
    print("      `clip(m*g*60, 20, 40) N` (tasks.py:11003, 11029; grasp.py:223) -")
    print("      not reached by the shipped dynamic line.")
    print()
    print("  The closing axis is NOT vertical: the release traces' pad-centre")
    print("  separation reads |dz|/|axis| = 0.60-0.96 (p50 0.84, n=11 holding")
    print("  traces, logs/p44/p2/amend_F_{C,S2}.log), so the payload's weight has")
    print("  an along-axis share 0.6-1.0 m g. That share is carried by a pad-to-pad")
    print("  ASYMMETRY (N1 - N2), not by more total normal force: one side gains")
    print("  what the other loses, so N1 + N2 = the drive's own preload. On the")
    print("  heaviest fruit it is 0.62-1.03 N against the 9.85 N grip (6-10 %),")
    print("  i.e. it cannot unload a pad by itself - the measured single-sided")
    print("  onsets are a SEATING property (logs/p9 section 3.1), which agrees.")
    print("  => the friction supply `mu*N` is a CONSTANT in m, so r is")
    print("     proportional to m.")
    print("     The P45 sketch's 'mass-independent if N is grip-set' is backwards:")
    print("     mass-independence is the WEIGHT-set case (N = m g / mu), i.e. the")
    print("     textbook version, which is not this cell. Halving the mass halves r.")
    print()
    worst = max(((name, mass((lo + hi) / 2.0, SHAPES[name][0]), SHAPES[name][2])
                 for name, (lo, hi) in DIMENSIONS.items()),
                key=lambda t: t[1] / t[2])
    name, m, mu_lo = worst
    print(f"  worst class = {name}: m = {m*1e3:.1f} g, mu_lo = {mu_lo:.2f}")
    print(f"  pinch N = {PINCH_P41:.2f} N (P41 shipped) / {PINCH_P40:.2f} N (P40 record)")
    for accel, why in ((1.0, "the commanded lift cap (a_max 1.0)"),
                       (5.83, "the measured worst single-tick transient (P40)"),
                       (1.089, "the commanded place cap (a_max 1.089)")):
        print(f"\n  |a| = {accel:>5.2f} m/s^2   ({why})")
        print(f"    {'scale':>6}{'m [g]':>9}{'demand [N]':>12}"
              f"{'r @N=9.85':>12}{'r @N=4.42':>12}{'1/r @9.85':>11}")
        for s in (1.0, 0.5, 0.25):
            demand = m * s * (G + accel)
            r41 = ratio(m * s, accel, mu_lo, PINCH_P41)
            r40 = ratio(m * s, accel, mu_lo, PINCH_P40)
            print(f"    {s:>6.2f}{m*s*1e3:>9.1f}{demand:>12.3f}"
                  f"{r41:>12.3f}{r40:>12.3f}{1.0/r41:>11.2f}x")
    print("\n  VECTOR note: |a - g| for a horizontal transient is sqrt(a^2+g^2), not")
    print("  a+g. At 5.83 m/s^2 that is 11.41 m/s^2 (r 0.270 at 1x) against P40's")
    print("  scalar-sum 15.64 (r 0.370). P40's number is the upper bound;")
    print("  the tangential form (g_share 0.54, from the measured pad axis) reads")
    print(f"  r = {ratio(m, 5.83, mu_lo, PINCH_P41, 0.54):.3f} at 1x. Every form gives the")
    print("  same 2x / 4x scaling - only the intercept moves.")
    print("\n  What the record says about whether that improvement is worth anything:")
    print("  `logs/p9/FRICTION_AUDIT.md` measures the real ratio per leg - escapes")
    print("  0.10-0.78 of the available friction on 29/31 legs (median 0.36), HELD")
    print("  legs median 0.37, i.e. the ratio does not separate the classes. A 0.25x")
    print("  mass moves a quantity that is already non-discriminative.")


def table_e() -> None:
    section("E. The fling v = J/m - the same impulse, a lighter fruit")
    print("  Anchor: `logs/473_probe_final.log` trial 16 - a 2.8 cm lychee released")
    print("  by the fast SYMMETRIC relax at peak |v| = 1.335 m/s; the SHIPPED")
    print("  asymmetric relax on the same pool/offsets (`logs/474_probe_asym.log`,")
    print("  trial 16) reads 0.695 m/s, and that run's max 0.748 m/s is the")
    print("  <= 0.75 m/s convention.")
    print()
    d_lychee, rho_lychee = 0.028, SHAPES["lychee"][0]
    m_lychee = mass(d_lychee, rho_lychee)
    v_sym = 1.335
    impulse = m_lychee * v_sym
    print(f"  the 2.8 cm lychee: m = {m_lychee*1e3:.2f} g at rho {rho_lychee:.0f}")
    print(f"  the impulse that produced 1.335 m/s: J = {impulse*1e3:.2f} mN s")
    print()
    print(f"    {'scale':>6}{'m [g]':>9}{'v same J':>11}{'vs 0.75':>10}"
          f"{'same J on a 6.6cm apple':>26}")
    m_apple = mass(0.066, SHAPES["apple"][0])
    for s in (1.0, 0.5, 0.25):
        m = m_lychee * s
        v = impulse / m
        print(f"    {s:>6.2f}{m*1e3:>9.2f}{v:>11.2f}{v/0.75:>9.1f}x"
              f"{impulse/m_apple:>23.3f} m/s")
    print()
    print(f"  the same J = {impulse*1e3:.1f} mN s is {impulse/m_apple*1e3:.1f} mm/s on a")
    print(f"  6.6 cm apple ({m_apple*1e3:.1f} g): the ejection speed is a pure 1/m")
    print("  statement about the SAME contact state, which is why the light fruit")
    print("  is the one that flies. 0.5x doubles it, 0.25x quadruples it.")
    print()
    print("  A second, independent 1/m channel: at grip-set N the friction force")
    print("  mu*N is fixed, so the roll-out angular acceleration")
    print("  alpha = tau/I = mu*N*R / ((2/5) m R^2) = 2.5*mu*N/(m*R) scales as 1/m.")
    m_apple_mid = mass((0.062 + 0.070) / 2.0, SHAPES["apple"][0])
    alpha = 2.5 * 0.45 * PINCH_P41 / (m_apple_mid * 0.033)
    print(f"  For the 6.6 cm apple that is {alpha/1e3:.1f}e3 rad/s^2 at 1x and 2x/4x")
    print("  that at 0.5x/0.25x - the walk, if it is the rotational mode, gets")
    print("  FASTER as the mass falls. The two channels point opposite ways.")


def table_e2() -> None:
    section("E2. The contact / rolling term - does mass enter the geometric walk?")
    print("  The walk's own geometry carries NO mass term. All four sites are pure")
    print("  length algebra:")
    print("    * `pinch_width(sample, quat)` = the mesh's extent along the closing")
    print("      axis (`axis_extent`, tasks.py:12529-12546) - a shape profile, no")
    print("      mass;")
    print("    * the close depth `pinch_width * 0.98` (tasks.py:9768-9771);")
    print("    * the carry's commanded span and the pads' local-width shrink: the")
    print("      condition is that the fruit's projected width between the faces")
    print("      falls as the hand advances - kinematics of the two rigid bodies;")
    print("    * the release relax target `pinch_width + PAD_THICK + margin`")
    print("      (tasks.py:12151-12172) - geometry plus a 6 mm margin.")
    print("  `grep 'sample.mass' src/fruit_sorting/tasks.py` finds only the two")
    print("  INDEXED close budgets (11003, 11029). Nothing in the dynamic carry,")
    print("  the servo, or the release reads a mass.")
    print()
    print("  So the walk is a kinematic/contact-state path, and the mass enters it")
    print("  only through the two 1/m channels already computed:")
    print("    (i)  the friction FORCE is mu*N (grip-set), so the roll-out angular")
    print("         acceleration is 2.5*mu*N/(m R) - worse as m falls;")
    print("    (ii) a depenetration kick is an impulse, so its speed is J/m - worse")
    print("         as m falls (section E).")
    print("  What a lighter fruit DOES improve is the translational force margin r")
    print("  (section D) - the exact quantity `logs/p9` measures as")
    print("  non-discriminative (0.36 escapes vs 0.37 held).")
    print()
    print("  Prediction the PREREG can state and falsify: a mass scale should move")
    print("  NOTHING in the timing (the profiles are tick-clocked by caps, not by")
    print("  inertia: logs/p44/CAP_CENSUS.md rule 1) and nothing in the walk; only")
    print("  the fling and any force-limited leg can move. If a 0.25x arm changes")
    print("  the `[cycle]` block times, the mass is leaking into a path this")
    print("  census did not find.")


def table_f() -> None:
    section("F. What a 0.25x mass implies physically (fixed size)")
    print("  Two equivalent readings of the same number: the DESIGN density rho")
    print("  (what `fruit_density` returns) and the SOLID-EQUIVALENT density")
    print("  m/V_sphere (what a physicist would call the density, since the 0.82")
    print("  factor is only a shape fudge).")
    print()
    print(f"    {'fruit':<16}{'d':>6}{'m ship':>9}{'rho ship':>10}{'rho 0.5x':>10}"
          f"{'rho 0.25x':>11}{'solid 0.25x':>13}")
    for label, name, d in (("peach", "peach", 0.065), ("kiwi", "kiwi", 0.056),
                           ("apple", "apple", 0.066), ("orange", "orange", 0.065)):
        rho = SHAPES[name][0]
        m = mass(d, rho)
        solid = m / volume(d)
        print(f"    {label + ' ' + f'{d*100:.1f}cm':<16}{d*100:>6.1f}{m*1e3:>9.1f}"
              f"{rho:>10.0f}{rho*0.5:>10.0f}{rho*0.25:>11.0f}"
              f"{solid*0.25:>13.0f}")
    print()
    print("  Reference densities [kg/m^3]: water 1000, real peach ~1000 (the P11")
    print("  audit's own 137 g at 60 mm implies 1215), real kiwi ~1050, cork ~240,")
    print("  balsa ~160, pine ~500. So:")
    print("    0.5x  -> 410-450 kg/m^3 = softwood; floats; not fruit.")
    print("    0.25x -> 205-225 kg/m^3 = cork; floats high; definitely not fruit.")
    print()
    print("  The one physical way to read it: a HOLLOW SHELL of real-density flesh.")
    for label, name, d in (("peach", "peach", 0.065), ("kiwi", "kiwi", 0.056)):
        rho = SHAPES[name][0]
        m = mass(d, rho)
        r = d / 2.0
        for s in (0.5, 0.25):
            v_shell = m * s / 1000.0  # at 1000 kg/m^3 material
            v_out = volume(d)
            v_in = v_out - v_shell
            r_in = (3.0 * v_in / (4.0 * math.pi)) ** (1.0 / 3.0)
            print(f"    {s:>4.2f}x {label} {d*100:.1f} cm: m = {m*s*1e3:5.1f} g -> "
                  f"a wall of {1000*(r-r_in):.2f} mm at 1000 kg/m^3")
    print()
    print("  And the physical version of the SAME experiment: at the real density,")
    print("  0.25x the mass is a SMALLER fruit -")
    for label, name, d in (("peach", "peach", 0.065), ("kiwi", "kiwi", 0.056)):
        print(f"    {label} {d*100:.1f} cm -> {d*100*0.25**(1/3):.1f} cm")
    print("  - which changes the pinch span (`pinch_width`), the pad standoff and")
    print("  the reach: a different geometric experiment, not a mass one.")


def table_g() -> None:
    section("G. The measured anchors")
    rows = [
        ("pool mass range (shipped)", "8.0-132.5 g", "section A, this script"),
        ("pool mass range (REAL_MASS)", "9.4-147.3 g", "section B"),
        ("pool composition", "16 fruit, 2 of each class",
         "[supply] scatter pool=16 ... classes=strawberry:2,... in every log"),
        ("release probe peak, shipped asym", "0.748 m/s (20 trials)",
         "logs/474_probe_asym.log"),
        ("release probe peak, fast symmetric", "1.335 m/s (a 2.8 cm lychee)",
         "logs/473_probe_final.log trial 16"),
        ("line release peak, in-hand", "0.771-0.932 m/s (8 of 10)",
         "logs/p44/p2/amend_F_C.log"),
        ("line release peak, already lost", "4.782 / 4.810 m/s (2 of 10)",
         "same log: free fall from the place height, not an ejection"),
        ("clean_slip, clean legs", "0.02-1.43 mm (median 0.04, n=33)",
         "logs/w8/B_RESULTS.md / logs/p9"),
        ("clean_slip, escape legs", "17.9-957 mm (median 278, n=31)",
         "same"),
        ("live clean_slip_max, P44 C", "0.1 mm clean / 978-1402 mm lost",
         "logs/p44/P2_RESULTS.md 9.2"),
        ("carry force, held legs", "4.1-4.5 N (9.31/9.74 N at P41+park)",
         "logs/p9 3.4 / logs/p43 P3"),
        ("worst carry transient", "5.83 m/s^2 single tick", "logs/p40/GRIP_CENSUS.md 4.1"),
        ("the slip ratio, measured", "0.10-0.78 (median 0.36 escapes / 0.37 held)",
         "logs/p9/FRICTION_AUDIT.md section 1"),
    ]
    for what, value, where in rows:
        print(f"  {what:<34} {value:<40} {where}")


def table_h() -> None:
    section("H. Every knob / site that changes mass or density")
    rows = [
        ("FRUIT_PHYSICS_REAL", "unset", "meshes.py:355, 362",
         "master; =1 turns on all three P12-A components"),
        ("FRUIT_PHYSICS_REAL_MASS", "unset (follows the master)",
         "meshes.py:356, 384, 399-410",
         "switches `fruit_density` to `density_real`; read once at import"),
        ("FruitShape.density", "700-900 kg/m^3", "meshes.py:261-310",
         "the shipped per-class density"),
        ("FruitShape.density_real", "840-1050 kg/m^3", "meshes.py:261-310",
         "the P12-A per-class real density"),
        ("the mass site", "-", "fruits.py:977 (create), 1039 (rescale)",
         "rho * 4/3 pi r^3 * 0.82 -> CreateMassAttr().Set(mass)"),
        ("the inertia", "-", "fruits.py:980-981, 1063",
         "NOT authored: PhysX derives it from the collider volume at that mass"),
        ("FRUIT_FORCE_FACTOR", "100", "tasks.py:11003, grasp.py:223",
         "INDEXED/policy close budget clip(m*g*100, 25, 60) N"),
        ("(same, second site)", "60", "tasks.py:11029",
         "INDEXED/policy load-up clip(m*g*60, 20, 40) N"),
        ("SceneConfig.fruit_dimensions", "sec. A", "assets.py:439-456",
         "mass ~ d^3; FRUIT_SIZE_FILTER (assets.py:441) narrows it"),
    ]
    for knob, default, site, what in rows:
        print(f"  {knob:<26} {default:<24} {site:<40} {what}")
    print()
    print("  There is NO scale knob: `grep FRUIT_[A-Z_]*MASS src/` finds only the two")
    print("  P12-A switches plus FRUIT_FINGER_SOFT_PAD_MASS (the opt-in padded hand's")
    print("  pad mass, scene.py:1575 - not a fruit). `FRUIT_MASS_SCALE` is the")
    print("  PREREG's design, not shipped code.")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help="kept for symmetry with the other census scripts")
    args = parser.parse_args(argv)
    print("P45 phase 1 - MASS CENSUS (offline; no stage, no pxr, no simulator)")
    print("tree: HEAD 1bae811; fruits.py 6f65e423, meshes.py 41efc522,")
    print("      assets.py 61baf52b, tasks.py b6de439c, grasp.py 6417e1d2")
    table_a()
    table_b()
    table_c()
    table_d()
    table_e()
    table_e2()
    table_f()
    table_g()
    table_h()
    if args.write:
        print("\n(run of record: logs/p45/MASS_CENSUS_out.txt)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
