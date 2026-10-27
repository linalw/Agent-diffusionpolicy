"""Randomized fruit objects and the conveyor spawner.

Fruit quality attributes (grade, ripeness, defects) are NOT perceived - the task
scope for now is pick-and-sort of moving fruit, so those attributes are drawn at
random and used only as task labels.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass

import numpy as np
from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.experimental.prims import RigidPrim

from .assets import SceneConfig
from .bed import BedPlan, BedSchedule
from .common import say
from .meshes import (
    FRUIT_SHAPES,
    author_fruit,
    author_stem,
    fruit_contact_stiffness,
    fruit_density,
    make_material,
    mass_scale,
    physics_real,
    physics_real_compliance,
    physics_real_mass,
    physics_real_rest,
)


def tune_contact_body(prim) -> None:
    """Contact-stability tuning for a fruit rigid body.

    The kinematic pads model the grip by *interfering* with the fruit: their
    faces are commanded ~2 % inside its diameter, so every tick PhysX depenetrates
    the fruit back out. With the default (unlimited) depenetration velocity that
    ejection is violent - the payload rattles inside the closed pads at
    0.3-0.5 m/s with a ~5 mm swing (measured, logs/266) - which is both what the
    slip monitor kept reacting to and what makes the grasp look twitchy.
    Capping the depenetration speed turns the same contact into a gentle, damped
    push, and a little body damping removes the residual ringing.

    All three are opt-in through the environment so the default stays the plain
    PhysX behaviour unless asked otherwise.
    """
    api = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
    api.CreateEnableCCDAttr().Set(False)
    for name, env, default in (
        ("MaxDepenetrationVelocity", "FRUIT_MAX_DEPEN_VELOCITY", "0"),
        ("LinearDamping", "FRUIT_LINEAR_DAMPING", "0"),
        ("AngularDamping", "FRUIT_ANGULAR_DAMPING", "0"),
    ):
        value = float(os.environ.get(env, default))
        if value <= 0.0:
            continue
        create = getattr(api, f"Create{name}Attr", None)
        if create is None:
            say(f"warning: PhysX rigid-body attribute {name} is not available here")
            continue
        create().Set(value)


# --------------------------------------------------------------------------- #
# P12-A / P12-A.2 property realism (the per-class density and contact table
# lives in `meshes.py`). The two values here are the fruit material's
# restitution band and the compliant-contact damping.
#
# Restitution: shipped uniform(0.02, 0.20) -> real uniform(0.35, 0.50). The
# audit (`logs/p11/A_PHYSICS_AUDIT.md` section 2.5, FULL) gives apple-apple
# COR 0.4 and apple-bin COR 0.5 (Jia et al. 2026); no per-class COR was
# sourced, so one band is used for every class. The component switch is
# `FRUIT_PHYSICS_REAL_REST` (or the master `FRUIT_PHYSICS_REAL=1` with the
# sub-knob unset); the resolution + read-once rules are documented in
# `meshes.py`.
#
# Damping: the audit's option 5b.1 suggests matching the finger material's
# 80 Ns/m for the fruit-side spring. The finger material itself is left at its
# shipped k = 30 kN/m (`assets.py`/`scene.py`): the material-pair combination
# rule is unverified offline (audit section 6), so the pair response is the
# battery's to measure rather than guessed here.
# --------------------------------------------------------------------------- #
_RESTITUTION_SHIPPED = (0.02, 0.2)
_RESTITUTION_REAL = (0.35, 0.50)
REAL_CONTACT_DAMPING = 80.0


def restitution_range(real: bool | None = None) -> tuple[float, float]:
    """The per-fruit restitution draw band - shipped unless the rest component
    is on (`FRUIT_PHYSICS_REAL_REST=1`, or the master with the sub-knob unset).

    `real` overrides the resolution for the offline stub.
    """
    on = physics_real_rest() if real is None else bool(real)
    return _RESTITUTION_REAL if on else _RESTITUTION_SHIPPED


def _physics_banner() -> str | None:
    """The P12-A/P12-A.2 banner naming the resolved physics, or None when off.

    Printed once per pool so a battery log names its physics; the knob-off
    stream is byte-identical (no line). With the master on and every component
    resolved on, the exact committed P12-A text is kept, so a
    `FRUIT_PHYSICS_REAL=1` log replays the committed line; a partial (or
    sub-knob-only) activation names the resolved component states instead.
    """
    mass_on = physics_real_mass()
    rest_on = physics_real_rest()
    compliance_on = physics_real_compliance()
    if not (mass_on or rest_on or compliance_on):
        return None
    if physics_real() and mass_on and rest_on and compliance_on:
        return (
            "[physics] FRUIT_PHYSICS_REAL=1: real class densities + "
            "restitution 0.35-0.50 + per-class compliant contact (P12-A)"
        )
    return (
        "[physics] FRUIT_PHYSICS_REAL components: "
        f"mass={int(mass_on)} rest={int(rest_on)} "
        f"compliance={int(compliance_on)} (P12-A.2)"
    )


def _mass_scale_banner() -> str | None:
    """The P45 banner naming the fruit mass scale, or None when it is shipped.

    Printed once per pool beside the P12-A banner, so every log names its
    physics; the shipped path prints nothing and is byte-identical. The line
    carries `mass_scale=<x>` so a battery log can be grepped for the arm it is.
    """
    scale = mass_scale()
    if scale == 1.0:
        return None
    return (
        f"[physics] FRUIT_MASS_SCALE={scale:g}: mass_scale={scale:g} "
        f"(mass x{scale:g} and, by PhysX's derivation, the inertia x{scale:g}; "
        "sizes/meshes/colliders unchanged - a physics experiment, not a "
        "fidelity claim; P45)"
    )


def _author_fruit_physics_material(
    stage: Usd.Stage,
    prim,
    path: str,
    friction: float,
    restitution: float,
    stiffness: float,
) -> None:
    """Author one fruit's physics material and bind it to `prim`.

    Always: static = dynamic friction and the restitution draw. When the
    compliance component is on (`FRUIT_PHYSICS_REAL_COMPLIANCE=1`, or the
    master with the sub-knob unset) a compliant-contact spring-damper is added
    on the fruit side (stiffness > 0, `REAL_CONTACT_DAMPING`) - the audit's
    option 5b.1, so a squeeze is partly absorbed by compression instead of
    going entirely into fruit motion. The shipped call authors exactly the
    shipped material - no `PhysxMaterialAPI` is applied - so the knob-off path
    is byte-inert.
    """
    phys_material = UsdShade.Material.Define(stage, f"{path}_physmat")
    phys_api = UsdPhysics.MaterialAPI.Apply(phys_material.GetPrim())
    phys_api.CreateStaticFrictionAttr().Set(friction)
    phys_api.CreateDynamicFrictionAttr().Set(friction)
    phys_api.CreateRestitutionAttr().Set(restitution)
    if stiffness > 0.0:
        contact = PhysxSchema.PhysxMaterialAPI.Apply(phys_material.GetPrim())
        contact.CreateCompliantContactStiffnessAttr().Set(float(stiffness))
        contact.CreateCompliantContactDampingAttr().Set(float(REAL_CONTACT_DAMPING))
    UsdShade.MaterialBindingAPI.Apply(prim).Bind(
        phys_material, UsdShade.Tokens.weakerThanDescendants, "physics"
    )


@dataclass
class FruitSample:
    """Metadata attached to one spawned fruit."""

    index: int
    prim_path: str
    category: str
    diameter: float
    mass: float
    friction: float
    grade: str
    ripeness: float
    defective: bool
    parked: bool = True
    #: Set once the gripper has closed on this fruit, so the belt stops driving it.
    held: bool = False
    #: Set while the gripper is carrying this fruit (see ``attach``).
    attached: bool = False


def _preview_material(stage: Usd.Stage, path: str, rgb: tuple[float, float, float], roughness: float = 0.45):
    material = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, f"{path}/shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*rgb))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return material


# --------------------------------------------------------------------------- #
# Scattered supply (v9/V1 directive)
# --------------------------------------------------------------------------- #
#: Shipped scattered-supply parameters. The pre-v9 spawner created the pool one
#: category per slot, released on a fixed `spawn_period_s` (0.19 m at 0.12 m/s),
#: primed 0.30 m apart, spawned within +/-5 mm of the centre line, and drew the
#: grade uniformly. Measured on that line: the bimanual grade-A lane (left arm)
#: reported "no eligible fruit" 29 times to the right arm's 6 in a ten-attempt
#: batch (`logs/g/10_rate_biarm_1..5.log`, bit-identical), the single-arm
#: acceptance ran with `queue_peak=0` because the feeder clock reset on every
#: `update` call (a 15 s attempt silently swallowed ~8 release slots), and the
#: 5 mm lateral spread was invisible. `FRUIT_SUPPLY_SCATTER=0` restores the
#: fixed line bit-for-bit for a like-for-like A/B.
SUPPLY_GAP_MIN = 0.10
SUPPLY_GAP_MAX = 0.35
#: Lateral scatter band, absolute across-the-belt x [m]. The belt spans
#: x = 0.11..0.57 (0.46 m) centred on the pick station (x = 0.34), but the
#: *reachable* band with the top-down grasp attitude is narrower and one-sided:
#: `scripts/174_station_reach.py` (both arms, seeded from the calibrated grasp
#: pose) holds ~6 mm residual for x = 0.18..0.39 and jumps to 55-96 mm at
#: x >= 0.42 (`logs/v1/61_station_reach_seeded.log`). The shipped scatter
#: therefore draws x in [0.20, 0.36] - 16 cm of visible spread.
#:
#: The belt's own drift does **not** stay inside the spawn band, and the old
#: claim here ("drift within +/-0.02 ... staying inside the reach") was wrong:
#: the delivered free-cadence line measured x min 0.148, i.e. 0.052 m below the
#: spawn floor (`logs/v1/12b_supply_after_free.log`). The V3 review extended the
#: probe's ladder below the original floor and re-ran it
#: (`logs/v3/60_station_reach_edge.log`, left arm at the shipped station, dy=0):
#: residual 6.0 mm at x = 0.18, 8.3 mm at x = 0.16, 20.4 mm at x = 0.14,
#: 34.6 mm at x = 0.12 and 50.8 mm at x = 0.10 - so the *delivered* edge is
#: **outside** the 6 mm catch-up tolerance. The line still runs 9/10 x5 on this
#: supply: the far edge is rare (the selector's floor and the schedule keep the
#: catch on the stocked segment over x = 0.20-0.36) and the post-descent solver
#: absorbs the residual where an edge fruit is caught. The probe run was cut
#: short after the left-arm rows (the right arm's low-edge rows were not
#: measured; its dy=0 ladder above x = 0.18 matches the left to 0.1-0.2 mm).
#: The pre-v9 line spawned within +/-5 mm of the centre but the belt drifted
#: fruit to x = 0.308..0.394 (measured), which is why the old line worked and
#: the first scattered pass (+/-0.12, to x = 0.46) did not: 1/10 with 8 s
#: failed descents (`logs/v1/20_rate_supply_1.log`).
SUPPLY_X_MIN = 0.20
SUPPLY_X_MAX = 0.36
#: Default grade mix. With the v9/V2 two-line lane rule (grade A -> the left
#: arm, every other grade -> the right) a uniform 1/3 A draw starves the left
#: lane, and the W3 owner decision makes the routing pure per arm (left = A,
#: right = B, C unsorted), so the mix has to keep both arms fed: a 50/30/20
#: split gives the A lane half the 16-slot pool while keeping B and C present
#: as classes (C rides the line unsorted).
SUPPLY_GRADES = {"A": 0.5, "B": 0.3, "C": 0.2}
#: W3 balanced mix for the pure per-arm routing (left = A only, right = B
#: only, C unsorted). The shipped 50/30/20 was designed for the old
#: A-vs-rest lane rule; under pure routing the right arm draws only 30 % of
#: the pool and is structurally starved (measured: right idle 75 % of its
#: span with the capture token on). The two-line wave scenario therefore
#: defaults to A:0.375/B:0.375/C:0.25 (6/6/4 over pool 16); the single-arm
#: line keeps the shipped 50/30/20 and `FRUIT_SUPPLY_GRADES` overrides both.
SUPPLY_GRADES_BALANCED = {"A": 0.375, "B": 0.375, "C": 0.25}

#: Dense-sheet supply (owner correction 2026-10-10). The v9/V1 scattered supply
#: was sparse (one fruit per 0.10-0.35 m sampled gap); the first W3 pass made
#: it spaced bursts (5 fruit at 0.10-0.18 m, then a 0.70-1.00 m empty gap).
#: The owner rejected the empty gaps: the supply must be a **continuous dense
#: sheet of overlapping clusters, back-to-back**. The shipped schedule is now a
#: cluster of `wave_size` fruit at 0.10-0.16 m gaps whose *cluster-boundary*
#: gap (0.09-0.12 m) is at or below the within-cluster band, so there is no
#: empty stretch anywhere on the line - the clusters merge into one sheet.
#: Every gap stays above `_release_clear`'s 0.08 m separation rule, so no
#: scheduled slot is refused. `FRUIT_SUPPLY_WAVE=0` restores the v9/V1
#: sampled-gap line bit-for-bit; the single-arm line defaults it off.
SUPPLY_WAVE_SIZE = 5
SUPPLY_WAVE_GAP_MIN = 0.10
SUPPLY_WAVE_GAP_MAX = 0.16
SUPPLY_WAVE_SEP_MIN = 0.09
SUPPLY_WAVE_SEP_MAX = 0.12

#: 2D scattered-sheet supply (W6-A owner directive). The wave/scatter schedules
#: are still single-file: every release slot carries one fruit, so from the belt
#: direction the line reads one-by-one. The patch schedule places **slices**
#: every ~slice_min..slice_max metres along the belt and each slice carries 1-2
#: fruit **abreast** (same along position, different lateral x), with the pair
#: probability `patch_pair` (~0.5-0.7). A pair's lateral separation is drawn in
#: `patch_sep_min..patch_sep_max`; the floor is above `_release_clear`'s 0.08 m
#: separation rule, so no two live fruit are ever closer than 0.08 m in the
#: belt plane (a same-slice pair is separated laterally, a cross-slice pair
#: along the belt). `_release_clear` gets the pair exception: a slot whose along
#: position is within 0.08 m of a live fruit is still released when the lateral
#: separation holds - that is the 2D reading. `FRUIT_SUPPLY_PATCH=0` (default)
#: leaves every existing schedule byte-reproducible: none of the patch draws
#: happen and `respawn`/`_release_clear` behave exactly as before.
SUPPLY_PATCH_SLICE_MIN = 0.14
SUPPLY_PATCH_SLICE_MAX = 0.22
SUPPLY_PATCH_PAIR = 0.6
SUPPLY_PATCH_SEP_MIN = 0.085
SUPPLY_PATCH_SEP_MAX = 0.12

#: Dense 2D "bed" supply (P32 phase 1, `FRUIT_SUPPLY_BED`, default off). The
#: owner's directive (2026-10-22) is that the belt read like a real grading line
#: packed with fruit - many abreast, a 2D bed, "enough fruit to serve as
#: candidates". The patch sheet is 1-2 abreast every 0.14-0.22 m (~8.9 fruit/m);
#: the bed is 3 measured reach columns (x = 0.20/0.28/0.36, `174`/`183`) released
#: as **rows**: the two edge columns abreast at the same along (a 0.16 m pair,
#: always corridor-safe) plus the middle column staggered by half a row pitch
#: (0.13-0.15 m since the 2026-10-22 owner decision) and only when its diagonal
#: clears the pair rule. The photo's
#: *touching* pack is not graspable by the open parallel jaw, so a row is
#: released only when the whole live bed satisfies the +/-0.066 m corridor rule
#: and the legacy 0.08 m floor; a row that cannot clear is shifted upstream
#: within a bound, and finally skipped (`supply_skipped` plus the lazy
#: `bed_refused`). The geometry and the schedule live in the pxr-free `bed.py`
#: so `scripts/211_bed_audit.py` reproduces them with plain `python3`.
#: Precedence when several schedules are set: bed > patch > wave > scatter.


def _default_grade_weight(grade: str, balanced: bool) -> float:
    """Default grade weight: balanced on the pure-routing two-line scenario.

    The two-line wave scenario sorts left=A / right=B only, and the shipped
    50/30/20 mix starves the B arm; the balanced 37.5/37.5/25 default lives
    beside `SUPPLY_GRADES_BALANCED`. Any explicit `FRUIT_SUPPLY_GRADES` still
    wins (it is parsed by `_mix_env` after this default).
    """
    table = SUPPLY_GRADES_BALANCED if balanced else SUPPLY_GRADES
    return float(table.get(grade, 1.0))


def _mix_env(name: str, keys, default: tuple[tuple[str, float], ...]):
    """Parse a ``KEY:WEIGHT,...`` environment mix, falling back to `default`."""
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        weights = {
            key.strip(): float(value)
            for key, _, value in (item.partition(":") for item in raw.split(","))
        }
    except ValueError:
        weights = {}
    if set(weights) != set(keys) or any(weight <= 0.0 for weight in weights.values()):
        say(
            f"[supply] warning: cannot use {name}={raw!r} "
            f"(expected all of {sorted(keys)} as NAME:WEIGHT); using default"
        )
        return default
    return tuple((str(key), float(weights[key])) for key in keys)


def _mix_allocate(weights: tuple[tuple[str, float], ...], total: int) -> list[str]:
    """Largest-remainder allocation of `total` slots to a weighted mix.

    Examples: ``A:0.5,B:0.3,C:0.2`` over 16 -> 8/5/3; eight equal classes over
    16 -> two each. Ties keep the caller's order, so a given mix spec always
    yields the same composition (the pool mix is deterministic; only the
    arrival order is drawn).
    """
    weight_sum = sum(weight for _, weight in weights)
    if total <= 0 or weight_sum <= 0.0:
        return [key for key, _ in weights][: max(0, total)]
    quotas = [(key, total * weight / weight_sum) for key, weight in weights]
    counts = {key: int(quota) for key, quota in quotas}
    missing = total - sum(counts.values())
    for key, quota in sorted(quotas, key=lambda item: -(item[1] - int(item[1])))[:missing]:
        counts[key] += 1
    out: list[str] = []
    for key, _ in weights:
        out.extend([key] * counts[key])
    return out


@dataclass(frozen=True)
class SupplyPlan:
    """Resolved scattered-supply parameters (env ``FRUIT_SUPPLY_*``)."""

    scatter: bool
    pool: int
    gap_min: float
    gap_max: float
    x_min: float
    x_max: float
    along_jitter: float
    stream: bool
    burst_max: int
    target: int
    target_from: float
    grades: tuple[tuple[str, float], ...]
    classes: tuple[tuple[str, float], ...]
    #: Dense-sheet schedule (W3 + owner correction). `wave=False` reproduces
    #: the v9/V1 sampled-gap line byte-for-byte; `wave=True` draws
    #: `wave_gap_*` within a cluster and `wave_sep_*` at the cluster boundary
    #: (kept small - clusters run back-to-back, no empty gaps), in the same
    #: seeded RNG stream.
    wave: bool = False
    wave_size: int = SUPPLY_WAVE_SIZE
    wave_gap_min: float = SUPPLY_WAVE_GAP_MIN
    wave_gap_max: float = SUPPLY_WAVE_GAP_MAX
    wave_sep_min: float = SUPPLY_WAVE_SEP_MIN
    wave_sep_max: float = SUPPLY_WAVE_SEP_MAX
    #: 2D scattered-sheet schedule (W6-A). `patch=True` replaces the single-
    #: file gap schedule with along-slices of 1-2 fruit abreast; patch draws
    #: are gated so `patch=False` reproduces every existing supply byte-for-byte.
    patch: bool = False
    patch_slice_min: float = SUPPLY_PATCH_SLICE_MIN
    patch_slice_max: float = SUPPLY_PATCH_SLICE_MAX
    patch_pair: float = SUPPLY_PATCH_PAIR
    patch_sep_min: float = SUPPLY_PATCH_SEP_MIN
    patch_sep_max: float = SUPPLY_PATCH_SEP_MAX
    #: Dense 2D bed schedule (P32 phase 1). `bed=True` replaces the single-file
    #: gap schedule with the row lattice planned by `bed.BedSchedule` (an
    #: abreast edge pair per row + a conditional staggered middle); `bed_plan`
    #: carries the resolved geometry. Default off: no bed draw happens and
    #: `_release_gap`/`respawn` behave exactly as before.
    bed: bool = False
    bed_plan: BedPlan | None = None
    #: P4-C1 H1 trickle feed (2026-10-16, default 0 = off/byte-identical).
    #: `FRUIT_SUPPLY_TRICKLE_LATE_S = capS`: in `_pump_supply`, a due slice
    #: whose virtual lateness exceeds the cap is consumed-and-skipped instead
    #: of delivered 2-4 s late at a position that is already below the moving
    #: catch's ~0.40 m selection floor by poll time. The schedule still draws
    #: one gap per due slot, so the mean due rate is unchanged; only the
    #: stale backlog is dropped (`supply_skipped`, plus the lazily-created
    #: `supply_trickled` counter). 0.0 keeps the shipped path byte-for-byte.
    trickle_late_s: float = 0.0

    @classmethod
    def from_env(cls, cfg: SceneConfig) -> "SupplyPlan":
        def number(name: str, default) -> float:
            raw = os.environ.get(name)
            if raw is None:
                return float(default)
            try:
                return float(raw)
            except ValueError:
                say(f"[supply] warning: {name}={raw!r} is not a number; using {default}")
                return float(default)

        scatter = os.environ.get("FRUIT_SUPPLY_SCATTER", "1") == "1"
        gap_min = max(0.02, number("FRUIT_SUPPLY_GAP_MIN", SUPPLY_GAP_MIN))
        gap_max = max(gap_min, number("FRUIT_SUPPLY_GAP_MAX", SUPPLY_GAP_MAX))

        def band(name: str, default_lo, default_hi, floor: float):
            """Parse a `LO,HI` band (or a scalar as centre +/-0.04), clamped at `floor`."""
            raw = os.environ.get(name)
            if raw is None:
                return float(default_lo), float(default_hi)
            try:
                if "," in raw:
                    lo_raw, hi_raw = raw.split(",", 1)
                    lo, hi = float(lo_raw), float(hi_raw)
                else:
                    mid = float(raw)
                    lo, hi = mid - 0.04, mid + 0.04
            except ValueError:
                say(
                    f"[supply] warning: {name}={raw!r} is not a length or LO,HI; "
                    "using the default"
                )
                return float(default_lo), float(default_hi)
            lo = max(floor, lo)
            return lo, max(lo, hi)

        wave_default = (
            "1"
            if scatter and os.environ.get("FRUIT_BIARM_TWOLINE", "0") == "1"
            else "0"
        )
        wave = scatter and os.environ.get("FRUIT_SUPPLY_WAVE", wave_default) == "1"
        wave_gap_min = max(
            0.085, number("FRUIT_SUPPLY_WAVE_GAP_MIN", SUPPLY_WAVE_GAP_MIN)
        )
        wave_gap_max = max(
            wave_gap_min, number("FRUIT_SUPPLY_WAVE_GAP_MAX", SUPPLY_WAVE_GAP_MAX)
        )
        # The cluster-boundary gap is deliberately kept at (or below) the
        # within-cluster band: the owner corrected the spaced-burst schedule
        # into a continuous dense sheet, so the boundary band must NOT be
        # floored above the within gap. Only `_release_clear`'s 0.08 m
        # separation rule is a hard floor (a smaller gap would be refused).
        wave_sep_min = max(
            0.085, number("FRUIT_SUPPLY_WAVE_SEP_MIN", SUPPLY_WAVE_SEP_MIN)
        )
        wave_sep_max = max(
            wave_sep_min, number("FRUIT_SUPPLY_WAVE_SEP_MAX", SUPPLY_WAVE_SEP_MAX)
        )
        # 2D scattered-sheet schedule (W6-A). It needs the scattered feeder
        # machinery (stream pump, recycle), so `FRUIT_SUPPLY_PATCH=1` without
        # `FRUIT_SUPPLY_SCATTER=1` is ignored with a warning rather than
        # silently changing the fixed line.
        patch_env = os.environ.get("FRUIT_SUPPLY_PATCH", "0") == "1"
        patch = bool(scatter and patch_env)
        if patch_env and not scatter:
            say(
                "[supply] warning: FRUIT_SUPPLY_PATCH=1 requires "
                "FRUIT_SUPPLY_SCATTER=1; ignored"
            )
        patch_slice_min, patch_slice_max = band(
            "FRUIT_SUPPLY_PATCH_SLICE",
            SUPPLY_PATCH_SLICE_MIN,
            SUPPLY_PATCH_SLICE_MAX,
            0.085,
        )
        patch_pair = min(
            1.0, max(0.0, number("FRUIT_SUPPLY_PATCH_PAIR", SUPPLY_PATCH_PAIR))
        )
        patch_sep_min, patch_sep_max = band(
            "FRUIT_SUPPLY_PATCH_SEP",
            SUPPLY_PATCH_SEP_MIN,
            SUPPLY_PATCH_SEP_MAX,
            0.085,
        )
        # P1 supply-density lever (the owner's #1: the arms wait too long -
        # the W6-B/R6 decomposition put 44-45 % of the interval in the
        # selection+arrival-wait family, and the starved-slot counts are the
        # starvation). `FRUIT_SUPPLY_PATCH_DENSITY` (D, default 1.0) raises the
        # sheet density: the along-slice gaps divide by D (the 0.085 m floor is
        # `_release_clear`'s 0.08 m separation rule plus a margin - a smaller
        # gap would be refused) and the abreast probability rises toward 1 (at
        # D >= 2 every slice carries a pair). At D=1.5 the patch sheet goes
        # from ~8.9 to ~15 fruit per belt metre.
        #
        # **P2 (2026-10-15): the same D also scales the wave schedule's two gap
        # bands** (the within-cluster `wave_gap_*` and the cluster-boundary
        # `wave_sep_*`, both floored at the same 0.085 m). The first transfer
        # attempt exposed why this is needed: a config with BOTH
        # `FRUIT_SUPPLY_WAVE=1` and `FRUIT_SUPPLY_PATCH=1` runs the *patch*
        # schedule (patch wins the branch), so "the wave sheet at D=1.5" had
        # silently re-run the patch sheet at D=1.5 - bit-identical to the
        # patch run, which is how the mistake was caught
        # (`logs/p2d/RESULTS.md` section 3). The knob keeps its `PATCH_` name
        # for compatibility; it reads on **either** scattered schedule and
        # D=1.0 is byte-identical on both.
        patch_density = max(1.0, number("FRUIT_SUPPLY_PATCH_DENSITY", 1.0))
        if patch_density != 1.0:
            patch_slice_min = max(0.085, patch_slice_min / patch_density)
            patch_slice_max = max(patch_slice_min, patch_slice_max / patch_density)
            patch_pair = min(
                1.0, patch_pair + (1.0 - patch_pair) * min(patch_density - 1.0, 1.0)
            )
            if wave and patch:
                # Both flags set: `patch` wins the schedule branch, so the wave
                # bands are inert. Say so - the P2 battery hit exactly this
                # (a "wave at D=1.5" config that silently re-ran the patch sheet;
                # the tell was bit-identical readouts), and the density banner
                # used to print the *inert* wave bands on a patch run, which
                # misled the log reader and broke `compare_streams.py`'s
                # line-for-line comparison.
                say(
                    "[supply] warning: FRUIT_SUPPLY_WAVE=1 with "
                    "FRUIT_SUPPLY_PATCH=1; the PATCH schedule wins"
                )
            if wave and not patch:
                wave_gap_min = max(0.085, wave_gap_min / patch_density)
                wave_gap_max = max(wave_gap_min, wave_gap_max / patch_density)
                wave_sep_min = max(0.085, wave_sep_min / patch_density)
                wave_sep_max = max(wave_sep_min, wave_sep_max / patch_density)
                say(
                    f"[supply] wave density x{patch_density:g}: gap "
                    f"{wave_gap_min:.3f}-{wave_gap_max:.3f} m, boundary "
                    f"{wave_sep_min:.3f}-{wave_sep_max:.3f} m"
                )
            if patch:
                say(
                    f"[supply] patch density x{patch_density:g}: slice "
                    f"{patch_slice_min:.3f}-{patch_slice_max:.3f} m, pair "
                    f"{patch_pair:.2f}"
                )
        # The balanced A:B:C mix follows the two-line scenario, whether it runs
        # the wave or the patch schedule there (`FRUIT_SUPPLY_GRADES` still wins).
        # Dense 2D bed (P32 phase 1). It shares the scattered feeder's stream
        # pump/backlog machinery, so like the patch it needs
        # `FRUIT_SUPPLY_SCATTER=1`; the schedule branch order below is
        # bed > patch > wave > scatter, and the create_pool banner names the one
        # that actually runs.
        bed_env = os.environ.get("FRUIT_SUPPLY_BED", "0") == "1"
        bed = bool(scatter and bed_env)
        if bed_env and not scatter:
            say(
                "[supply] warning: FRUIT_SUPPLY_BED=1 requires "
                "FRUIT_SUPPLY_SCATTER=1; ignored"
            )
        if bed and patch_env:
            # Precedence: bed > patch > wave > scatter. `patch` resolves off so
            # exactly one schedule flag is set (the pump's branch order would
            # also pick the bed first, but then the banner would print an inert
            # patch=on line - the same confusion the P2 density battery hit).
            patch = False
            say(
                "[supply] warning: FRUIT_SUPPLY_BED=1 with "
                "FRUIT_SUPPLY_PATCH=1; the BED schedule wins"
            )
        elif bed and os.environ.get("FRUIT_SUPPLY_WAVE", "") == "1":
            say(
                "[supply] warning: FRUIT_SUPPLY_BED=1 with "
                "FRUIT_SUPPLY_WAVE=1; the BED schedule wins"
            )
        # The bed's bigger pool is its own knob (`FRUIT_SUPPLY_BED_POOL`, 40):
        # rows deliver 2-3 fruit every 0.13-0.15 m, so a packed belt holds 19-24
        # live bodies and the pool must leave a burst's worth of rows parked
        # (a 28-fruit pool - the belt's own capacity - made 57 % of the real
        # loop's draws recycle a *live* body; see `bed.BED_POOL`). An explicit
        # `FRUIT_SUPPLY_POOL` still wins, and no legacy schedule reads the bed
        # pool, so every existing pool stays byte-identical.
        bed_plan = BedPlan.from_env(cfg) if bed else None
        if bed and "FRUIT_SUPPLY_POOL" not in os.environ and bed_plan is not None:
            pool_default = float(bed_plan.pool)
        else:
            pool_default = float(cfg.num_fruits)
        # The approach-segment top-up places a fruit at `spawn_y` with a drawn
        # lateral offset, which would break the bed's lattice and its corridor
        # rule. The bed packs itself, so the top-up is refused (with a warning)
        # rather than silently producing an off-lattice slot.
        target = max(0, int(number("FRUIT_SUPPLY_TARGET", 0)))
        if bed and target > 0:
            say(
                "[supply] warning: FRUIT_SUPPLY_TARGET is not used by the bed "
                "schedule (it packs its own slots); ignored"
            )
            target = 0
        balanced = (
            wave or patch or bed
        ) and os.environ.get("FRUIT_BIARM_TWOLINE", "0") == "1"

        # P1c species lock: `FRUIT_SUPPLY_SPECIES=<name>` restricts the pool to
        # one species (the composition-controlled comparison); unset = shipped.
        species_only = os.environ.get("FRUIT_SUPPLY_SPECIES", "").strip()
        if species_only:
            if species_only in cfg.fruit_dimensions:
                say(f"[supply] species lock: {species_only} only")
            else:
                say(
                    f"[supply] warning: FRUIT_SUPPLY_SPECIES={species_only!r} is "
                    f"not a known species ({sorted(cfg.fruit_dimensions)}); ignored"
                )
                species_only = ""
        default_grades = tuple(
            (grade, _default_grade_weight(grade, balanced)) for grade in cfg.grades
        )
        x_min = number("FRUIT_SUPPLY_X_MIN", SUPPLY_X_MIN)
        x_max = max(x_min, number("FRUIT_SUPPLY_X_MAX", SUPPLY_X_MAX))
        return cls(
            scatter=scatter,
            pool=max(1, int(number("FRUIT_SUPPLY_POOL", pool_default))),
            gap_min=gap_min,
            gap_max=gap_max,
            x_min=x_min,
            x_max=x_max,
            along_jitter=max(0.0, number("FRUIT_SUPPLY_ALONG_JITTER", 0.0)),
            stream=os.environ.get("FRUIT_SUPPLY_STREAM", "1") == "1",
            burst_max=max(1, int(number("FRUIT_SUPPLY_BURST_MAX", 6))),
            target=target,
            target_from=max(0.0, number("FRUIT_SUPPLY_TARGET_FROM", 0.35)),
            grades=_mix_env("FRUIT_SUPPLY_GRADES", cfg.grades, default_grades),
            classes=_mix_env(
                "FRUIT_SUPPLY_CLASSES",
                cfg.fruit_dimensions,
                # P1c (2026-10-16) species lock. The composition-controlled test
                # needs a supply whose presented class multiset is fixed BY
                # CONSTRUCTION, and neither mix knob can express it:
                # `FRUIT_SUPPLY_CLASSES` requires every species to be listed with
                # a POSITIVE weight (`_mix_env` rejects <= 0), so a one-species
                # pool is unreachable; `FRUIT_SUPPLY_GRADES` is the grade mix,
                # not the species mix. So the lock lives here, as a restriction
                # of the *default* species mix - an explicit `FRUIT_SUPPLY_CLASSES`
                # still wins, exactly as before. Default off: unset behaves
                # identically to the shipped all-species pool.
                ((species_only, 1.0),) if species_only else tuple(
                    (name, 1.0) for name in cfg.fruit_dimensions
                ),
            ),
            wave=bool(wave),
            wave_size=max(1, int(number("FRUIT_SUPPLY_WAVE_SIZE", SUPPLY_WAVE_SIZE))),
            wave_gap_min=wave_gap_min,
            wave_gap_max=wave_gap_max,
            wave_sep_min=wave_sep_min,
            wave_sep_max=wave_sep_max,
            patch=patch,
            patch_slice_min=patch_slice_min,
            patch_slice_max=patch_slice_max,
            patch_pair=patch_pair,
            patch_sep_min=patch_sep_min,
            patch_sep_max=patch_sep_max,
            bed=bed,
            bed_plan=bed_plan,
            trickle_late_s=max(0.0, number("FRUIT_SUPPLY_TRICKLE_LATE_S", 0.0)),
        )

    def sample_gap(self, rng: random.Random) -> float:
        """One along-the-line gap [m] between consecutive released fruit."""
        return rng.uniform(self.gap_min, self.gap_max)

    @property
    def schedule(self) -> str:
        """Name of the schedule that owns the branch: bed/patch/wave/scatter.

        The branch order in `_release_gap`/`_pump_supply` is the same, so this
        is what a log's banner or the offline audit should print (the bed is the
        only schedule that resolves a lower-precedence flag off, so at most one
        of `bed`/`patch`/`wave` is true).
        """
        if self.bed:
            return "bed"
        if self.patch:
            return "patch"
        if self.wave:
            return "wave"
        return "scatter"


# --------------------------------------------------------------------------- #
# P50 phase 2 (2026-10-27, **default off**): the per-instance release-offset
# compensation at `respawn`.
#
# Measured (`logs/p50/OFFSET_TABLE.md`): the delivered lateral x is
#
#     x_delivered = x_spawn + offset(instance)
#
# with the transport contributing **0.00 mm** (475 transits, P38; 0.09 mm over
# 215-224 ticks on the delivered path) and the offset a **per-instance
# constant** - two passes over 48 cells are bit-identical (spread 0.00 mm) and
# the shipped line agrees to <= 0.5 mm on 55/65 attributed releases. It is
# **not** a function of (species, diameter): two strawberries 0.9 mm apart in
# diameter read +20.0 and -24.3 mm, and a pooled fit leaves a 10.19 mm residual
# sd, so the table has to be measured **per pool** (OFFSET_TABLE.md section 5).
#
# With `FRUIT_RELEASE_OFFSET=1` the value the schedule already drew is
# post-processed inside `respawn`:
#
#     x_spawn = planned_x - offset(instance) / 1000
#
# so the *delivered* x lands back on the planned x. **The draw and the RNG
# stream are untouched** - the compensation shifts the value `respawn` already
# drew - which is what makes an A/B against `=0` a comparison of the *same
# supply draws* with only the physical x differing (PREREG section 2). The
# spawn band is deliberately **not clamped**: the measured excursion is
# 0.165-0.387 m, still inside the belt (x 0.11-0.57) with >= 45 mm to the near
# edge; the band the metric is about is the *delivered* one.
#
# Scope gate (PREREG section 2, measured reason): the patch and bed schedules
# put two fruit **abreast** 0.085-0.12 m apart, so a +-55 mm per-instance
# lateral shift would change a pair's separation. Those schedules are skipped
# and counted (`offset_scoped_off`). Inside their scope the single-file
# schedules (scatter/wave/fixed) are compensated on every release - the pump's
# slot, its top-up and the `release_next` recycle all go through `respawn`.
#
# Unset contract: with the knob unset no table is read, no draw changes, no
# line and no `stats` key is added - the tree is byte-identical (proven by the
# arm M4, not asserted). The table is `{signature: offset_mm}` with
# `signature = "<species>|<diameter to 0.1 mm>"` (the instance identity the pool
# exposes); a missing signature leaves that instance **uncompensated** and is
# counted (`offset_misses`), never silently zeroed. `FRUIT_RELEASE_OFFSET_DIAG=1`
# adds one print-only `[offset] release` row per release in **both** arms (the
# paired planned/spawn read). Tables are generated per pool by
# `logs/p50/p2/make_offset_table.py`.
# --------------------------------------------------------------------------- #
RELEASE_OFFSET_ACTIVE = os.environ.get("FRUIT_RELEASE_OFFSET", "0").strip() == "1"
RELEASE_OFFSET_TABLE_PATH = os.environ.get("FRUIT_RELEASE_OFFSET_TABLE", "").strip()
RELEASE_OFFSET_DIAG = os.environ.get("FRUIT_RELEASE_OFFSET_DIAG", "0").strip() == "1"


def release_offset_signature(sample: FruitSample) -> str:
    """The pool-instance identity the P50 offset table is keyed on.

    `species|diameter to 0.1 mm` - the identity the pool exposes without adding
    a field to the sample. `rescale` (the collector's recycle) can rewrite a
    sample's category/diameter, in which case its signature changes and the
    release is counted as a miss instead of being compensated with a stale
    value.
    """
    return f"{sample.category}|{sample.diameter * 1000.0:.1f}"


def load_release_offset_table(path: str) -> dict[str, float]:
    """Read a P50 per-pool offset table (`{signature: offset_mm}`).

    Accepts either the flat map or the generator's envelope
    (`{"schema": ..., "offsets": {...}, "provenance": {...}}`), so a hand-written
    table and a generated one are the same object here.
    """
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    raw = payload.get("offsets") if isinstance(payload, dict) else None
    if raw is None:
        raw = payload
    if not isinstance(raw, dict) or not raw:
        raise RuntimeError(
            f"FRUIT_RELEASE_OFFSET_TABLE={path}: expected a non-empty "
            "{signature: offset_mm} map (or an object with an 'offsets' map)"
        )
    table: dict[str, float] = {}
    for key, value in raw.items():
        try:
            table[str(key)] = float(value)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                f"FRUIT_RELEASE_OFFSET_TABLE={path}: entry {key!r} is not a "
                f"number in mm ({value!r})"
            ) from exc
    return table


class FruitSpawner:
    """Owns a fixed pool of fruit rigid bodies recycled onto the belt."""

    # Approximate visual colour per category (roughness differs for fuzzy fruit).
    CATEGORY_STYLE = {
        "strawberry": ((0.85, 0.12, 0.14), 0.55),
        "lychee": ((0.80, 0.25, 0.22), 0.65),
        "kiwi": ((0.45, 0.32, 0.16), 0.85),
        "tomato": ((0.88, 0.20, 0.12), 0.35),
        "apple": ((0.80, 0.10, 0.12), 0.30),
        "orange": ((0.92, 0.50, 0.10), 0.75),
        "peach": ((0.95, 0.60, 0.45), 0.80),
        "pear": ((0.72, 0.78, 0.25), 0.45),
    }

    def __init__(self, stage: Usd.Stage, cfg: SceneConfig, root: str = "/World/Fruits", seed: int = 0):
        self.stage = stage
        self.cfg = cfg
        self.root = root
        self.seed = int(seed)
        self.rng = random.Random(seed)
        #: Resolved scattered-supply parameters (v9/V1). `scatter=False`
        #: reproduces the pre-v9 fixed line bit-for-bit.
        self.supply = SupplyPlan.from_env(cfg)
        #: Dense 2D bed schedule (P32 phase 1, default off). Its own RNG stream
        #: (`BedSchedule`), so nothing here touches `self.rng`: the legacy
        #: arrival streams draw exactly the same numbers with the knob unset.
        self.bed_schedule = (
            BedSchedule(self.supply.bed_plan, seed=self.seed)
            if self.supply.bed and self.supply.bed_plan is not None
            else None
        )
        self.samples: list[FruitSample] = []
        self.active: list[FruitSample] = []
        self._rigids: dict[int, RigidPrim] = {}
        #: P45: printed the one-shot mass/inertia read-back already.
        self._mass_probe_done = False
        self._attach_offset: dict[int, np.ndarray] = {}
        self._cursor = 0
        self._next_release = 0.0
        #: Wave schedule cursor: how many gaps of the current burst have been
        #: drawn. Reset at the between-wave gap, so a burst is always exactly
        #: `wave_size` releases wide even when releases are skipped.
        self._wave_count = 0
        #: Index of the fruit the task is currently working on: it must never be
        #: recirculated, otherwise the pads end up chasing a *parked* body (measured,
        #: logs/351: pads and "fruit" both at x = -1.5 m while the arm was at the
        #: pick station).
        #: Along-position downstream of which a mid-belt fruit may be recycled
        #: invisibly (the two-line scheduler moves it past its downstream
        #: station; see `run_bimanual` in `tasks.py`).
        self.recycle_y = float(cfg.pick_y)
        self.protected: int | None = None
        #: The bimanual scheduler protects one fruit per arm; `protected` stays
        #: the single-arm interface (the policy env and the collector set it
        #: directly), and both are honoured by `update`.
        self.protected_indices: set[int] = set()
        self._waited: dict[int, float] = {}
        self._last_sim_time = 0.0
        #: Seconds each fruit has been sitting still in a discharge tray; the
        #: spawner recycles it once the dwell passes `cfg.output_tray_dwell_s`.
        self._tray_dwell: dict[int, float] = {}
        self.stats = {"released": 0, "reached_end": 0, "fell_off": 0, "discharged": 0}
        #: Release slots the scattered feeder skipped: either the slot's virtual
        #: position was already past the station (the feeder was not called
        #: while an attempt ran) or the spot was not clear of a live fruit.
        self.stats["supply_skipped"] = 0
        #: P4-C1 H1 pure-reporting diagnostic (`FRUIT_SUPPLY_DIAG=1`, default
        #: off). Read once here - not per `update` call - so the shipped path
        #: pays one attribute check at most and never touches the env or the
        #: control loop. When on, `_pump_supply` prints one `[supply-diag]`
        #: line per pump call that processed due slots: due / released /
        #: past-floor / trickle-stale / clear-refused / queue-interlock /
        #: pool-empty and the delivered lateness band.
        self._supply_diag = os.environ.get("FRUIT_SUPPLY_DIAG", "0") == "1"
        #: P32 phase A pure-reporting diagnostic (`FRUIT_BED_DIAG=1`, default
        #: off), bed only: one `[bed-pump]` line per pump call that processed
        #: due slots (the absolute clock, the schedule's due time and the lateness
        #: band) and one `[bed-row]` line per placed/refused row. Read once here,
        #: so the shipped path pays one attribute check per due slot and never
        #: touches the env or the control loop. `tasks.select_target` reads the
        #: same variable for its per-attempt `[bed-sel]` census, and the feeder
        #: probe (`scripts/214_bed_feeder_probe.py`) runs on both.
        self._bed_diag = os.environ.get("FRUIT_BED_DIAG", "0") == "1"
        #: P32 phase A bed-stock cap [m]: a bed row is never released further
        #: downstream than `spawn_y - this`, because a row released below the
        #: selection floor is not a candidate (it rides past the station). The
        #: pump's backlog deeper than this is dropped - see `_pump_supply`.
        self.supply_bed_stock_m = float(
            os.environ.get("FRUIT_SUPPLY_BED_STOCK_M", "0.16")
        )
        #: P32 phase A bed-stock depth: how many live bodies the approach band
        #: (`_bed_stock_depth`, 0.58 m from the release floor to the spawn) may
        #: hold before the pump holds its next row. **10 = the band's delivered
        #: design capacity**: 0.58 m / 0.14 m mean pitch = 4.1 rows x the
        #: measured 2.4 fruit per row (64 % middles) = 9.9. The shipped
        #: `FRUIT_QUEUE_MAX=6` is a *station-window* number (0.5 m in front of
        #: the gate, calibrated for the single-file lines) and applied to the
        #: bed's band it throttles the feeder to ~0.55 rows/s against a design
        #: 0.88 - measured as the 1/10 hole at band 6 with a 4 mm miss
        #: (`logs/p32/62_probe_hold.log` attempt 6). At 10 the band delivers the
        #: design rate and the station window still holds the shipped ~6 bodies.
        #: **Coupling (m6):** the capacity moves with the plan - the
        #: `_bed_stock_depth` band is `spawn_y + 0.05 - (pick_y + 0.10)` long,
        #: so a wider `FRUIT_SUPPLY_BED_ALONG_*` band or more columns needs a
        #: *larger* cap, and a narrower one a smaller. The env value is clamped
        #: to the band's geometric maximum (`bed_stock_capacity`, 13 at the
        #: shipped geometry), so a typo cannot pack more fruit into the band
        #: than it can hold; the default stays the measured 10.
        requested = int(os.environ.get("FRUIT_SUPPLY_BED_STOCK_MAX", "10"))
        capacity = self.bed_stock_capacity()
        # Bed off (`capacity == 0`): keep the requested value; the attribute is
        # only read on the bed path, so the legacy spawner's state is unchanged.
        self.supply_bed_stock_max = max(
            1, min(requested, capacity) if capacity > 0 else requested
        )
        #: P32 Gate-A residual R2, bed only: the stride of the scan-only
        #: end-of-line sweep (`scan_despawn`, called from the driver's
        #: `_step_sim`). The end-of-line recycle lived **only** inside `update`,
        #: which the driver calls at the attempt boundary, so between two pumps
        #: the belt kept carrying fruit past `despawn_y` and off the belt's
        #: physical end: measured as `fell_off` (5 on the cadence arm, 102 - 96
        #: of them past the end - on the 20-attempt boundary control) with
        #: `reached_end=0`. The bound is geometric, not tuned: the belt end
        #: (`belt_center[1] - belt_size[1]/2` = -0.80 m) is 0.10 m past
        #: `despawn_y` (-0.70 m), i.e. **0.83 s** of travel at the shipped
        #: 0.12 m/s, so any stride below that recycles a body while it is still
        #: on the belt. 0.25 s is a 3.3x margin and costs one fruit-pose read
        #: per live body every 30 ticks (pose reads are run-neutral; see
        #: AGENTS section 2).
        self.supply_bed_sweep_s = float(
            os.environ.get("FRUIT_SUPPLY_BED_SWEEP_S", "0.25")
        )
        self._despawn_stride = max(
            1, int(round(self.supply_bed_sweep_s * 120.0))
        )
        #: Control ticks accrued since the last sweep (`scan_despawn`).
        self._despawn_ticks = 0
        #: Set to a CleatedBelt so the cleats advance with the physics loop.
        self.belt = None
        #: P50 phase 2 (default off): the per-pool release-offset table. Resolved
        #: once here; with `FRUIT_RELEASE_OFFSET` unset nothing is read and the
        #: three counters below do not exist, so `stats` (and every offline
        #: comparison of it, e.g. `scripts/172_supply_selftest.py`) is unchanged.
        self._release_offsets: dict[str, float] = {}
        self._release_table_path = ""
        if RELEASE_OFFSET_ACTIVE:
            if not RELEASE_OFFSET_TABLE_PATH:
                raise RuntimeError(
                    "FRUIT_RELEASE_OFFSET=1 needs FRUIT_RELEASE_OFFSET_TABLE=<path>: "
                    "a missing table must not silently no-op (P50 PREREG section 2)"
                )
            self._release_table_path = RELEASE_OFFSET_TABLE_PATH
            self._release_offsets = load_release_offset_table(RELEASE_OFFSET_TABLE_PATH)
            self.stats["offset_shifted"] = 0
            self.stats["offset_misses"] = 0
            self.stats["offset_scoped_off"] = 0
        stage.DefinePrim(root, "Xform")

    # ------------------------------------------------------------------ #
    def create_pool(self) -> None:
        categories = list(self.cfg.fruit_dimensions.keys())
        if self.supply.scatter:
            pool = self.supply.pool
            grades = _mix_allocate(self.supply.grades, pool)
            classes = _mix_allocate(self.supply.classes, pool)
            # The composition is deterministic (every pool carries the designed
            # mix); only the arrival order is drawn, so a shuffle cannot make a
            # class vanish from a short run.
            self.rng.shuffle(classes)
            self.rng.shuffle(grades)
            for i in range(pool):
                self._create_fruit(i, classes[i], grade=grades[i])
            # Randomise the release order too: the cursor walks `self.samples`,
            # so without this the line replays the same class cycle.
            self.rng.shuffle(self.samples)
            counts: dict[str, int] = {}
            for name in classes:
                counts[name] = counts.get(name, 0) + 1
            # The schedule's own geometry in the one-line banner. The bed is a
            # **row** lattice, so the scatter line's `gaps=0.10-0.35 m` would be
            # a false claim there (P32 Gate-1 finding: the Oracle read the
            # banner and saw the wrong schedule); it prints the rows instead.
            if self.supply.bed and self.supply.bed_plan is not None:
                bed = self.supply.bed_plan
                mids = ",".join(
                    f"{bed.columns[i]:.2f}" for i in bed.middle_columns
                )
                geometry = (
                    "rows="
                    f"{len(bed.edge_columns)} abreast "
                    f"({bed.columns[bed.edge_columns[-1]] - bed.columns[bed.edge_columns[0]]:.2f} m)"
                    f" + conditional mid at x={mids} "
                    f"pitch={bed.along_min:.3f}-{bed.along_max:.3f} m"
                )
            else:
                geometry = (
                    f"gaps={self.supply.gap_min:.2f}-{self.supply.gap_max:.2f} m"
                )
            say(
                f"[supply] scatter pool={pool} seed={self.seed} "
                f"{geometry} "
                f"lateral x={self.supply.x_min:.2f}-{self.supply.x_max:.2f} m "
                f"stream={'on' if self.supply.stream else 'off'} "
                f"target={self.supply.target} "
                f"wave="
                + (
                    f"on size={self.supply.wave_size} "
                    f"gap={self.supply.wave_gap_min:.2f}-{self.supply.wave_gap_max:.2f} "
                    f"sep={self.supply.wave_sep_min:.2f}-{self.supply.wave_sep_max:.2f}"
                    if self.supply.wave and not self.supply.bed
                    else "off"
                )
                + " grades="
                + ",".join(f"{key}:{weight:g}" for key, weight in self.supply.grades)
                + " classes="
                + ",".join(f"{name}:{counts.get(name, 0)}" for name in categories)
                + (
                    f" patch=on slice={self.supply.patch_slice_min:.2f}-"
                    f"{self.supply.patch_slice_max:.2f} "
                    f"pair={self.supply.patch_pair:.2f} "
                    f"sep={self.supply.patch_sep_min:.3f}-"
                    f"{self.supply.patch_sep_max:.2f}"
                    if self.supply.patch
                    else ""
                )
            )
            # The bed names itself (the schedule actually running: bed > patch >
            # wave) and its geometry, so a battery log can be read without the
            # shell command. The knob-off stream carries no extra line.
            if self.supply.bed and self.supply.bed_plan is not None:
                plan = self.supply.bed_plan
                mid_lo = plan.admitted_radius(plan.diagonal(plan.along_min))
                mid_hi = plan.admitted_radius(plan.diagonal(plan.along_max))
                say(
                    "[supply] schedule: bed "
                    f"rows={len(plan.edge_columns)} abreast "
                    f"(edge pair {plan.columns[plan.edge_columns[-1]] - plan.columns[plan.edge_columns[0]]:.2f} m)"
                    f" + conditional mid "
                    f"columns={','.join(f'{x:.2f}' for x in plan.columns)} "
                    f"pitch={plan.along_min:.3f}-{plan.along_max:.3f} m "
                    f"(mid half a pitch downstream, joins only when its "
                    f"diagonal clears the pair rule: <= "
                    f"{2*mid_lo*100:.1f}-{2*mid_hi*100:.1f} cm dia) "
                    f"margin={plan.margin:.3f} m "
                    f"shift={plan.shift_max:.2f} m pool={self.supply.pool} "
                    "corridor=+/-0.066 m"
                )
            # P4-C1 H1 (default off): print the trickle state only when it is
            # active, so the shipped banner stream stays byte-identical.
            if self.supply.trickle_late_s > 0.0:
                say(
                    f"[supply] trickle feed: deliver only slices due within "
                    f"{self.supply.trickle_late_s:.2f}s of the pump; the stale "
                    "backlog is consumed as supply_skipped (consume-and-skip)"
                )
            if self._supply_diag:
                say("[supply] diag: per-pump released/refused lines on")
        else:
            for i in range(self.cfg.num_fruits):
                category = categories[i % len(categories)]
                self._create_fruit(i, category)
        # P12-A / P12-A.2: one banner when any real-property component is on,
        # so a battery log names its physics; the knob-off stream is
        # byte-identical (no line).
        banner = _physics_banner()
        if banner is not None:
            say(banner)
        # P45: one banner when the mass scale is set (unset prints nothing, so
        # the shipped stream is byte-identical).
        banner = _mass_scale_banner()
        if banner is not None:
            say(banner)
        # P50 (default off): one line naming the table and the pool coverage, so
        # a compensated log proves its own table applies to the pool it drew. No
        # line with the knob unset (byte-identical stream).
        if RELEASE_OFFSET_ACTIVE:
            signatures = [release_offset_signature(sample) for sample in self.samples]
            covered = [self._release_offsets[key] for key in signatures
                       if key in self._release_offsets]
            say(
                f"[offset] release compensation: table={self._release_table_path} "
                f"instances={len(covered)}/{len(signatures)} "
                f"offset_mm="
                + (f"{min(covered):+.1f}..{max(covered):+.1f}" if covered else "n/a")
                + " (x_spawn = planned_x - offset, single-file schedules only, "
                "spawn band not clamped)"
            )
        say(f"created {len(self.samples)} fruit rigid bodies")

    def _create_fruit(self, index: int, category: str, grade: str | None = None) -> None:
        lo, hi = self.cfg.fruit_dimensions[category]
        diameter = self.rng.uniform(lo, hi)
        # Mass roughly scales with volume; density ~ 700 kg/m^3 (fruit is buoyant).
        mass = float(700.0 * (4.0 / 3.0) * np.pi * (diameter / 2.0) ** 3)
        friction = self.rng.uniform(0.4, 1.1)

        path = f"{self.root}/Fruit_{index:02d}"
        # Real fruit geometry: a procedural mesh at the final size, authored with
        # no Scale op (PhysX mis-cooks scaled shapes - see WORKLOG).
        shape = FRUIT_SHAPES[category]
        base = shape.colors[self.rng.randrange(len(shape.colors))]
        colour = tuple(
            float(np.clip(c + self.rng.uniform(-0.05, 0.05), 0.0, 1.0)) for c in base
        )
        fruit_mesh = author_fruit(self.stage, path, shape, diameter, self.rng, colour)
        author_stem(self.stage, f"{path}_stem", shape, diameter, self.rng)

        xform = UsdGeom.Xformable(fruit_mesh)
        xform.ClearXformOpOrder()
        xform.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, -5.0))

        prim = fruit_mesh.GetPrim()
        # Mass follows the volume of the actual shape, not just the diameter.
        # P12-A/P12-A.2: the density is the measured real one when the mass
        # component is on (`fruit_density`; the 0.82 sphere-shape discount is
        # unchanged).
        mass = float(fruit_density(shape) * (4.0 / 3.0) * np.pi * (diameter / 2.0) ** 3 * 0.82)
        # P45: the mass-scale experiment. A **physics change, not a fidelity
        # claim** (`meshes.mass_scale`): the size, the mesh, the collider and the
        # pinch span stay exactly as they are, only the authored mass moves - and
        # because no fruit authors `physics:diagonalInertia`, PhysX derives the
        # tensor from that mass and the tensor scales with it. Unset skips the
        # multiply entirely, so the shipped float path cannot move.
        scale = mass_scale()
        if scale != 1.0:
            mass *= scale
        friction = self.rng.uniform(*shape.friction)
        UsdPhysics.RigidBodyAPI.Apply(prim)
        mass_api = UsdPhysics.MassAPI.Apply(prim)
        mass_api.CreateMassAttr().Set(mass)

        _author_fruit_physics_material(
            self.stage,
            prim,
            path,
            friction,
            self.rng.uniform(*restitution_range()),
            fruit_contact_stiffness(shape),
        )

        rigid_api = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
        rigid_api.CreateEnableCCDAttr().Set(False)
        # Sleeping is the reason a closing gripper can pass straight through a
        # fruit: a body PhysX has put to sleep is not woken by the approaching
        # finger, so the pads close to their commanded gap with zero contact.
        # FRUIT_NO_SLEEP=1 keeps every fruit awake (sleepThreshold 0 = never
        # sleep). Note it must be sleepThreshold, *not* stabilizationThreshold:
        # setting the latter to 0 leaves the body permanently stabilised, which
        # also ignores contacts (see scripts/43_fruit_vs_box.py).
        # Sleeping is the default-on guard whenever the kinematic gripper is in
        # use (a sleeping body is not woken by the approaching pads, which reads
        # as "the gripper closed on air"). FRUIT_NO_SLEEP=0 disables it.
        no_sleep = os.environ.get("FRUIT_NO_SLEEP")
        if no_sleep is None:
            no_sleep = "1" if os.environ.get("FRUIT_KINEMATIC_GRIPPER", "1") == "1" else "0"
        if no_sleep == "1":
            rigid_api.CreateSleepThresholdAttr().Set(0.0)
        tune_contact_body(prim)

        self.samples.append(
            FruitSample(
                index=index,
                prim_path=path,
                category=category,
                diameter=diameter,
                mass=mass,
                friction=friction,
                grade=self.rng.choice(self.cfg.grades) if grade is None else grade,
                ripeness=self.rng.uniform(0.4, 1.0),
                defective=self.rng.random() < 0.12,
                parked=False,
            )
        )

    # ------------------------------------------------------------------ #
    def refresh_rigids(self) -> None:
        """(Re)build rigid prim handles; call after the simulation starts."""
        for sample in self.samples:
            self._rigids[sample.index] = RigidPrim(sample.prim_path)
        self._probe_mass_inertia()

    def _probe_mass_inertia(self) -> None:
        """One-shot read-back of the authored mass and the derived inertia (P45).

        `logs/p45/MASS_CENSUS.md` §1.4 says the fruit authors `mass` **only**
        (`_create_fruit` / `rescale`, no `physics:diagonalInertia`), so PhysX
        derives the tensor from the collider's volume at that mass and a mass
        scale is also an **inertia** scale. That was a *documented* derivation,
        not a measurement, because nothing read the tensor back; this is the
        read. It runs **once**, at the rig-handle refresh before the attempt
        loop, and only when `FRUIT_MASS_SCALE` is set - so the shipped stream
        gets no line and no extra tensor call (the AGENTS rule about
        instrumentation in a control loop does not apply to a one-shot read
        that no attempt has started under, but a per-tick version would).

        `I/m` is the gyration radius squared; for the near-spherical hull it
        sits at `(2/5) R^2` with `R = d/2` and must be **identical across mass
        scales** - that is "the size did not move", read from physics rather
        than from the config.
        """
        scale = mass_scale()
        if scale == 1.0 or not self._rigids or self._mass_probe_done:
            return
        self._mass_probe_done = True
        masses: list[float] = []
        ratios: list[float] = []
        shape_ratios: list[float] = []
        for sample in self.samples:
            rigid = self._rigids.get(sample.index)
            if rigid is None:
                continue
            try:
                mass = float(np.asarray(rigid.get_masses(indices=[0])).reshape(-1)[0])
                tensor = np.asarray(rigid.get_inertias(indices=[0])).reshape(-1)
            except Exception as exc:  # noqa: BLE001 - report, never fatal
                say(f"[physics] mass readback (P45) unavailable: {exc}")
                return
            inertia = float(np.mean(tensor[[0, 4, 8]]))
            if mass <= 0.0 or inertia <= 0.0:
                say("[physics] mass readback (P45): non-positive mass/inertia")
                return
            masses.append(mass)
            ratio = inertia / mass
            ratios.append(ratio)
            shape_ratios.append(ratio / (0.4 * (sample.diameter / 2.0) ** 2))
        if not masses:
            return
        say(
            f"[physics] mass readback (P45): n={len(masses)} "
            f"mass={min(masses) * 1e3:.2f}-{max(masses) * 1e3:.2f} g "
            f"(/ {scale:g} = {min(masses) / scale * 1e3:.2f}-"
            f"{max(masses) / scale * 1e3:.2f} g unscaled), "
            f"I/m={min(ratios):.3e}-{max(ratios):.3e} m^2, "
            f"I/m / (2/5)R^2 = {min(shape_ratios):.2f}-{max(shape_ratios):.2f} "
            f"(1.00 = a sphere; the spread is the hull's own shape) - "
            f"the inertia follows the authored mass, sizes unchanged"
        )

    def rescale(self, sample: FruitSample, category: str, diameter: float) -> None:
        """Change a recycled fruit's category/size (rebuilds its mesh)."""
        lo, hi = self.cfg.fruit_dimensions[category]
        sample.category = category
        sample.diameter = float(np.clip(diameter, lo, hi))
        shape = FRUIT_SHAPES[category]
        sample.mass = float(
            fruit_density(shape) * (4.0 / 3.0) * np.pi * (sample.diameter / 2.0) ** 3 * 0.82
        )
        # P45: the *second* mass site - the recycled fruit. Miss this one and a
        # respawned fruit silently returns to full mass, which would make every
        # later attempt in a shard a different experiment. Same unset-skips rule
        # as `_create_fruit`; the inertia follows the authored mass by PhysX's
        # own derivation (no `physics:diagonalInertia` is authored here either).
        scale = mass_scale()
        if scale != 1.0:
            sample.mass *= scale
        sample.friction = self.rng.uniform(*shape.friction)
        sample.grade = self.rng.choice(self.cfg.grades)
        sample.ripeness = self.rng.uniform(0.4, 1.0)
        sample.defective = self.rng.random() < 0.12

        # Re-author the mesh at the new size rather than scaling the prim.
        stage = self.stage
        stem_path = f"{sample.prim_path}_stem"
        if stage.GetPrimAtPath(stem_path).IsValid():
            stage.RemovePrim(stem_path)
        stage.RemovePrim(sample.prim_path)
        base = shape.colors[self.rng.randrange(len(shape.colors))]
        colour = tuple(
            float(np.clip(c + self.rng.uniform(-0.05, 0.05), 0.0, 1.0)) for c in base
        )
        mesh = author_fruit(stage, sample.prim_path, shape, sample.diameter, self.rng, colour)
        author_stem(stage, stem_path, shape, sample.diameter, self.rng)
        xform = UsdGeom.Xformable(mesh)
        xform.ClearXformOpOrder()
        xform.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, -5.0))
        prim = mesh.GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(prim)
        UsdPhysics.MassAPI.Apply(prim).CreateMassAttr().Set(sample.mass)
        _author_fruit_physics_material(
            stage,
            prim,
            sample.prim_path,
            sample.friction,
            self.rng.uniform(*restitution_range()),
            fruit_contact_stiffness(shape),
        )
        tune_contact_body(prim)

    # ------------------------------------------------------------------ #
    # P50 phase 2: the per-instance release-offset compensation (default off)
    # ------------------------------------------------------------------ #
    def _release_offset(self, sample: FruitSample, x: float) -> float:
        """Return the spawn x for a planned x, through the P50 offset table.

        Inert (one boolean, no read, no line, no counter) unless
        `FRUIT_RELEASE_OFFSET=1` or the print-only `FRUIT_RELEASE_OFFSET_DIAG=1`
        is set. With the knob on: `x_spawn = planned - offset(instance)/1000`,
        **not clamped** (the measured excursion stays on the belt), skipped and
        counted on the patch/bed schedules (a pair's abreast separation must not
        move), and left uncompensated + counted on a table miss.
        """
        if not RELEASE_OFFSET_ACTIVE:
            if RELEASE_OFFSET_DIAG:
                say(
                    f"[offset] release idx={int(sample.index):02d} "
                    f"cat={sample.category:<10s} "
                    f"dia_mm={sample.diameter * 1000:6.1f} planned={x:+.5f} "
                    f"spawn={x:+.5f} off_mm=  +0.00 src=control"
                )
            return x
        if self.supply.patch or self.supply.bed:
            self.stats["offset_scoped_off"] += 1
            if RELEASE_OFFSET_DIAG:
                say(
                    f"[offset] release idx={int(sample.index):02d} "
                    f"cat={sample.category:<10s} "
                    f"dia_mm={sample.diameter * 1000:6.1f} planned={x:+.5f} "
                    f"spawn={x:+.5f} off_mm=  +0.00 src=scoped-off"
                )
            return x
        offset_mm = self._release_offsets.get(release_offset_signature(sample))
        if offset_mm is None:
            self.stats["offset_misses"] += 1
            if RELEASE_OFFSET_DIAG:
                say(
                    f"[offset] release idx={int(sample.index):02d} "
                    f"cat={sample.category:<10s} "
                    f"dia_mm={sample.diameter * 1000:6.1f} planned={x:+.5f} "
                    f"spawn={x:+.5f} off_mm=  +0.00 src=miss"
                )
            return x
        self.stats["offset_shifted"] += 1
        spawn = x - float(offset_mm) / 1000.0
        if RELEASE_OFFSET_DIAG:
            say(
                f"[offset] release idx={int(sample.index):02d} "
                f"cat={sample.category:<10s} "
                f"dia_mm={sample.diameter * 1000:6.1f} planned={x:+.5f} "
                f"spawn={spawn:+.5f} off_mm={float(offset_mm):+7.2f} src=table"
            )
        return spawn

    def respawn(self, sample: FruitSample, along: float | None = None,
                x_jitter: float = 0.10, x: float | None = None) -> None:
        """Drop a fruit onto the belt at the upstream end.

        ``along`` overrides the along-the-line (Y) spawn position. ``x``
        overrides the lateral position on the scattered line (the patch
        schedule places abreast pairs at a planned x); ``None`` keeps the
        seeded draw, so every pre-patch path is unchanged. The fruit is placed
        a few centimetres above the surface and falls onto it, so the physics
        engine never has to resolve an interpenetration.

        P50 (default off): ``FRUIT_RELEASE_OFFSET=1`` post-processes that lateral
        value through the per-instance table (``x_spawn = planned - offset``) so
        the *delivered* x lands on the planned one; see `_release_offset`.
        """
        cfg = self.cfg
        y = cfg.spawn_y if along is None else along
        if self.supply.scatter:
            x = (
                self.rng.uniform(self.supply.x_min, self.supply.x_max)
                if x is None
                else float(x)
            )
            if along is None and self.supply.along_jitter > 0.0:
                y += self.rng.uniform(
                    -self.supply.along_jitter, self.supply.along_jitter
                )
        else:
            x = cfg.belt_center[0] + self.rng.uniform(-cfg.lateral_jitter, cfg.lateral_jitter)
        # P50 phase 2 (default off): the per-instance release-offset compensation.
        # The draw above is unchanged; only the value that reaches the rigid body
        # moves, so the A/B compares the same supply draws (see the block above
        # `class FruitSpawner`).
        x = self._release_offset(sample, float(x))
        z = cfg.belt_center[2] + cfg.belt_size[2] / 2.0 + sample.diameter / 2.0 + 0.03
        rigid = self._rigids[sample.index]
        rigid.set_world_poses(
            positions=[[x, y, z]],
            orientations=[[1.0, 0.0, 0.0, 0.0]],
        )
        rigid.set_velocities(
            linear_velocities=[[0.0, cfg.belt_speed, 0.0]],
            angular_velocities=[[0.0, 0.0, 0.0]],
        )
        sample.parked = False
        sample.held = False
        sample.attached = False
        self._tray_dwell.pop(sample.index, None)

    # ------------------------------------------------------------------ #
    # Conveyor feeding
    # ------------------------------------------------------------------ #
    def protect(self, index: int | None) -> None:
        """Mark one fruit as owned by an in-flight attempt (never recirculated)."""
        if index is not None:
            self.protected_indices.add(int(index))

    def unprotect(self, index: int | None) -> None:
        """Release one fruit's protection when its attempt ends."""
        if index is not None:
            self.protected_indices.discard(int(index))

    def is_protected(self, sample: FruitSample) -> bool:
        return bool(sample.index in self.protected_indices or sample.index == self.protected)

    def park(self, sample: FruitSample) -> None:
        """Move a fruit out of the scene.

        Each fruit gets its own far-away slot: parking several bodies at the same
        point makes them interpenetrate and PhysX resolves that with explosive
        contact forces.
        """
        rigid = self._rigids[sample.index]
        x = 60.0 + 3.0 * sample.index
        rigid.set_world_poses(positions=[[x, 0.0, -50.0]], orientations=[[1.0, 0.0, 0.0, 0.0]])
        rigid.set_velocities(linear_velocities=[[0.0, 0.0, 0.0]], angular_velocities=[[0.0, 0.0, 0.0]])
        sample.parked = True
        self._tray_dwell.pop(sample.index, None)

    def reset(self) -> None:
        """Park every fruit and restart the release schedule."""
        for sample in self.samples:
            self.park(sample)
        self.active = []
        self._cursor = 0
        self._next_release = 0.0
        self._wave_count = 0
        if self.supply.bed and self.supply.bed_plan is not None:
            # Same seed, same schedule: a reset replays the bed's lattice
            # instead of continuing from wherever the previous run stopped.
            self.bed_schedule = BedSchedule(self.supply.bed_plan, seed=self.seed)
        self._tray_dwell.clear()
        app_utils.update_app(steps=1)

    def release_next(self, place: bool = True) -> FruitSample:
        """Randomize and drop the next queued fruit at the belt entrance.

        The cursor skips a fruit that is currently held or protected by an
        in-flight attempt: `respawn` teleports its sample upstream, and under the
        bimanual pipeline `update` runs while the other arm carries, so the
        feeder must never steal a payload (the same wrap-around teleport the
        video recorder measured, `logs/902_video_before.log`). Single-arm runs
        call `update` only between attempts, where no sample is held or
        protected, so their cursor sequence is unchanged.

        `place=False` draws and accounts the sample but leaves it where it is;
        the bed schedule needs the fruit's radius *before* it can choose the
        slot (the pair-clearance predicate is per-fruit) and then respawns it at
        the planned column. Every legacy caller uses the default, so their
        sequence is unchanged.
        """
        count = len(self.samples)
        if self.supply.scatter:
            sample = self._pick_recyclable(count)
        else:
            for _scan in range(count):
                sample = self.samples[self._cursor % count]
                self._cursor += 1
                if sample.parked or (not sample.held and not self.is_protected(sample)):
                    break
            else:
                sample = None
        if sample is None:
            return None
        # The feeder's next slot can already be occupied by a fruit that is
        # sitting in a discharge tray. `respawn` teleports it upstream (that is
        # the recycle), so classify it first: a tray fruit is the output line's
        # end, never `fell_off`. Without this, the scheduled release stole a
        # tray fruit *before* the settle dwell could count it (seen in the clip
        # run `logs/481`: the fruit vanished from the tray with no event).
        if not sample.parked and sample.index in self._rigids and not sample.held:
            pos = self.position(sample)
            if self.cfg.on_output_tray(pos):
                self.stats["discharged"] += 1
                say(
                    f"[belt] {sample.category} (index {sample.index}) discharged to the tray "
                    f"at x={float(pos[0]):.2f} (recycled by the feeder schedule)"
                )
        if place:
            self.respawn(sample)
        if sample not in self.active:
            self.active.append(sample)
        self.stats["released"] += 1
        return sample

    def _pick_recyclable(self, count: int) -> FruitSample | None:
        """Choose the next sample to recycle, preferring a parked one.

        The scattered feeder advances the cursor ~3 slots per attempt instead of
        one, so a wrapped cursor can land on a fruit that is still mid-belt or
        already riding an output conveyor. Teleporting one of those upstream
        would be visible in a clip and would re-introduce a fruit that was
        already sorted. Priority: parked (the normal recycle) > main belt
        downstream of the station (already past selection, about to despawn) >
        main belt upstream; held, protected, or output-line fruit are never
        taken.

        On the bed (`self.supply.bed`) every draw is counted (`bed_draws`) and
        a draw that falls through to a live body is counted
        (`bed_live_recycled`, see `_bed_note_live_draw`), so the audit can
        assert the fraction is zero. Both counters are lazily created and
        bed-gated: the legacy stats dict is unchanged.

        **Known sim path, now refused (P32 Gate-A residual R1, fixed):** the
        x-window test below (`|x - belt_center[0]| <= 0.30`) also reaches the
        raised output lanes, so a fruit placed there was treated as a main-belt
        body downstream of the station and recycled (measured `x=0.628,
        y=-0.583, z=1.377` for a pear, the run's `live_recycled=1/489`). The
        offline fake belt never puts a body there. The bed now refuses any body
        above `belt_top + 0.10 m` (the `bed_top` cut below, 1.27 m at the
        shipped scene): a placed fruit on the raised lane sits at z 1.35-1.38,
        while the tallest class on the belt reaches 1.235 m, so the band cannot
        exclude a main-belt body. Bed-gated (`self.supply.bed`): every legacy
        schedule keeps the shipped predicate byte-for-byte.
        """
        if self.supply.bed:
            self.stats["bed_draws"] = self.stats.get("bed_draws", 0) + 1
        # A body higher than this is not on the main belt (bed only). The main
        # belt's top is 1.17 m; a placed fruit on a raised output lane is at
        # 1.34 m (the belt top) + its radius, i.e. >= 1.37 m.
        bed_top = (
            float(self.cfg.belt_center[2])
            + float(self.cfg.belt_size[2]) / 2.0
            + 0.10
            if self.supply.bed
            else None
        )
        fallback: FruitSample | None = None
        for _scan in range(count):
            sample = self.samples[self._cursor % count]
            self._cursor += 1
            if sample.parked:
                return sample
            if sample.held or self.is_protected(sample):
                continue
            pos = self.position(sample)
            if abs(float(pos[0]) - self.cfg.belt_center[0]) > 0.30:
                continue  # on an output conveyor or off the main belt
            if bed_top is not None and float(pos[2]) > bed_top:
                continue  # placed on a raised output lane (bed only, R1)
            if float(pos[2]) < self.cfg.belt_center[2] - 0.25:
                continue  # fell off
            if float(pos[1]) <= self.recycle_y:
                self._bed_note_live_draw(sample)
                return sample  # downstream of the station: recycling is invisible
            if fallback is None:
                fallback = sample
        if fallback is not None:
            self._bed_note_live_draw(fallback)
        return fallback

    def _bed_note_live_draw(self, sample: FruitSample) -> None:
        """Count a draw that fell through to a **live** body (P32 B1, bed only).

        `_pick_recyclable` prefers a parked body; a live one means the pool was
        exhausted, and `respawn` will teleport it from wherever it was (mid-belt,
        or already past the station) to the spawn point - a visible jump and a
        destroyed candidate. The bed's pool is sized so this never happens
        (`bed.BED_POOL`) and `scripts/211_bed_audit.py` asserts the fraction is
        zero. Gated on `self.supply.bed` so a legacy stats dict (and every
        shipped log line that prints one) stays byte-identical.
        """
        if not self.supply.bed:
            return
        self.stats["bed_live_recycled"] = self.stats.get("bed_live_recycled", 0) + 1
        pos = self.position(sample)
        upstream = float(pos[1]) - float(self.recycle_y)
        previous = float(self.stats.get("bed_live_recycled_max_upstream_m", 0.0))
        # Keep the event with the largest displacement (signed: negative = a
        # placed body downstream of the recycle line, the measured output-lane
        # path); the old `max(0, ...)` clamp printed 0.00 m for exactly that
        # event and hid where it came from.
        if abs(upstream) >= abs(previous):
            self.stats["bed_live_recycled_max_upstream_m"] = upstream
        if self._bed_diag:
            # m3 attribution: the pool drew a live body (the pre-B1 teleport
            # path). Print where it was so a non-zero run is attributable.
            say(
                f"[bed-recycle] {sample.category} idx={sample.index} "
                f"x={float(pos[0]):.3f} y={float(pos[1]):.3f} "
                f"z={float(pos[2]):.3f}"
            )

    def update(
        self, sim_time: float, advance_furniture: bool = True
    ) -> list[FruitSample]:
        """Release on schedule and recycle fruit that reached the downstream end.

        `advance_furniture=False` (P32 phase 2, `FRUIT_FEED_CADENCE=1`, default
        off) runs the same pump - the absolute release schedule, the
        recirculation clock, the transport wake loop and the despawn scan - but
        leaves the conveyor's kinematic furniture where it is. The main belt's
        cleat phase advances **once per `update` call** (`enforce_transport` ->
        `belt.step`), i.e. the shipped line moves the cleats for its 60-90
        between-attempt ticks and not at all during an attempt. A mid-attempt
        feed must not silently change that second thing as well: the cadence
        lever is the feeder's release schedule, and the A/B has to compare it
        against the shipped furniture cadence. The default `True` is every
        existing call site (the driver loops, the collector, the rl env and the
        offline audits) - byte-identical.
        """
        released = []
        # Recirculation. A fruit that waits in the queue window without being
        # picked for FRUIT_MAX_WAIT_S seconds of simulated time goes back to the
        # feeder (park -> released again later), which is what a return line does
        # and what keeps the queue from growing without bound now that the gate
        # presents one fruit at a time.
        dt = max(0.0, float(sim_time) - float(getattr(self, "_last_sim_time", sim_time)))
        self._last_sim_time = float(sim_time)
        wait_limit = float(os.environ.get("FRUIT_MAX_WAIT_S", "60"))
        if wait_limit > 0.0:
            for sample in list(self.active):
                if sample.parked or sample.held or self.is_protected(sample):
                    continue
                pos = self.position(sample)
                along = float(pos[1])
                lateral = float(pos[0])
                # Only fruit still *on the main belt* count as queued: a fruit on
                # the raised output line is at the same along-position but off the
                # centre line, and parking those emptied the output bins in the
                # v2 layout (seen in logs/292, where recirculation fired on
                # already-placed fruit).
                on_belt = abs(lateral - self.cfg.belt_center[0]) < 0.30
                if on_belt and self.cfg.pick_y - 0.10 <= along <= self.cfg.pick_y + 0.45:
                    waited = float(getattr(self, "_waited", {}).get(sample.index, 0.0)) + dt
                    self._waited[sample.index] = waited
                    if waited > wait_limit:
                        self.stats["recirculated"] = self.stats.get("recirculated", 0) + 1
                        say(
                            f"[belt] recirculating {sample.category} (index {sample.index}): "
                            f"waited {waited:.0f}s at the gate"
                        )
                        self.park(sample)
                        self.active.remove(sample)
                        self._waited.pop(sample.index, None)
                elif hasattr(self, "_waited"):
                    self._waited[sample.index] = 0.0
        # Line-full interlock. With a gate at the pick station the fruit behind it
        # queue up, and every queued body joins one contact island with the belt
        # and the cleats: the step time grew until the simulation ran at ~0.1x
        # real time (logs/275, 35 min for four attempts). Real lines do not push
        # product into a full buffer either, so the release is held while the
        # queue just upstream of the gate is already `FRUIT_QUEUE_MAX` deep.
        queue_max = int(os.environ.get("FRUIT_QUEUE_MAX", "6"))
        if self.supply.scatter and self.supply.stream:
            released.extend(self._pump_supply(sim_time, queue_max))
        elif sim_time >= self._next_release and self._queue_depth() < queue_max:
            sample = self.release_next()
            if sample is not None:
                released.append(sample)
                self._next_release = sim_time + self.cfg.spawn_period_s
        self.enforce_transport(advance_furniture=advance_furniture)
        tray_dwell_s = float(self.cfg.output_tray_dwell_s)
        for sample in list(self.active):
            if sample.parked:
                self.active.remove(sample)
                continue
            pos = self.position(sample)
            along = float(pos[1])
            # End of the output line. A fruit that has settled in a discharge
            # tray has finished its cycle; the tray is real end-of-line hardware
            # (`conveyor.OutputBelt._build_discharge`), so this is counted as
            # `discharged`, not as a fruit that fell off. The dwell is for the
            # clip and for the tray to actually hold the fruit for a moment.
            if not sample.held and self.cfg.on_output_tray(pos):
                speed = float(np.linalg.norm(self.velocity(sample)))
                if speed < 0.05:
                    dwell = self._tray_dwell.get(sample.index, 0.0) + dt
                    self._tray_dwell[sample.index] = dwell
                    if dwell >= tray_dwell_s:
                        self.stats["discharged"] += 1
                        say(
                            f"[belt] {sample.category} (index {sample.index}) discharged to the "
                            f"tray at x={float(pos[0]):.2f} (settled {dwell:.1f}s)"
                        )
                        self.park(sample)
                        self.active.remove(sample)
                else:
                    self._tray_dwell[sample.index] = 0.0
                continue
            # A fruit still on the chute is between the belt top and the tray:
            # not on the main belt, not on the floor. `_end_of_line` suppresses
            # `fell_off` while it is inside the discharge envelope, or it would
            # be recycled mid-slide. The classification is shared with the bed's
            # scan-only sweep (`scan_despawn`), so the two scans cannot disagree
            # about a body.
            kind = self._end_of_line(sample, pos, along)
            if kind is not None:
                self._recycle_end(sample, kind, pos, along)
        return released

    def _end_of_line(self, sample: FruitSample, pos, along: float) -> str | None:
        """Classify a live body at the end of the line (`update`'s despawn test).

        `"fell_off"` wins over `"reached_end"` - the shipped precedence: a body
        that is both past `despawn_y` and below the belt by 0.25 m was lost, not
        delivered. A body sliding down the output chute keeps `fell_off` False
        while it is inside `on_output_discharge`, so it is not recycled
        mid-slide. `None` means the body is still on the line.

        Split out (P32 R2) so `scan_despawn` - the bed's between-pump sweep -
        reuses this exactly instead of re-deriving the geometry: the two call
        sites must never classify the same body differently.
        """
        fell_off = float(pos[2]) < self.cfg.belt_center[2] - 0.25
        if fell_off and not sample.held and self.cfg.on_output_discharge(pos):
            fell_off = False
        if fell_off:
            return "fell_off"
        if float(along) < self.cfg.despawn_y:
            return "reached_end"
        return None

    def _recycle_end(self, sample: FruitSample, kind: str, pos, along: float) -> None:
        """Count and recycle one end-of-line body the way `update` always has.

        `park` is the recycle (the body re-enters the pool as `parked` and the
        feeder draws it later); it is **not** a mid-belt teleport, because the
        caller has already established that the body is past `despawn_y` or on
        the floor.
        """
        self.stats[kind] += 1
        if kind == "fell_off" and self._bed_diag:
            # m3 attribution (bed only, pure reporting): a `fell_off` is
            # either an unattended belt loss or a failed attempt's payload
            # leaving the line. The row names the sample and where it was,
            # so the run's `[bed] stats fell_off=` can be attributed
            # instead of assumed.
            say(
                f"[bed-fall] {sample.category} idx={sample.index} "
                f"x={float(pos[0]):.3f} y={along:.3f} z={float(pos[2]):.3f} "
                f"held={sample.held}"
            )
        self.park(sample)
        self.active.remove(sample)

    def scan_despawn(self, ticks: int = 1) -> None:
        """Scan-only end-of-line sweep (P32 Gate-A residual R2; bed only).

        `update` is the only place the end-of-line scan runs, and the driver
        calls it at the attempt boundary (the 60-tick feed loop in
        `scripts/20_pick_place.py`, the bimanual loop's `gap_ticks`). Between
        those calls the belt keeps carrying fruit (`_step_sim`, inside an
        attempt), so a body that crossed `despawn_y` then kept going over the
        belt's physical end (-0.80 m) was charged `fell_off` by the *next*
        pump: measured **5** (4 past the end) on the cadence arm and **102**
        (96 past the end) on the 20-attempt boundary control, with
        `reached_end=0` - the accounting signature of the gap, not of a push.

        This is that scan, on the driver's own tick, and **nothing else**: no
        release schedule (`_next_release` untouched), no interlock, no
        `enforce_transport`/`belt.step` (the conveyor's kinematic furniture keeps
        the shipped per-pump cadence), no tray-dwell accrual and no
        recirculation clock. A body still on the belt is never touched - only
        one past `despawn_y` or on the floor is classified (`_end_of_line`) and
        recycled (`_recycle_end`), which is exactly what `update` would do.

        Bed-gated: a legacy spawner returns immediately (one attribute read per
        control tick, the same budget as `_feed_on`), and the shipped driver
        never calls it. Thread safety: every `_step_sim` runs under the bimanual
        relay's single run permit, so `active` cannot be mutated concurrently.
        """
        if not self.supply.bed:
            return
        self._despawn_ticks += max(1, int(ticks))
        if self._despawn_ticks < self._despawn_stride:
            return
        self._despawn_ticks = 0
        # Lazy counters (bed gate above), so a legacy `stats` dict is unchanged:
        # `sweeps` proves the sweep ran and `swept` is how many of the run's
        # `reached_end` came from it rather than from the pump's own scan.
        self.stats["bed_sweeps"] = self.stats.get("bed_sweeps", 0) + 1
        for sample in list(self.active):
            if sample.parked or sample.held:
                continue
            pos = self.position(sample)
            if self.cfg.on_output_tray(pos):
                # A discharged body's recycle is the tray dwell in `update`
                # (it needs that method's `dt`); the sweep must not race it.
                continue
            along = float(pos[1])
            kind = self._end_of_line(sample, pos, along)
            if kind is not None:
                self._recycle_end(sample, kind, pos, along)
                self.stats["bed_swept"] = self.stats.get("bed_swept", 0) + 1

    def bed_stock_capacity(self) -> int:
        """Geometric maximum of the bed's approach band [fruit] (m6).

        The pump's interlock (`FRUIT_SUPPLY_BED_STOCK_MAX`) is a *depth* on the
        band `_bed_stock_depth` counts: `spawn_y + 0.05` down to
        `pick_y + 0.10`, i.e. 0.63 m at the shipped scene. With the mean row
        pitch and every column occupied the band holds
        `floor(0.63 / 0.14) + 1 = 5` rows x 3 columns = 15 slots; the strict
        capacity used for the clamp counts full rows only (4 x 3 = 12) plus
        one partial row at the spawn end (3) = 15, and the shipped delivered
        design is 10 (2.4 fruit per row). The clamp is deliberately the
        *geometric* ceiling, not the delivered density: it only stops a typo
        from demanding more bodies than the band can physically hold.

        Plan-dependent by construction: `FRUIT_SUPPLY_BED_ALONG_*` and the
        column list move it, and `fruits.py` re-evaluates it at construction.
        """
        plan = self.supply.bed_plan
        if plan is None:
            return 0
        lo = float(self.cfg.pick_y) + 0.10
        hi = float(self.cfg.spawn_y) + 0.05
        mean_pitch = 0.5 * (plan.along_min + plan.along_max)
        if mean_pitch <= 1e-9:
            return len(plan.columns)
        rows = max(1, int(max(0.0, hi - lo) // mean_pitch) + 1)
        return max(1, rows * len(plan.columns))

    def _bed_stock_depth(self) -> int:
        """Bed feeder interlock input: live fruit in the **approach band**.

        `FRUIT_QUEUE_MAX` (6) was calibrated for the single-file lines, where the
        station window `[pick_y - 0.05, pick_y + 0.45]` is the buffer in front of
        the gate: six bodies there is ~4 s of travel and the approach segment is
        stocked *by the backlog* of a slow feeder. The bed's rows are due every
        ~1.1 s of travel, so the same six bodies sit mostly *downstream of the
        station window* and the pack's throughput is what fills it - measured
        (`logs/p32/60_probe_nocap.log`): at the shipped q6 the station check
        blocked 1 due row in 3, the stock band above the catch floor went empty
        for 2-3 s at a time, and 8 of 10 selections found nothing (live 9-12
        fruit, all of it below 0.24 m).

        So the bed paces on the band the *selector* draws from - the segment
        between the release floor and the spawn point, 0.58 m, the same length as
        the station window - and the depth keeps the shipped linear density
        (6 fruit / 0.58 m = 10.3/m against 6 / 0.50 m = 12/m). Counting stops at
        `spawn_y + 0.05` because a body released this call is already there.
        Bed-gated: every legacy schedule keeps `_queue_depth` byte-for-byte.
        """
        lo = float(self.cfg.pick_y) + 0.10
        hi = float(self.cfg.spawn_y) + 0.05
        depth = 0
        for sample in self.active:
            if sample.parked or sample.held:
                continue
            pos = self.position(sample)
            if abs(float(pos[0]) - self.cfg.belt_center[0]) > 0.30:
                continue
            if lo <= float(pos[1]) <= hi:
                depth += 1
        return depth

    def _queue_depth(self) -> int:
        """Fruit waiting just upstream of the gate (the line-full interlock input).

        Only fruit still on the main belt count: fruit on the raised output
        conveyors are off the centre line, and counting them held the release
        interlock shut so the line starved after the output bins filled ("no
        eligible fruit", logs/295).
        """
        gate_y = self.cfg.pick_y
        queued = 0
        for sample in self.active:
            if sample.parked or sample.held:
                continue
            pos = self.position(sample)
            if (
                abs(float(pos[0]) - self.cfg.belt_center[0]) < 0.30
                and gate_y - 0.05 <= float(pos[1]) <= gate_y + 0.45
            ):
                queued += 1
        return queued

    def bed_stats_line(self) -> str | None:
        """Final `[bed] stats` row (P32 phase A, m3); None when the bed is off.

        The per-attempt diagnostics name the pump's state, but the *run's*
        zero-recycle and zero-fell-off assertions were only visible in the
        offline audit. This row puts them in the simulator log itself, so a
        claim of "the pool never recycled a live body" and "no body fell off
        the belt" is evidenced by the run that made it. Gated on `supply.bed`,
        so every legacy log keeps its byte-identical stream.
        """
        if not self.supply.bed:
            return None
        stats = self.stats
        draws = int(stats.get("bed_draws", 0))
        recycled = int(stats.get("bed_live_recycled", 0))
        live = sum(1 for sample in self.active if not sample.parked and not sample.held)
        return (
            f"[bed] stats draws={draws} placed={int(stats.get('bed_placed', 0))} "
            f"live_recycled={recycled}/{draws} "
            f"({recycled * 100.0 / draws if draws else 0.0:.1f} %) "
            + (
                f"recycled_dy={float(stats.get('bed_live_recycled_max_upstream_m', 0.0)):+.2f}m "
                if recycled
                else ""
            )
            + f"holds={int(stats.get('bed_holds', 0))} "
            f"refused={int(stats.get('bed_refused', 0))} "
            f"rebased={int(stats.get('bed_rebased', 0))} "
            f"late_dropped={float(stats.get('bed_late_dropped_s', 0.0)):.1f}s "
            f"fell_off={int(stats.get('fell_off', 0))} "
            f"reached_end={int(stats.get('reached_end', 0))} "
            f"sweeps={int(stats.get('bed_sweeps', 0))} "
            f"swept={int(stats.get('bed_swept', 0))} "
            f"supply_skipped={int(stats.get('supply_skipped', 0))} "
            f"live={live}"
        )

    def _release_gap(self) -> float:
        """One release gap [m] on the scattered line: bed, patch, dense-sheet or uniform.

        With `bed=True` (P32 phase 1) the gap is one **row pitch** from
        `BedSchedule`; a pump call releases the row's abreast edge pair at that
        along plus the middle column half a pitch downstream, so the fruit order
        on the belt is pair, middle, pair, middle. The bed draws from its own RNG
        stream, so this branch is the only place a bed number is drawn and the
        legacy branches below are untouched.

        With `patch=True` (W6-A 2D sheet) the gap is one **slice spacing**
        drawn from `patch_slice_min..patch_slice_max`; the slice's fruit are
        placed abreast by `_release_patch_slot`, so the spacing here is
        measured slice-start to slice-start.

        With `wave=True`: within a cluster the gap is drawn from
        `wave_gap_min..wave_gap_max`; after `wave_size` releases the
        cluster-boundary gap is drawn from `wave_sep_min..wave_sep_max`. The
        boundary band is kept at or below the within-cluster band (owner
        correction 2026-10-10), so clusters run back-to-back and the line is a
        **continuous dense sheet** - no empty stretch between bursts. Both
        bands come from the same seeded RNG stream as the uniform line, so a
        seed reproduces the whole arrival pattern (the manifests pin the
        bands).
        """
        if not self.supply.scatter:
            return float(self.cfg.spawn_period_s)
        if self.bed_schedule is not None:
            return self.bed_schedule.next_gap()
        if self.supply.patch:
            return self.rng.uniform(
                self.supply.patch_slice_min, self.supply.patch_slice_max
            )
        if not self.supply.wave:
            return self.supply.sample_gap(self.rng)
        self._wave_count += 1
        if self._wave_count >= self.supply.wave_size:
            self._wave_count = 0
            return self.rng.uniform(
                self.supply.wave_sep_min, self.supply.wave_sep_max
            )
        return self.rng.uniform(self.supply.wave_gap_min, self.supply.wave_gap_max)

    def _release_period(self) -> float:
        """Seconds until the next scheduled release (one sampled gap of travel)."""
        if self.supply.scatter:
            speed = abs(float(self.cfg.belt_speed))
            if speed > 1e-3:
                return self._release_gap() / speed
        return float(self.cfg.spawn_period_s)

    def _release_clear(self, along: float, x: float | None = None) -> bool:
        """True when no live fruit already occupies `along` on the main belt.

        `x` is the lateral position the new fruit would take. On the patch
        schedule a same-**slice** partner sits at the same `along` by design,
        so the 0.08 m separation rule is applied in the belt plane: a live
        fruit inside the along window is only in the way when its lateral
        separation is below `patch_sep_min` (>= 0.085 m). Without `x` (every
        pre-patch call site) the original along-only rule is unchanged.
        """
        for sample in self.active:
            if sample.parked or sample.held:
                continue
            pos = self.position(sample)
            if abs(float(pos[0]) - self.cfg.belt_center[0]) > 0.30:
                continue
            if abs(float(pos[1]) - float(along)) < 0.08:
                if x is None:
                    return False
                if abs(float(pos[0]) - float(x)) < self.supply.patch_sep_min:
                    return False
        return True

    def _bed_neighbours(self, exclude=None):
        """Live fruit in the belt plane as `(along, x, radius)` for the bed rule.

        Same population `_release_clear` looks at (parked and held fruit are not
        in the way; a *protected* fruit still is), plus the radius the corridor
        rule needs. Fruit on a raised output conveyor are off the centre line
        (`|x - centre| > 0.30`) and are skipped exactly as there. Fruit-pose
        reads are the safe readback class (they do not move the run - see the
        WORKLOG entry "it is the arm-link readback, not reads in general").

        `exclude` is one sample index or a collection: a row's drawn samples are
        about to be placed (and a fallback recycle can name a live body), so they
        must not block their own row.
        """
        skip: set[int] = set()
        if exclude is not None:
            if isinstance(exclude, (set, frozenset, list, tuple)):
                skip = {int(index) for index in exclude}
            else:
                skip = {int(exclude)}
        out = []
        for sample in self.active:
            if sample.parked or sample.held:
                continue
            if sample.index in skip:
                continue
            pos = self.position(sample)
            if abs(float(pos[0]) - self.cfg.belt_center[0]) > 0.30:
                continue
            out.append((float(pos[1]), float(pos[0]), 0.5 * float(sample.diameter)))
        return out

    def _bed_draw_row(self) -> list[FruitSample]:
        """Draw up to one row's worth of samples without placing them.

        A row is at most one fruit per column (2-3 at the shipped geometry). A
        short draw (pool exhausted) degrades the row instead of dropping it: the
        schedule places the fruit it was given. The samples stay parked until
        `_bed_commit_row` (or `_bed_refuse`) decides their fate.
        """
        width = len(self.supply.bed_plan.columns) if self.supply.bed_plan else 2
        samples: list[FruitSample] = []
        seen: set[int] = set()
        for _ in range(width):
            sample = self.release_next(place=False)
            if sample is None:
                break
            if sample.index in seen:
                # Degenerate pool (fewer bodies than one row): the recycled
                # cursor wrapped onto a fruit already drawn for this row. It
                # cannot fill a second slot - park it and degrade the row.
                self.park(sample)
                if sample in self.active:
                    self.active.remove(sample)
                break
            seen.add(sample.index)
            samples.append(sample)
        return samples

    def _bed_place_row(self, along: float):
        """Draw and place one row: `(row, samples)`; `row` is None when refused.

        The schedule needs the fruit's radius before it can choose the row (the
        pair rule is per-pair), so the samples are drawn unplaced, then respawned
        at the planned columns. `along_max` is the spawn point: an on-time row
        has no upstream room, a late one (the pump's backlog) does.
        """
        samples = self._bed_draw_row()
        if not samples:
            return None, []
        row = self.bed_schedule.place_row(
            along,
            [0.5 * float(sample.diameter) for sample in samples],
            self._bed_neighbours(exclude=[sample.index for sample in samples]),
            along_max=float(self.cfg.spawn_y),
        )
        return row, samples

    def _bed_commit_row(self, row, samples, released: list[FruitSample]) -> None:
        """Respawn a row's placed slots, park any unused sample, count the row.

        `bed_placed` counts **placed fruit slots**, not draws: the row draws one
        sample per column (3) but the mixed pool's middle is usually refused, so
        `stats["released"]` (one per `release_next`) runs ~1.5x the fruit that
        actually lands on the belt. The audit's density numbers use
        `bed_placed`.
        """
        for slot, sample in zip(row.slots, samples):
            self.respawn(sample, along=slot.along, x=slot.x)
            released.append(sample)
        for sample in samples[len(row.slots):]:
            self.park(sample)
            if sample in self.active:
                self.active.remove(sample)
        self.stats["bed_rows"] = self.stats.get("bed_rows", 0) + 1
        self.stats["bed_placed"] = self.stats.get("bed_placed", 0) + len(row.slots)
        if row.has_middle:
            self.stats["bed_full_rows"] = self.stats.get("bed_full_rows", 0) + 1

    def _bed_refuse(self, samples) -> None:
        """Skip a row: count it and park its samples (the cost is the row)."""
        self.stats["supply_skipped"] += 1
        self.stats["bed_refused"] = self.stats.get("bed_refused", 0) + 1
        for sample in samples:
            self.park(sample)
            if sample in self.active:
                self.active.remove(sample)

    def _release_bed_row(
        self, along: float, released: list[FruitSample]
    ) -> bool:
        """Release one bed **row**: the abreast edge pair, plus the middle if it clears.

        Returns False only when the feeder had no recyclable sample (the pump
        then stops, like the uniform path). A row the pair rule refuses after its
        bounded shift is counted (`supply_skipped` + the lazy `bed_refused`) and
        its samples are parked again, so a violating pair is never released onto
        the belt. The parked samples are not wasted: the feeder's
        `_pick_recyclable` prefers parked bodies, so they re-enter on a later
        row - a refusal costs the *row* (one pitch of density), not the fruit.

        A row shifted upstream is released that much *later*: the spawner's
        absolute clock is pushed by the same time, so the following pitch stays
        the one the schedule drew. The shift is per row, not per fruit.

        The legacy `_release_clear` pair rule is the 0.08 m plane floor, and the
        bed enforces it (plus the jaw corridor) through `BedPlan.pair_clear`
        against every live fruit and inside the row itself. `_release_clear`'s
        lateral branch is not applied here because a row's middle sits 0.055-0.065
        m from its edges - closer than that branch's 0.085 m lateral test would
        allow - while the diagonal corridor rule is the constraint that actually
        protects the jaw.
        """
        row, samples = self._bed_place_row(along)
        if not samples:
            return False
        if row is None:
            self._bed_refuse(samples)
            if self._bed_diag:
                say(
                    f"[bed-row] along={along:.3f} refused after the "
                    f"{self.supply.bed_plan.shift_max:.2f} m shift cap "
                    f"(pair rule / 0.08 m floor)"
                )
            return True
        self._bed_commit_row(row, samples, released)
        if self._bed_diag:
            # P32 phase A: where the row actually landed. A row placed near the
            # station floor (0.10 m) is not a candidate - it rides past the
            # selection floor (~0.40 m) before the arm can be dispatched, which
            # is the starvation the pump's stock cap fixes.
            say(
                f"[bed-row] along={along:.3f} shift={row.shift:.2f} "
                f"slots={len(row.slots)} "
                f"x=" + ",".join(f"{slot.x:.2f}" for slot in row.slots)
                + f" r=" + ",".join(f"{slot.radius:.3f}" for slot in row.slots)
            )
        if row.shift > 0.0:
            speed = max(abs(float(self.cfg.belt_speed)), 0.03)
            self._next_release += row.shift / speed
            self.stats["bed_shifted"] = self.stats.get("bed_shifted", 0) + 1
        return True

    def _patch_plan(self) -> tuple[float, float | None]:
        """One patch slice's lateral plan: `(x0, partner_x)`; partner None = single.

        Pair probability `patch_pair`; a pair's lateral separation is drawn
        from `patch_sep_min..patch_sep_max` (floored above `_release_clear`'s
        0.08 m rule and clamped to the lateral band so the partner stays
        inside `x_min..x_max`). The draws happen only when the caller has
        already decided to release a slice, so the patch-off RNG stream is
        untouched.
        """
        span = float(self.supply.x_max) - float(self.supply.x_min)
        if self.rng.random() < self.supply.patch_pair and span >= self.supply.patch_sep_min:
            sep = min(
                self.rng.uniform(self.supply.patch_sep_min, self.supply.patch_sep_max),
                span,
            )
            x0 = self.rng.uniform(self.supply.x_min, self.supply.x_max - sep)
            return x0, x0 + sep
        return self.rng.uniform(self.supply.x_min, self.supply.x_max), None

    def _release_patch_slot(
        self, along: float, queue_max: int, released: list[FruitSample]
    ) -> bool:
        """Release one patch slice: 1-2 fruit abreast at the same belt position.

        Returns False when the feeder had no recyclable sample (the pump then
        stops, like the uniform path); a refusal by the clearance/queue rules
        degrades the slice (or its partner half) to `supply_skipped`, exactly
        how the uniform pump counts a slot that never existed.
        """
        x0, partner = self._patch_plan()
        if not self._release_clear(along, x0):
            self.stats["supply_skipped"] += 1
            return True
        sample = self.release_next()
        if sample is None:
            return False
        self.respawn(sample, along=along, x=x0)
        released.append(sample)
        if partner is None:
            return True
        if (
            len(released) >= self.supply.burst_max
            or self._queue_depth() >= queue_max
            or not self._release_clear(along, partner)
        ):
            self.stats["supply_skipped"] += 1
            return True
        partner_sample = self.release_next()
        if partner_sample is None:
            self.stats["supply_skipped"] += 1
            return False
        self.respawn(partner_sample, along=along, x=partner)
        released.append(partner_sample)
        return True

    def _pump_supply(self, sim_time: float, queue_max: int) -> list[FruitSample]:
        """Release the scattered feed's backlog at its virtual belt positions.

        `update` is called by the driver loops, not by a real feeder, so a 15 s
        attempt skips ~8 release slots. The old time-schedule reset its clock on
        every call (`_next_release = sim_time + period`) and silently dropped
        that backlog: the shipped acceptance measured `queue_peak=0` - one fruit
        dropped in just before each attempt and an empty belt between them. The
        scattered feed keeps an absolute schedule and, when it is behind, places
        each due fruit at the position it would have reached by now
        (`spawn_y - late * belt_speed`), so the approach segment stays stocked
        with several pieces at once. A slot whose virtual position is already
        past the station is skipped (that fruit never existed, it is not counted
        as fallen), the queue interlock still caps the station window, and a
        placement that would overlap a live fruit is skipped rather than dropped
        on top of it.

        On the patch schedule each due slot is a **slice**: `_release_patch_slot`
        places its 1-2 fruit abreast at `along` (see there for the pair rules).
        On the bed schedule each due slot is a **row** (`_release_bed_row`): the
        abreast edge pair at `along` plus the middle column half a pitch
        downstream, so one pump call delivers a whole row.

        **The bed is paced differently on purpose (P32 phase A).** The backlog
        above is the single-file lines' stocking mechanism; the bed's lattice is
        already dense and its discharge is the schedule's own `period`, so the
        same backlog only pushes every row past the selection floor - measured
        at `lag = +17.5 s` with 9-12 live fruit and *nothing* above the 0.40 m
        catch floor (`logs/p32/60_probe_nocap.log`). Three bed-only rules follow:
        a due row's lateness is capped at `FRUIT_SUPPLY_BED_STOCK_M` (a row
        released further downstream than `spawn_y - stock` is not a candidate, so
        the stale *time* is dropped and the row lands in the stock band); the
        line-full interlock counts `_bed_stock_depth()` (the approach band)
        rather than the station window; and a due row blocked by that interlock
        is *held* (`bed_holds`), never dropped. Every legacy schedule keeps the
        shipped behaviour byte-for-byte (`FRUIT_SUPPLY_BED` unset).

        P4-C1 H1 (`FRUIT_SUPPLY_TRICKLE_LATE_S`, default 0 = off): when set,
        a due slot whose lateness exceeds the cap is consumed-and-skipped
        (`supply_skipped`, plus the lazy `supply_trickled`) instead of being
        delivered late; the schedule still draws one gap per due slot, so only
        the stale backlog is removed, not the due rate.
        """
        cfg = self.cfg
        speed = max(abs(float(cfg.belt_speed)), 0.03)
        floor = float(cfg.pick_y) + 0.10
        released: list[FruitSample] = []
        # P4-C1 H1 diagnostics: locals only, no state and no env reads on the
        # shipped path (`_supply_diag` is read once in `__init__`).
        diag = self._supply_diag
        bed_diag = self._bed_diag
        due = past = stale = clear_refused = 0
        queue_hit = pool_empty = 0
        late_lo: float | None = None
        late_hi: float | None = None
        next_first = float(self._next_release)
        bed_rows = 0
        bed_band = 0
        # Initialised beside `bed_band`: the `[bed-pump]` row below reads both,
        # and a pump call that finds nothing due must not hit a stale local from
        # the previous call (the pre-P32-A `UnboundLocalError` class in the row).
        bed_band_max = queue_max
        bed_along_lo: float | None = None
        bed_along_hi: float | None = None
        # Trickle feed (P4-C1 H1, default 0 = shipped consume-as-is): a due
        # slice older than the cap is dropped - see `SupplyPlan.trickle_late_s`.
        trickle = float(self.supply.trickle_late_s)
        # P32 phase A, bed only: cap the *delivery* lateness at the stock band.
        # The scattered/patch/wave feeds use the backlog on purpose (a 15 s
        # attempt skips ~8 slots and the approach segment is stocked *by* a late
        # release); the bed has a dense lattice whose discharge rate is the
        # feeder's own `period`, so a backlog there does not stock the segment -
        # it pushes every row past the selection floor. The cap is a distance
        # from the spawn point, so it does not move with the belt speed; it is
        # also clamped to the geometric room (`spawn_y - floor`), so a knob
        # larger than the belt cannot release below the station floor.
        bed_stock_late = 0.0
        if self.bed_schedule is not None:
            room = max(0.0, float(cfg.spawn_y) - floor)
            bed_stock_late = min(max(0.0, float(self.supply_bed_stock_m)), room) / speed
        while sim_time >= self._next_release and len(released) < self.supply.burst_max:
            due += 1
            period = self._release_period()
            late = float(sim_time) - float(self._next_release)
            if self.bed_schedule is not None and late > bed_stock_late:
                # The backlog is deeper than the stock band: drop the stale
                # *time*, not a fruit. The feeder is a rate limiter, not an
                # unbounded buffer - a real one that missed a slot does not dump
                # the whole backlog onto the line at once. Re-basing here is what
                # keeps every delivered row inside `[spawn_y - stock, spawn_y]`
                # instead of at the station floor (the measured defect: all rows
                # at along 0.10-0.20, nothing above the 0.40 m selection floor,
                # `logs/p32/51_bed_pipeline.log` / `52_bed_pipeline2.log`).
                # Counted in seconds so the log states how much demand the feeder
                # could not deliver (a density number, not a rate claim).
                self.stats["bed_rebased"] = self.stats.get("bed_rebased", 0) + 1
                self.stats["bed_late_dropped_s"] = (
                    float(self.stats.get("bed_late_dropped_s", 0.0))
                    + (late - bed_stock_late)
                )
                late = bed_stock_late
                self._next_release = float(sim_time) - bed_stock_late
            along = float(cfg.spawn_y) - min(late * speed, 1.60)
            self._next_release += period
            if along < floor:
                self.stats["supply_skipped"] += 1
                past += 1
                continue
            if trickle > 0.0 and late > trickle:
                # H1 consume-and-skip: the stale backlog is dropped, not
                # delivered late. `supply_trickled` is created lazily so the
                # off path's stats dict (and every shipped byte) is unchanged.
                self.stats["supply_skipped"] += 1
                self.stats["supply_trickled"] = (
                    self.stats.get("supply_trickled", 0) + 1
                )
                stale += 1
                continue
            # The line-full interlock. The bed paces on its *approach band*
            # (`_bed_stock_depth`, the segment the selector draws from) because
            # the station-window count blocked 1 due row in 3 and left the band
            # empty for 2-3 s at a time (`logs/p32/60_probe_nocap.log`: 8/10
            # selections with nothing above the catch floor). Every legacy
            # schedule keeps the station-window rule byte-for-byte.
            depth = (
                self._bed_stock_depth()
                if self.bed_schedule is not None
                else self._queue_depth()
            )
            bed_band = depth
            bed_band_max = (
                self.supply_bed_stock_max
                if self.bed_schedule is not None
                else queue_max
            )
            if depth >= bed_band_max:
                if self.bed_schedule is not None:
                    # The bed **holds** its due row instead of dropping it: a
                    # feeder that finds the band full waits, and the row is
                    # released (at the stock cap) as soon as there is room. The
                    # station-window rule below advances the clock past the due
                    # row, which is right for the single-file lines (their
                    # backlog is the stocking mechanism) but cost the bed ~20 %
                    # of its design rows - measured as the one 0/10 probe slot
                    # at band=6 (`logs/p32/61_probe_fixed.log` attempt 7: the
                    # newest release was 4 mm below the catch floor).
                    self.stats["bed_holds"] = self.stats.get("bed_holds", 0) + 1
                    queue_hit = 1
                    break
                self._next_release = max(self._next_release, sim_time + period)
                queue_hit = 1
                break
            if self.bed_schedule is not None:
                # A row is atomic: `_release_bed_row` places its whole group
                # (the abreast pair plus the conditional middle) or none of it,
                # so the pump's `burst_max` cap is checked *before* a row and a
                # row may overshoot it by at most its width - the same way the
                # patch slice's partner may overshoot by one.
                before = len(released)
                skipped_before = self.stats["supply_skipped"]
                placed_before = int(self.stats.get("bed_placed", 0))
                if not self._release_bed_row(along, released):
                    pool_empty = 1
                    clear_refused += self.stats["supply_skipped"] - skipped_before
                    break
                clear_refused += self.stats["supply_skipped"] - skipped_before
                if len(released) > before:
                    late_lo = late if late_lo is None else min(late_lo, late)
                    late_hi = late if late_hi is None else max(late_hi, late)
                if int(self.stats.get("bed_placed", 0)) > placed_before:
                    bed_rows += 1
                    bed_along_lo = along if bed_along_lo is None else min(bed_along_lo, along)
                    bed_along_hi = along if bed_along_hi is None else max(bed_along_hi, along)
                continue
            if self.supply.patch:
                before = len(released)
                skipped_before = self.stats["supply_skipped"]
                if not self._release_patch_slot(along, queue_max, released):
                    pool_empty = 1
                    clear_refused += self.stats["supply_skipped"] - skipped_before
                    break
                clear_refused += self.stats["supply_skipped"] - skipped_before
                if len(released) > before:
                    late_lo = late if late_lo is None else min(late_lo, late)
                    late_hi = late if late_hi is None else max(late_hi, late)
                continue
            if not self._release_clear(along):
                self.stats["supply_skipped"] += 1
                clear_refused += 1
                continue
            sample = self.release_next()
            if sample is None:
                pool_empty = 1
                break
            self.respawn(sample, along=along)
            released.append(sample)
            late_lo = late if late_lo is None else min(late_lo, late)
            late_hi = late if late_hi is None else max(late_hi, late)
        if diag and due:
            say(
                f"[supply-diag] t={float(sim_time):.3f} due={due} "
                f"rel={len(released)} past={past} stale={stale} "
                f"clear={clear_refused} queue={queue_hit} pool={pool_empty} "
                f"late="
                + ("none" if late_lo is None else f"{late_lo:.2f}-{late_hi:.2f}")
            )
        if bed_diag and self.bed_schedule is not None and (due or queue_hit or pool_empty):
            # P32 phase A: the pump's clock and what it delivered. `next` is the
            # schedule's due time *before* this call and `lag` the offset to the
            # absolute clock - the number that has to stay small for the rows to
            # land at the spawn instead of at the station floor.
            say(
                f"[bed-pump] t={float(sim_time):.3f} next={next_first:.3f} "
                f"lag={float(sim_time) - next_first:+.3f} due={due} "
                f"rows={bed_rows} band={bed_band}/{bed_band_max} past={past} queue={queue_hit} "
                f"pool={pool_empty} "
                f"late="
                + ("none" if late_lo is None else f"{late_lo:.2f}-{late_hi:.2f}")
                + (
                    ""
                    if bed_along_lo is None
                    else f" along={bed_along_lo:.3f}..{bed_along_hi:.3f}"
                )
                + (
                    f" rebased={int(self.stats.get('bed_rebased', 0))}"
                    f" dropped={float(self.stats.get('bed_late_dropped_s', 0.0)):.1f}s"
                    if int(self.stats.get("bed_rebased", 0))
                    else ""
                )
            )
        # Top up the catchable approach segment (`FRUIT_SUPPLY_TARGET`,
        # **default 0 = off**). The time schedule alone paces releases ~1.9 s
        # apart, but the shipped loops call `update` in bursts (a 15 s attempt,
        # then a 60-tick feed window), so after a long attempt the segment holds
        # fewer fruit than the schedule's steady state and the bimanual worker -
        # which checks a lane every ~0.5 s - spins on "no eligible fruit". The
        # top-up was measured: at `FRUIT_SUPPLY_TARGET=3` the bimanual's
        # no-eligible slots fall 29/39 (74 %) -> 8/18 (44 %) and its rate rises
        # 5/10 -> 6/10, but the **single-arm line's rate falls 9/10 -> 5/10**
        # (the marginal left place escape flips more often with the denser
        # segment; `logs/v1/53_diag_topup_single.log` vs
        # `logs/v1/20_rate_supply_1.log`). The shipped default therefore keeps
        # the top-up off and the two-line rework (v9/V2) owns the bimanual
        # starvation.
        if self.supply.target > 0:
            while len(released) < self.supply.burst_max:
                if self._approach_depth() >= self.supply.target:
                    break
                if self._queue_depth() >= queue_max:
                    break
                if not self._spawn_clear():
                    break
                sample = self.release_next()
                if sample is None:
                    break
                self.respawn(sample)
                released.append(sample)
                self._next_release = max(
                    self._next_release, sim_time + self._release_period()
                )
        return released

    def _approach_depth(self) -> int:
        """Fruit already in the moving catch's catchable approach segment.

        Counts main-belt fruit between `FRUIT_SUPPLY_TARGET_FROM` (default
        0.35 m, just below the selector's own `_dynamic_select_floor` of
        ~0.40 m) and the spawn point. This is the segment both lanes draw from;
        the top-up keeps it at `FRUIT_SUPPLY_TARGET` fruit so a lane check
        rarely finds none.
        """
        floor = float(self.cfg.pick_y) + float(self.supply.target_from)
        depth = 0
        for sample in self.active:
            if sample.parked or sample.held:
                continue
            pos = self.position(sample)
            if abs(float(pos[0]) - self.cfg.belt_center[0]) > 0.30:
                continue
            if floor <= float(pos[1]) <= float(self.cfg.spawn_y) + 0.05:
                depth += 1
        return depth

    def _spawn_clear(self) -> bool:
        """True when a new fruit can be dropped at the spawn point.

        Requires the newest main-belt fruit to be at least `gap_min` downstream
        of `spawn_y`, so a top-up release never lands on top of one just placed.
        """
        limit = float(self.cfg.spawn_y) - self.supply.gap_min
        for sample in self.active:
            if sample.parked or sample.held:
                continue
            pos = self.position(sample)
            if abs(float(pos[0]) - self.cfg.belt_center[0]) > 0.30:
                continue
            if float(pos[1]) > limit:
                return False
        return True

    def enforce_transport(
        self, dt: float = 1.0 / 120.0, advance_furniture: bool = True
    ) -> None:
        """Keep fruit moving on the belt.

        Transport itself is physical: the belt's surface velocity plus the rubber
        friction material carry the fruit, and the cleats push them along. This
        method only wakes a fruit that PhysX has put to sleep (a sleeping body
        ignores conveyor contact forces), so nothing freezes mid-belt.

        `advance_furniture=False` skips the conveyor's own `belt.step(dt)` (the
        cleat phase / encoder / speed ramp) and keeps only the wake loop - the
        split `update(advance_furniture=False)` needs for the mid-attempt feed
        (see `update`). Every existing caller keeps the default and is
        byte-identical.
        """
        if self.belt is not None and advance_furniture:
            self.belt.step(dt)
        # Follow the belt's *current* speed: at the pick station the line is
        # stopped, and nudging fruit then would push it out of the jaws.
        speed = self.belt.speed if self.belt is not None else self.cfg.belt_speed
        expected = speed * self.cfg.transport_efficiency
        if abs(expected) < 1e-6:
            return
        for sample in self.active:
            if sample.parked or sample.held:
                continue
            pos = self.position(sample)
            on_belt = (
                abs(pos[2] - (self.cfg.belt_center[2] + self.cfg.belt_size[2] / 2.0 + sample.diameter / 2.0))
                < 0.03
            )
            if not on_belt:
                continue
            vel = self.velocity(sample)
            if abs(float(vel[1])) < 0.02:
                self._rigids[sample.index].set_velocities(
                    linear_velocities=[[0.0, expected, 0.0]],
                    angular_velocities=[[0.0, 0.0, 0.0]],
                )

    def prime(self, count: int = 2) -> None:
        """Pre-load a few fruit so the belt is not empty at t=0.

        The pre-v9 line placed them on a fixed 0.30 m ladder from `spawn_y`,
        which put the last two of a four-fruit pre-load downstream of the
        selector's window before the first attempt even started. The scattered
        feed samples the same gaps it releases with (the wave schedule when
        `FRUIT_SUPPLY_WAVE=1`, so the pre-load is the first wave; with
        `FRUIT_SUPPLY_PATCH=1` it samples slice spacings and places one fruit
        per slice - the abreast pairs start with the pump's first slice), and
        stops filling once the next position would sit inside the station
        window (`pick_y + 0.12`), so the pre-load covers the selector's
        upstream window. `scatter=0` keeps the 0.30 m ladder bit-for-bit.

        With `FRUIT_SUPPLY_BED=1` the pre-load is the bed's own first **rows**
        (`_prime_bed`): the same row schedule, the same pair rule, and the
        pump's clock is advanced past the pre-loaded span so its first row lands
        upstream of the last pre-loaded fruit instead of on top of it.
        """
        if self.bed_schedule is not None:
            self._prime_bed(count)
            app_utils.update_app(steps=1)
            return
        alongs: list[float] = []
        along = float(self.cfg.spawn_y)
        floor = float(self.cfg.pick_y) + 0.12
        for i in range(max(0, int(count))):
            if i > 0:
                if self.supply.scatter:
                    along -= self._release_gap()
                    if along < floor:
                        break
                else:
                    along = float(self.cfg.spawn_y) - 0.30 * i
            alongs.append(along)
        for place in alongs:
            sample = self.release_next()
            if sample is None:
                break
            # Space the pre-loaded fruit downstream (-Y), not past the upstream end.
            self.respawn(sample, along=place)
        app_utils.update_app(steps=1)

    def _prime_bed(self, count: int) -> None:
        """Pre-load the bed's first **rows** (P32 phase 1); see `prime`.

        `count` counts rows, not fruit: a row is the schedule's unit and carries
        up to one fruit per column (2-3 at the shipped geometry), so `prime(4)`
        loads 8-12 fruit on both edges and the middles. The loop mirrors the
        pump's per-row order exactly: `next_gap()` first (it sets the row index
        and draws the pitch to the *next* row), then the placement at the along
        the previous pitch put us on. That keeps the row lattice and the RNG
        stream continuous with the pump's first call, and the station floor ends
        the pre-load exactly as it does for the legacy schedules.
        """
        schedule = self.bed_schedule
        speed = max(abs(float(self.cfg.belt_speed)), 0.03)
        along = float(self.cfg.spawn_y)
        floor = float(self.cfg.pick_y) + 0.12
        span = 0.0
        previous_gap = 0.0
        last_shift = 0.0
        for i in range(max(0, int(count))):
            gap = schedule.next_gap()
            if i > 0:
                along -= previous_gap
                span += previous_gap
                if along < floor:
                    break
            previous_gap = gap
            row, samples = self._bed_place_row(along)
            if not samples:
                break
            if row is None:
                self._bed_refuse(samples)
                continue
            self._bed_commit_row(row, samples, [])
            last_shift = float(row.shift)
        # Those rows are already on the belt: the pump's next release is due
        # once the pre-loaded span (plus the last row's upstream shift, if the
        # pair rule moved it) has travelled clear of the spawn point.
        #
        # **On the absolute clock (P32 phase A).** `update` compares the
        # schedule's due time against `SimulationManager.get_simulation_time()`,
        # which at this call is *not* zero (the scene's warm-up and the
        # `advance(30)` before `prime` have already run, and the arm's
        # `go_ready` transit - 3-5 s - runs after it). Writing a bare
        # `span/speed` here left the schedule that many seconds behind the
        # clock, so the first pump call released its backlog at the *station
        # floor* instead of the spawn (`logs/p32/52_bed_pipeline2.log` attempt
        # 0: the pre-load already at along 0.29, `bed_placed` 12 with nothing
        # above 0.29). `_sim_clock` is 0.0 without Isaac (the offline audit),
        # which is the previous behaviour byte-for-byte.
        self._next_release = max(
            self._next_release, self._sim_clock() + (span + last_shift) / speed
        )

    @staticmethod
    def _sim_clock() -> float:
        """The absolute simulation clock [s], or 0.0 where there is no Isaac app.

        `FruitSpawner.update`/`_pump_supply` are driven by the caller's
        `sim_time` (`SimulationManager.get_simulation_time()` in every entry
        script). The bed's pre-load has to place its schedule on that same base;
        the offline audit (`scripts/211_bed_audit.py`, `172_supply_selftest.py`)
        has no app, and 0.0 there is exactly the relative clock it drove before.
        """
        try:
            from isaacsim.core.simulation_manager import SimulationManager

            return float(SimulationManager.get_simulation_time())
        except Exception:  # noqa: BLE001 - no app / stub module: keep the 0 base
            return 0.0

    def position(self, sample: FruitSample) -> np.ndarray:
        pos = self._rigids[sample.index].get_world_poses()[0]
        return np.asarray(pos.numpy() if hasattr(pos, "numpy") else pos)[0]

    def stop(self, sample: FruitSample) -> None:
        """Zero a fruit's velocity so it stays where the gripper found it."""
        self._rigids[sample.index].set_velocities(
            linear_velocities=[[0.0, 0.0, 0.0]], angular_velocities=[[0.0, 0.0, 0.0]]
        )

    def place(self, sample: FruitSample, position: np.ndarray) -> None:
        """Teleport a fruit to an exact position and hold it there."""
        self._rigids[sample.index].set_world_poses(
            positions=[np.asarray(position, dtype=float).tolist()],
            orientations=[[1.0, 0.0, 0.0, 0.0]],
        )
        self.stop(sample)

    # ------------------------------------------------------------------ #
    # Grasp attachment
    # ------------------------------------------------------------------ #
    def attach(self, sample: FruitSample, gripper_point: np.ndarray) -> None:
        """Attach a fruit to the gripper.

        The OpenArm finger collision meshes do not reliably contact small fruit
        in this build (see WORKLOG), so a closed, centred grasp is represented by
        attaching the fruit to the gripper and carrying it kinematically. The
        recorded offset is the fruit's position relative to the gripper point at
        the moment of the grasp, so the payload keeps its pose in the hand.
        """
        position = self.position(sample).copy()
        self._attach_offset[sample.index] = position - np.asarray(gripper_point, dtype=float)
        sample.attached = True
        sample.held = True

    def detach(self, sample: FruitSample) -> None:
        sample.attached = False
        self._attach_offset.pop(sample.index, None)

    def follow(self, sample: FruitSample, gripper_point: np.ndarray) -> None:
        """Place an attached fruit at the gripper, preserving the grasp offset."""
        if not sample.attached:
            return
        offset = self._attach_offset[sample.index]
        target = np.asarray(gripper_point, dtype=float) + offset
        self._rigids[sample.index].set_world_poses(
            positions=[target.tolist()], orientations=[[1.0, 0.0, 0.0, 0.0]]
        )
        self._rigids[sample.index].set_velocities(
            linear_velocities=[[0.0, 0.0, 0.0]], angular_velocities=[[0.0, 0.0, 0.0]]
        )

    def velocity(self, sample: FruitSample) -> np.ndarray:
        vel = self._rigids[sample.index].get_velocities()[0]
        return np.asarray(vel.numpy() if hasattr(vel, "numpy") else vel)[0]

    def angular(self, sample: FruitSample) -> np.ndarray:
        """World angular velocity of one fruit [rad/s].

        The transport probe needs it to say whether a fruit is being *carried*
        (`|omega| * r == |v|`, i.e. rolling on the belt) or *pushed* (no rotation),
        and the encoder-prior design in the notes assumes the second.
        """
        vel = self._rigids[sample.index].get_velocities()[1]
        return np.asarray(vel.numpy() if hasattr(vel, "numpy") else vel)[0]

    def fruit_pose(self, sample: FruitSample) -> tuple[np.ndarray, np.ndarray]:
        """World position and quaternion (w, x, y, z) of one fruit."""
        positions, orientations = self._rigids[sample.index].get_world_poses()
        return (
            np.asarray(
                positions.numpy() if hasattr(positions, "numpy") else positions
            )[0],
            np.asarray(
                orientations.numpy() if hasattr(orientations, "numpy") else orientations
            )[0],
        )

    def enable_contact_tracking(self, threshold: float = 0.05) -> int:
        """Turn on PhysX contact tracking for every fruit body.

        One call per body at setup, not per tick - the solver then accumulates the
        net contact force for free, and `net_contact_forces` only has to read it.
        Fruit reads are the *safe* class of readback: unlike arm-link reads they do
        not change the run (see the WORKLOG).
        """
        count = 0
        for rigid in self._rigids.values():
            try:
                rigid.set_enabled_contact_tracking(True, threshold=threshold)
                count += 1
            except Exception:  # noqa: BLE001
                continue
        return count

    def net_contact_forces(self) -> dict[int, list[float]]:
        """Net contact force on every live fruit [N], keyed by sample index."""
        out: dict[int, list[float]] = {}
        for sample in self.active:
            if sample.parked:
                continue
            rigid = self._rigids.get(sample.index)
            if rigid is None:
                continue
            try:
                force = rigid.get_net_contact_forces()
                array = np.asarray(force.numpy() if hasattr(force, "numpy") else force)
                out[sample.index] = array.reshape(-1)[:3].astype(float).tolist()
            except Exception:  # noqa: BLE001
                out[sample.index] = [0.0, 0.0, 0.0]
        return out

    def state(self) -> list[dict]:
        """Observation of all live fruit - the input to the slow loop's selector."""
        out = []
        for sample in self.active:
            if sample.parked:
                continue
            out.append(
                {
                    "index": sample.index,
                    "prim_path": sample.prim_path,
                    "category": sample.category,
                    "diameter": sample.diameter,
                    "mass": sample.mass,
                    "friction": sample.friction,
                    "grade": sample.grade,
                    "ripeness": sample.ripeness,
                    "defective": sample.defective,
                    "position": self.position(sample),
                    "velocity": self.velocity(sample),
                }
            )
        return out

    def positions(self) -> np.ndarray:
        out = []
        for sample in self.samples:
            pos = self._rigids[sample.index].get_world_poses()[0]
            out.append(np.asarray(pos.numpy() if hasattr(pos, "numpy") else pos)[0])
        return np.asarray(out)
