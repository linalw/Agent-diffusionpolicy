"""Procedural fruit meshes.

Each fruit is built as a surface of revolution from a profile curve, with
per-instance surface noise, so no two are identical. Vertices are generated
**at the final size in metres** - never via a Scale xform op, because PhysX
does not cook collision correctly for scaled shapes (see WORKLOG).
"""

from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass, field

import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade


# --------------------------------------------------------------------------- #
# Profiles: return a list of (radius, z) in normalised units, bottom -> top.
# --------------------------------------------------------------------------- #
#: Hand-traced apple silhouette, bottom pole -> top pole, in normalised units
#: (widest radius = 1). The shoulder sits *above* the stem cavity, which is what
#: makes an apple read as an apple rather than a ball with a dent.
APPLE_CONTROL: list[tuple[float, float]] = [
    (0.00, -0.90),   # calyx basin floor
    (0.26, -0.93),
    (0.52, -0.88),
    (0.76, -0.70),
    (0.92, -0.44),
    (1.00, -0.12),
    (1.00, 0.12),
    (0.96, 0.36),
    (0.86, 0.58),
    (0.68, 0.76),
    (0.47, 0.87),
    (0.31, 0.90),    # shoulder
    (0.21, 0.86),    # cavity wall
    (0.12, 0.80),
    (0.00, 0.78),    # cavity floor, where the stem sits
]


def _interp_control(control: list[tuple[float, float]], samples: int) -> list[tuple[float, float]]:
    """Catmull-Rom through the control points, resampled to `samples` rows."""
    pts = [control[0]] + list(control) + [control[-1]]
    out: list[tuple[float, float]] = []
    total = len(control) - 1
    for i in range(samples + 1):
        u = i / samples * total
        seg = min(int(u), total - 1)
        t = u - seg
        p0, p1, p2, p3 = pts[seg], pts[seg + 1], pts[seg + 2], pts[seg + 3]
        t2, t3 = t * t, t * t * t
        r = 0.5 * (
            2 * p1[0]
            + (-p0[0] + p2[0]) * t
            + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
            + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
        )
        z = 0.5 * (
            2 * p1[1]
            + (-p0[1] + p2[1]) * t
            + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
            + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
        )
        out.append((max(0.0, r), z))
    return out


def apple_profile(samples: int = 44) -> list[tuple[float, float]]:
    """A real apple silhouette: shoulders above a deep stem cavity, calyx basin."""
    return _interp_control(APPLE_CONTROL, samples)


#: Hand-traced pear silhouette (P32 phase 3), as (r / r_max, z / H): r is in
#: units of the widest half-width and z runs 0 at the base rim to 1 at the top
#: lip. The body rows are the reference photo's outer contour at the 0.05 H step
#: (`~/图片/截图/4315455_113747057037_2.jpg`, a yellow-green pear; the extraction
#: and the figure are `scripts/212_pear_profile.py`, `logs/p32/pear_profile.png`):
#: H/W 1.150, widest at 0.307 H, neck 0.483 r_max at 0.80 H, a rounded base
#: (0.419 r_max at the contact) and a 4 %-of-H stem cavity inside a 0.115 r_max
#: lip. The body is a single-valued r(z); the basin floor before the rim and the
#: cavity floor after the lip are the two z reversals (3 sampled rows each, the
#: same construction as APPLE_CONTROL's calyx basin). The photo's base is a broad
#: contact ring around a shadowed dimple, not a pole.
PEAR_CONTROL: list[tuple[float, float]] = [
    (0.000, 0.020),   # calyx basin floor
    (0.419, 0.000),   # base rim / contact ring, the lowest point
    (0.530, 0.009),   # base round-off: 0.42 -> 0.73 r_max in the first 0.05 H
    (0.630, 0.022),
    (0.690, 0.036),
    (0.725, 0.050),
    (0.841, 0.100),
    (0.916, 0.150),
    (0.970, 0.200),
    (0.993, 0.250),   # the maximum is flat: 0.25-0.35 H are within 1 %
    (1.000, 0.307),   # widest point, a third of the way up the body
    (0.986, 0.350),
    (0.968, 0.400),
    (0.926, 0.450),
    (0.874, 0.500),
    (0.812, 0.550),
    (0.739, 0.600),
    (0.669, 0.650),
    (0.599, 0.700),
    (0.537, 0.750),
    (0.483, 0.800),   # neck
    (0.438, 0.850),
    (0.390, 0.900),
    (0.319, 0.950),
    (0.115, 1.000),   # the lip the stem sits in
    (0.000, 0.960),   # cavity floor, where the stem is authored
]

#: The pear's height over its width. The photo (body only, stem excluded) reads
#: 1.150 +-0.005 across the mask thresholds 25-90/255; 1.20 is the owner's
#: 1.2-1.3 band floor, +4.3 % on the measurement and inside the 5 % match.
PEAR_HEIGHT_RATIO = 1.20


def pear_profile(samples: int = 75) -> list[tuple[float, float]]:
    """The reference pear: smooth teardrop, long neck, stem cavity on top.

    `PEAR_CONTROL` is height-normalised; the mesh frame needs r in units of the
    widest half-width (= the class radius, so the class diameter stays the
    pear's width) and z in the same units. The base rim sits at z = -1, which is
    what the spawner assumes (`belt + diameter / 2` puts the lowest row on the
    belt, `fruits.py`); H/W = 1.20 puts the lip at z = +1.40.

    `samples` is three rows per control segment (75 for 25 segments) so the
    measured rows - the widest at 0.307 H and the cavity lip - land on rings and
    the delivered mesh carries the measured silhouette; the old 41-ring shape
    read as a faceted bucket (`logs/p29/fruit_pear.png`, P32 phase 3). The
    pre-change profile is kept for the comparison in
    `scripts/212_pear_profile.py`.
    """
    span = 2.0 * PEAR_HEIGHT_RATIO
    control = [(r, -1.0 + span * z) for (r, z) in PEAR_CONTROL]
    profile = _interp_control(control, samples)
    # Normalise to the realised maximum: the class diameter is defined as the
    # fruit's width, so the widest row must be exactly one class radius.
    r_max = max(r for (r, _) in profile)
    return [(r / r_max, z) for (r, z) in profile]


def _sphere_with_dimple(samples: int, top_dimple: float, flat: float) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for i in range(samples + 1):
        theta = math.pi * i / samples
        r = math.sin(theta)
        z = math.cos(theta) * flat
        if top_dimple > 0 and theta < 0.55:
            k = 1.0 - theta / 0.55
            z -= top_dimple * k**1.4
            r *= 1.0 - 0.20 * k**2
        pts.append((r, z))
    return pts


def orange_profile(samples: int = 40) -> list[tuple[float, float]]:
    return _sphere_with_dimple(samples, top_dimple=0.05, flat=1.0)


def tomato_profile(samples: int = 40) -> list[tuple[float, float]]:
    return _sphere_with_dimple(samples, top_dimple=0.10, flat=0.88)


def peach_profile(samples: int = 40) -> list[tuple[float, float]]:
    return _sphere_with_dimple(samples, top_dimple=0.12, flat=0.94)


def kiwi_profile(samples: int = 40) -> list[tuple[float, float]]:
    return _sphere_with_dimple(samples, top_dimple=0.04, flat=1.15)


def lychee_profile(samples: int = 40) -> list[tuple[float, float]]:
    return _sphere_with_dimple(samples, top_dimple=0.03, flat=1.0)


def strawberry_profile(samples: int = 40) -> list[tuple[float, float]]:
    """Conical: wide shoulders, pointed tip."""
    pts: list[tuple[float, float]] = []
    for i in range(samples + 1):
        t = i / samples
        # t=0 at the tip (bottom), t=1 at the shoulders (top)
        r = math.sin(math.pi * t) ** 0.75
        z = -1.0 + 2.0 * t
        r *= 0.55 + 0.45 * t  # taper toward the tip
        if t > 0.88:
            k = (t - 0.88) / 0.12
            z -= 0.06 * k**1.5
            r *= 1.0 - 0.30 * k**2
        pts.append((r, z))
    return pts


# --------------------------------------------------------------------------- #
@dataclass
class FruitShape:
    """Everything that makes one fruit category look and feel different."""

    name: str
    profile: object
    colors: list[tuple[float, float, float]]
    roughness: float = 0.35
    #: (min, max) kinetic friction against the belt rubber
    friction: tuple[float, float] = (0.5, 0.9)
    #: kg/m^3
    density: float = 800.0
    #: kg/m^3 under the mass component (`FRUIT_PHYSICS_REAL_MASS=1`, or the
    #: master `FRUIT_PHYSICS_REAL=1` with the sub-knob unset; P12-A/P12-A.2):
    #: the measured real density (`logs/p11/A_PHYSICS_AUDIT.md` section 2.1) or
    #: a documented estimate. 0.0 = no real value, the shipped `density` stands.
    density_real: float = 0.0
    #: N/m under the compliance component (`FRUIT_PHYSICS_REAL_COMPLIANCE=1`, or
    #: the master with the sub-knob unset; P12-A/P12-A.2): the Hertzian
    #: whole-fruit contact stiffness at 1 mm of compression (audit sections
    #: 2.2/5b.1) or a size-and-firmness estimate. 0.0 = the shipped rigid
    #: contact.
    contact_stiffness_real: float = 0.0
    stem: bool = False
    #: amplitude of the surface noise, relative to the radius
    bumpy: float = 0.02
    #: how much the shape is squashed along z when placed (1.0 = none)
    length_scale: float = 1.0
    #: number of vertical lobes (apples have five); 0 disables lobing
    lobes: int = 0
    #: amplitude of the lobing, relative to the radius
    lobe_amount: float = 0.02


#: P12-A property realism (`FRUIT_PHYSICS_REAL=1`; default 0 = the shipped
#: values; P12-A.2 splits the batch into the `FRUIT_PHYSICS_REAL_MASS` /
#: `_REST` / `_COMPLIANCE` component sub-knobs - see the switch block below).
#: The reference is the P11-A audit (`logs/p11/A_PHYSICS_AUDIT.md`,
#: sections 1-2 and 5b); per class the real density [kg/m^3] and the
#: compliant-contact stiffness [N/m] at 1 mm of compression are:
#:
#:   class       density                          contact stiffness
#:   apple       840    FULL - Jia et al. 2026    27000  model - Hertzian (E 2.091 MPa, nu 0.35, R 33 mm)
#:   tomato      960    FULL - Geasa & Hassan     4000  model - Hertzian (E 0.30 MPa, nu 0.45, R 26.5 mm)
#:   orange      1000   abstract - 0.97-1.03      13000  est. - firm rind
#:   peach       1000   est.                      19000  E 1.53 MPa FULL; nu/R assumed
#:   pear        950    est.                      15000  est. - firm flesh
#:   kiwi        1050   est.                       7000  est. - soft flesh
#:   lychee      1000   est.                      23000  est. - hard pericarp
#:   strawberry  950    est.                       3000  est. - very soft
#:
#: "est." = no audited source: the density in the sensible 950-1050 kg/m^3
#: band and the stiffness from the same Hertzian form k(1 mm) = 2 E* sqrt(R d)
#: with an assumed E for the class's firmness. The audit's own peach
#: mass/diameter reading (137 g at ~60 mm) would imply ~1215 kg/m^3 if a
#: sphere is trusted, so the peach estimate is deliberately conservative.
#: The mass formula itself is unchanged (density x 4/3 pi r^3 x the 0.82
#: sphere-shape discount, `fruits.py`): the optional per-class volume proxy
#: was not taken, so the real densities narrow but do not close the mass gap
#: (apple ~12 % light at 81 mm, tomato ~27 % at 53 mm, peach ~32 % at 60 mm -
#: the 0.82 factor is the residual).
FRUIT_SHAPES: dict[str, FruitShape] = {
    "apple": FruitShape(
        "apple", apple_profile,
        [(0.46, 0.025, 0.045), (0.40, 0.035, 0.075), (0.52, 0.28, 0.035)],
        roughness=0.30, friction=(0.45, 0.70), density=850.0, stem=True, bumpy=0.010,
        lobes=5, density_real=840.0, contact_stiffness_real=27000.0,
    ),
    "pear": FruitShape(
        "pear", pear_profile,
        [(0.42, 0.44, 0.10), (0.50, 0.42, 0.075), (0.36, 0.38, 0.09)],
        roughness=0.42, friction=(0.45, 0.70), density=880.0, stem=True, bumpy=0.012,
        density_real=950.0, contact_stiffness_real=15000.0,
    ),
    "orange": FruitShape(
        "orange", orange_profile,
        [(0.78, 0.26, 0.02), (0.70, 0.22, 0.02)],
        roughness=0.68, friction=(0.70, 1.00), density=900.0, bumpy=0.030,
        density_real=1000.0, contact_stiffness_real=13000.0,
    ),
    "tomato": FruitShape(
        "tomato", tomato_profile,
        [(0.58, 0.045, 0.03), (0.66, 0.09, 0.035)],
        roughness=0.28, friction=(0.50, 0.75), density=780.0, stem=False, bumpy=0.012,
        density_real=960.0, contact_stiffness_real=4000.0,
    ),
    "peach": FruitShape(
        "peach", peach_profile,
        [(0.74, 0.30, 0.17), (0.66, 0.26, 0.15)],
        roughness=0.72, friction=(0.55, 0.85), density=820.0, bumpy=0.006,
        density_real=1000.0, contact_stiffness_real=19000.0,
    ),
    "kiwi": FruitShape(
        "kiwi", kiwi_profile,
        [(0.26, 0.175, 0.075), (0.22, 0.155, 0.065)],
        roughness=0.85, friction=(0.75, 1.05), density=900.0, bumpy=0.030,
        density_real=1050.0, contact_stiffness_real=7000.0,
    ),
    "lychee": FruitShape(
        "lychee", lychee_profile,
        [(0.50, 0.10, 0.085), (0.44, 0.085, 0.07)],
        roughness=0.80, friction=(0.55, 0.85), density=850.0, bumpy=0.045,
        density_real=1000.0, contact_stiffness_real=23000.0,
    ),
    "strawberry": FruitShape(
        "strawberry", strawberry_profile,
        [(0.60, 0.035, 0.05), (0.52, 0.03, 0.045)],
        roughness=0.45, friction=(0.55, 0.85), density=700.0, stem=False, bumpy=0.035,
        density_real=950.0, contact_stiffness_real=3000.0,
    ),
}


def shape_for(name: str) -> FruitShape:
    """`FRUIT_SHAPES[name]` with a clear failure when a class has no mesh.

    `SceneConfig.fruit_dimensions` and this table must name the same classes;
    the `.get` here turns a bare `KeyError` (the Gate-B R6 item) into the
    sentence that says which file to fix. Callers: the raised output belt's
    clearance audit (`conveyor.OutputBelt.build`) and its offline twin
    (`scripts/422_v3_layout_probe.py`).
    """
    shape = FRUIT_SHAPES.get(name)
    assert shape is not None, (
        f"fruit class {name!r} has no FRUIT_SHAPES entry; add it to "
        f"src/fruit_sorting/meshes.py (the scene config's fruit_dimensions "
        f"and this table must name the same classes)"
    )
    return shape


# --------------------------------------------------------------------------- #
# P12-A / P12-A.2: the property-realism switches for the real table above
# (owner directive 2026-10-18; the two-line anchor is the measurement reference,
# no re-baseline in the implementation lane). The batch is one master switch
# plus three component sub-knobs:
#
#   FRUIT_PHYSICS_REAL              master; `1` turns on ALL THREE components
#   FRUIT_PHYSICS_REAL_MASS         the real per-class densities/masses
#   FRUIT_PHYSICS_REAL_REST         the restitution 0.35-0.50 band (fruits.py)
#   FRUIT_PHYSICS_REAL_COMPLIANCE   the per-class fruit compliant contact
#
# Resolution (per component): a sub-knob explicitly present in the environment
# always wins for its component with the exact `== "1"` parse the other
# `FRUIT_*` flags use (`0`/any other value = off); when unset, the component
# follows the master - so `FRUIT_PHYSICS_REAL=1` alone is the committed P12-A
# batch and `FRUIT_PHYSICS_REAL=1 FRUIT_PHYSICS_REAL_REST=0` is mass +
# compliance only. All four variables are read ONCE at import - this gates
# build-time physics authoring, so it cannot change mid-run - and unset/`0`/any
# other value everywhere keeps the shipped numbers, so the shipped path is
# byte-inert. `fruits.py` never reads the environment; it consumes the
# resolvers below (`restitution_range` reads `physics_real_rest`, the material
# helper's stiffness argument `fruit_contact_stiffness` reads
# `physics_real_compliance`, the mass sites `fruit_density` reads
# `physics_real_mass`).
_PHYSICS_REAL_RAW = os.environ.get("FRUIT_PHYSICS_REAL")
_PHYSICS_REAL_MASS_RAW = os.environ.get("FRUIT_PHYSICS_REAL_MASS")
_PHYSICS_REAL_REST_RAW = os.environ.get("FRUIT_PHYSICS_REAL_REST")
_PHYSICS_REAL_COMPLIANCE_RAW = os.environ.get("FRUIT_PHYSICS_REAL_COMPLIANCE")


def physics_real() -> bool:
    """Whether the P12-A master switch is on (`FRUIT_PHYSICS_REAL=1`).

    The exact `== "1"` parse the other `FRUIT_*` flags use. This is the
    component default when a sub-knob is unset; the components themselves are
    read through `physics_real_mass()` / `physics_real_rest()` /
    `physics_real_compliance()`.
    """
    return _PHYSICS_REAL_RAW == "1"


def _component_real(sub_raw: str | None) -> bool:
    """Resolve one P12-A.2 component: an explicit sub-knob wins, else the master.

    `sub_raw` is the sub-knob's raw env value (`None` = unset). Explicit means
    present at all: the exact `== "1"` parse applies, so `=0` (or any other
    value) is an explicit off even under `FRUIT_PHYSICS_REAL=1`.
    """
    if sub_raw is not None:
        return sub_raw == "1"
    return physics_real()


def physics_real_mass() -> bool:
    """Whether the real per-class densities/masses are on (P12-A.2)."""
    return _component_real(_PHYSICS_REAL_MASS_RAW)


def physics_real_rest() -> bool:
    """Whether the real restitution band is on (P12-A.2)."""
    return _component_real(_PHYSICS_REAL_REST_RAW)


def physics_real_compliance() -> bool:
    """Whether the per-class fruit compliant contact is on (P12-A.2)."""
    return _component_real(_PHYSICS_REAL_COMPLIANCE_RAW)


def fruit_density(shape: FruitShape, real: bool | None = None) -> float:
    """The class's mass density [kg/m^3] for the fruit mass formula.

    The shipped `shape.density`, or the measured/estimated `shape.density_real`
    when the mass component is on (`FRUIT_PHYSICS_REAL_MASS=1`, or the master
    with the sub-knob unset; a class without a real value falls back to the
    shipped one). `real` overrides the resolution for the offline stub.
    """
    on = physics_real_mass() if real is None else bool(real)
    if on and shape.density_real > 0.0:
        return shape.density_real
    return shape.density


def fruit_contact_stiffness(shape: FruitShape, real: bool | None = None) -> float:
    """The fruit material's compliant-contact stiffness [N/m]; 0.0 = rigid.

    Authored only when the compliance component is on
    (`FRUIT_PHYSICS_REAL_COMPLIANCE=1`, or the master with the sub-knob unset;
    the audit's option 5b.1: the fruit side of the contact becomes a
    spring-damper, so a squeeze is partly absorbed by compression instead of
    going entirely into fruit motion). `real` overrides the resolution for the
    offline stub.
    """
    on = physics_real_compliance() if real is None else bool(real)
    if on and shape.contact_stiffness_real > 0.0:
        return shape.contact_stiffness_real
    return 0.0


# --------------------------------------------------------------------------- #
def axis_extent(shape: FruitShape, diameter: float, local_axis) -> float:
    """Extent of the fruit along `local_axis` (unit, in the fruit's own frame) [m].

    The mesh is a surface of revolution about its local z, so its support along
    any direction follows from the profile alone - no mesh query, no USD access.
    That matters twice over: the per-grasp USD traversal used for this measurement
    slowed a closed-loop run by ~4x, and reads inside the control loop perturb the
    simulation (see the WORKLOG).

    The per-instance deformation is not reproduced (each fruit gets a +/-6 % length
    bias and a small lobing), so this is the undeformed extent: good to a few
    percent, which is what a closure diagnostic needs.
    """
    axis = np.asarray(local_axis, dtype=float)
    length = float(np.linalg.norm(axis))
    if length < 1e-9:
        return 0.0
    axis = axis / length
    scale = diameter / 2.0
    radial = float(np.hypot(axis[0], axis[1]))
    axial = shape.length_scale * axis[2]
    # A surface of revolution has a point at every azimuth, so the support in +u
    # comes from the widest row on that side and the support in -u from the widest
    # row on the other: the extent is the sum, not the range, of the two.
    profile = shape.profile()
    support_plus = max(
        r_norm * scale * radial + z_norm * scale * axial for (r_norm, z_norm) in profile
    )
    support_minus = max(
        r_norm * scale * radial - z_norm * scale * axial for (r_norm, z_norm) in profile
    )
    return float(support_plus + support_minus)


#: The upper bound of the per-instance mesh scale: `build_mesh_points` draws
#: `uniform(0.94, 1.06)` for both lateral biases and the z length
#: (`rng.uniform(0.94, 1.06)`), so a static clearance audit must read
#: `fruit_height(..., scale=INSTANCE_SCALE_MAX)` to bound the tallest instance
#: it will ever see rather than the nominal profile (Gate-B R5).
INSTANCE_SCALE_MAX = 1.06


def fruit_height(shape: FruitShape, diameter: float, scale: float = 1.0) -> float:
    """The fruit's own height along its axis [m], from the profile (undeformed).

    `diameter` is the *width* (the profile's r_max is the class radius), so a
    shape whose profile spans more than +-1 r_max in z - the pear's lip is at
    1.4, H/W 1.20 - is taller than it is wide. The answer feeds the raised
    output belt's under-belt clearance audit (`conveyor.OutputBelt.build`,
    `scripts/422_v3_layout_probe.py`), which used to read the *diameter* and
    therefore overstated the gap by 1.4 cm once the pear became 1.2 d tall.

    `scale` folds the per-instance deformation in: `build_mesh_points` draws
    `uniform(0.94, 1.06)` for the z length, so the nominal read (`scale=1.0`)
    is the undeformed profile and `scale=INSTANCE_SCALE_MAX` is the tallest
    instance the mesh can deliver (the Gate-B R5 item: the 46 mm body
    clearance is nominal, the instance-scale bound is ~41 mm).
    """
    z = [p[1] for p in shape.profile()]
    return (max(z) - min(z)) * diameter / 2.0 * shape.length_scale * scale


def stem_over_top(shape: FruitShape, diameter: float) -> float:
    """The tallest the authored stalk can stand above the fruit's top [m].

    `author_stem` draws `length = uniform(0.30, 0.45) * diameter`, sets the
    cylinder's centre to `(cavity_floor + top_z) / 2 + 0.30 * length` and tilts
    it by up to 12 deg. A clearance audit must not *understate* the fruit, so
    this returns the bound `0.45 * diameter` - the longest stalk standing on the
    body top - rather than the authored stalk's real reach, which is smaller by
    the cavity depth (the stalk is seated in it). A stem-less shape returns 0.
    """
    return 0.45 * diameter if shape.stem else 0.0


def build_mesh_points(
    shape: FruitShape, diameter: float, rng: random.Random, segments: int = 28
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (points, faces, vertex_normals) for the fruit at `diameter` metres."""
    profile = shape.profile()
    scale = diameter / 2.0
    # Per-instance deformation so no two fruit are identical.
    bias_a = rng.uniform(0.94, 1.06)
    bias_b = rng.uniform(0.94, 1.06)
    length = shape.length_scale * rng.uniform(0.94, 1.06)
    phase = rng.uniform(0.0, math.tau)

    points: list[tuple[float, float, float]] = []
    rows: list[list[int]] = []  # vertex indices per profile row (poles = 1 index)
    pole_rows: list[bool] = []
    for (r_norm, z_norm) in profile:
        if r_norm * scale < 1e-4:
            # A true pole is a single vertex. Emitting `segments` coincident
            # vertices there creates degenerate triangles and PhysX then fails to
            # cook the convex hull - the collider silently disappears and the
            # gripper closes straight through the fruit.
            index = len(points)
            points.append((0.0, 0.0, z_norm * scale * length))
            rows.append([index])
            pole_rows.append(True)
            continue
        row: list[int] = []
        for j in range(segments):
            phi = math.tau * j / segments
            lobe = (
                1.0 + shape.lobe_amount * math.cos(shape.lobes * phi + phase)
                if shape.lobes else 1.0 + 0.03 * math.cos(2.0 * phi + phase)
            )
            noise = 1.0 + shape.bumpy * rng.uniform(-1.0, 1.0)
            r = r_norm * scale * lobe * noise * (bias_a if math.cos(phi) > 0 else bias_b)
            z = z_norm * scale * length * (1.0 + 0.01 * rng.uniform(-1.0, 1.0))
            row.append(len(points))
            points.append((r * math.cos(phi), r * math.sin(phi), z))
        rows.append(row)
        pole_rows.append(False)

    faces: list[int] = []
    for i in range(len(rows) - 1):
        lower, upper = rows[i], rows[i + 1]
        if pole_rows[i]:
            pole = lower[0]
            for j in range(segments):
                faces += [pole, upper[(j + 1) % segments], upper[j]]
            continue
        if pole_rows[i + 1]:
            pole = upper[0]
            for j in range(segments):
                faces += [lower[j], lower[(j + 1) % segments], pole]
            continue
        for j in range(segments):
            jn = (j + 1) % segments
            faces += [lower[j], lower[jn], upper[jn], lower[j], upper[jn], upper[j]]

    points_arr = np.asarray(points, dtype=np.float32)
    faces_arr = np.asarray(faces, dtype=np.int32).reshape(-1, 3)
    # Smooth vertex normals: average the adjacent face normals.
    normals = np.zeros_like(points_arr)
    tri = points_arr[faces_arr]
    face_normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    for k, face in enumerate(faces_arr):
        normals[face] += face_normals[k]
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = normals / np.maximum(lengths, 1e-9)
    return points_arr, faces_arr.reshape(-1), normals


def make_material(
    stage: Usd.Stage, path: str, colour: tuple[float, float, float], roughness: float,
    metallic: float = 0.0, clearcoat: float = 0.0,
) -> UsdShade.Material:
    material = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, f"{path}/shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*colour))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(metallic)
    shader.CreateInput("specular", Sdf.ValueTypeNames.Float).Set(0.12 + 0.18 * clearcoat)
    shader.CreateInput("clearcoat", Sdf.ValueTypeNames.Float).Set(clearcoat)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return material


def author_fruit(
    stage: Usd.Stage,
    path: str,
    shape: FruitShape,
    diameter: float,
    rng: random.Random,
    colour: tuple[float, float, float],
    segments: int = 28,
) -> UsdGeom.Mesh:
    """Author a fruit mesh prim at `path`, sized in metres, with no Scale op."""
    points, faces, normals = build_mesh_points(shape, diameter, rng, segments)
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr(points.tolist())
    mesh.CreateFaceVertexCountsAttr([3] * (len(faces) // 3))
    mesh.CreateFaceVertexIndicesAttr(faces.tolist())
    mesh.CreateSubdivisionSchemeAttr("none")
    mesh.CreateNormalsAttr(normals.tolist())
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
    mesh.CreateExtentAttr(
        [
            (float(points[:, 0].min()), float(points[:, 1].min()), float(points[:, 2].min())),
            (float(points[:, 0].max()), float(points[:, 1].max()), float(points[:, 2].max())),
        ]
    )

    material = make_material(
        stage, f"{path}_mat", colour, shape.roughness,
        clearcoat=0.25 if shape.roughness < 0.35 else 0.0,
    )
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)

    UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
    mesh_collision = UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim())
    # Approximation is tunable because PhysX fails to cook some of them for these
    # procedurally generated meshes: with "convexHull" the collider silently
    # vanishes and the gripper closes straight through the fruit.
    mesh_collision.CreateApproximationAttr().Set(
        os.environ.get("FRUIT_COLLISION_APPROX", "convexHull")
    )
    return mesh


def author_stem(
    stage: Usd.Stage, path: str, shape: FruitShape, diameter: float, rng: random.Random
) -> None:
    """A short stalk on top of the fruit - a big part of looking like fruit."""
    if not shape.stem:
        return
    profile = shape.profile()
    top_z = max(p[1] for p in profile) * diameter / 2.0 * shape.length_scale
    cavity_floor = profile[-1][1] * diameter / 2.0 * shape.length_scale
    length = rng.uniform(0.30, 0.45) * diameter
    stem = UsdGeom.Cylinder.Define(stage, path)
    stem.GetRadiusAttr().Set(max(0.0015, diameter * 0.035))
    stem.GetHeightAttr().Set(length)
    xform = UsdGeom.Xformable(stem)
    xform.ClearXformOpOrder()
    xform.AddTranslateOp().Set(
        Gf.Vec3d(
            rng.uniform(-0.01, 0.01) * diameter,
            rng.uniform(-0.01, 0.01) * diameter,
            (cavity_floor + top_z) / 2.0 + length * 0.30,
        )
    )
    xform.AddRotateXYZOp().Set(
        Gf.Vec3f(rng.uniform(-12, 12), rng.uniform(-12, 12), 0.0)
    )
    material = make_material(stage, f"{path}_mat", (0.32, 0.22, 0.10), 0.8)
    UsdShade.MaterialBindingAPI.Apply(stem.GetPrim()).Bind(material)
