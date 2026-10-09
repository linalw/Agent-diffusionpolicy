"""Randomized fruit objects and the conveyor spawner.

Fruit quality attributes (grade, ripeness, defects) are NOT perceived - the task
scope for now is pick-and-sort of moving fruit, so those attributes are drawn at
random and used only as task labels.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass

import numpy as np
from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.experimental.prims import RigidPrim

from .assets import SceneConfig
from .common import say
from .meshes import FRUIT_SHAPES, author_fruit, author_stem, make_material


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
        balanced = wave and os.environ.get("FRUIT_BIARM_TWOLINE", "0") == "1"
        default_grades = tuple(
            (grade, _default_grade_weight(grade, balanced)) for grade in cfg.grades
        )
        x_min = number("FRUIT_SUPPLY_X_MIN", SUPPLY_X_MIN)
        x_max = max(x_min, number("FRUIT_SUPPLY_X_MAX", SUPPLY_X_MAX))
        return cls(
            scatter=scatter,
            pool=max(1, int(number("FRUIT_SUPPLY_POOL", cfg.num_fruits))),
            gap_min=gap_min,
            gap_max=gap_max,
            x_min=x_min,
            x_max=x_max,
            along_jitter=max(0.0, number("FRUIT_SUPPLY_ALONG_JITTER", 0.0)),
            stream=os.environ.get("FRUIT_SUPPLY_STREAM", "1") == "1",
            burst_max=max(1, int(number("FRUIT_SUPPLY_BURST_MAX", 6))),
            target=max(0, int(number("FRUIT_SUPPLY_TARGET", 0))),
            target_from=max(0.0, number("FRUIT_SUPPLY_TARGET_FROM", 0.35)),
            grades=_mix_env("FRUIT_SUPPLY_GRADES", cfg.grades, default_grades),
            classes=_mix_env(
                "FRUIT_SUPPLY_CLASSES",
                cfg.fruit_dimensions,
                tuple((name, 1.0) for name in cfg.fruit_dimensions),
            ),
            wave=bool(wave),
            wave_size=max(1, int(number("FRUIT_SUPPLY_WAVE_SIZE", SUPPLY_WAVE_SIZE))),
            wave_gap_min=wave_gap_min,
            wave_gap_max=wave_gap_max,
            wave_sep_min=wave_sep_min,
            wave_sep_max=wave_sep_max,
        )

    def sample_gap(self, rng: random.Random) -> float:
        """One along-the-line gap [m] between consecutive released fruit."""
        return rng.uniform(self.gap_min, self.gap_max)


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
        self.samples: list[FruitSample] = []
        self.active: list[FruitSample] = []
        self._rigids: dict[int, RigidPrim] = {}
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
        #: Set to a CleatedBelt so the cleats advance with the physics loop.
        self.belt = None
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
            say(
                f"[supply] scatter pool={pool} seed={self.seed} "
                f"gaps={self.supply.gap_min:.2f}-{self.supply.gap_max:.2f} m "
                f"lateral x={self.supply.x_min:.2f}-{self.supply.x_max:.2f} m "
                f"stream={'on' if self.supply.stream else 'off'} "
                f"target={self.supply.target} "
                f"wave="
                + (
                    f"on size={self.supply.wave_size} "
                    f"gap={self.supply.wave_gap_min:.2f}-{self.supply.wave_gap_max:.2f} "
                    f"sep={self.supply.wave_sep_min:.2f}-{self.supply.wave_sep_max:.2f}"
                    if self.supply.wave
                    else "off"
                )
                + " grades="
                + ",".join(f"{key}:{weight:g}" for key, weight in self.supply.grades)
                + " classes="
                + ",".join(f"{name}:{counts.get(name, 0)}" for name in categories)
            )
        else:
            for i in range(self.cfg.num_fruits):
                category = categories[i % len(categories)]
                self._create_fruit(i, category)
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
        mass = float(shape.density * (4.0 / 3.0) * np.pi * (diameter / 2.0) ** 3 * 0.82)
        friction = self.rng.uniform(*shape.friction)
        UsdPhysics.RigidBodyAPI.Apply(prim)
        mass_api = UsdPhysics.MassAPI.Apply(prim)
        mass_api.CreateMassAttr().Set(mass)

        phys_material = UsdShade.Material.Define(self.stage, f"{path}_physmat")
        phys_api = UsdPhysics.MaterialAPI.Apply(phys_material.GetPrim())
        phys_api.CreateStaticFrictionAttr().Set(friction)
        phys_api.CreateDynamicFrictionAttr().Set(friction)
        phys_api.CreateRestitutionAttr().Set(self.rng.uniform(0.02, 0.2))
        UsdShade.MaterialBindingAPI.Apply(prim).Bind(
            phys_material, UsdShade.Tokens.weakerThanDescendants, "physics"
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

    def rescale(self, sample: FruitSample, category: str, diameter: float) -> None:
        """Change a recycled fruit's category/size (rebuilds its mesh)."""
        lo, hi = self.cfg.fruit_dimensions[category]
        sample.category = category
        sample.diameter = float(np.clip(diameter, lo, hi))
        shape = FRUIT_SHAPES[category]
        sample.mass = float(
            shape.density * (4.0 / 3.0) * np.pi * (sample.diameter / 2.0) ** 3 * 0.82
        )
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
        phys_material = UsdShade.Material.Define(stage, f"{sample.prim_path}_physmat")
        phys_api = UsdPhysics.MaterialAPI.Apply(phys_material.GetPrim())
        phys_api.CreateStaticFrictionAttr().Set(sample.friction)
        phys_api.CreateDynamicFrictionAttr().Set(sample.friction)
        phys_api.CreateRestitutionAttr().Set(self.rng.uniform(0.02, 0.2))
        UsdShade.MaterialBindingAPI.Apply(prim).Bind(
            phys_material, UsdShade.Tokens.weakerThanDescendants, "physics"
        )
        tune_contact_body(prim)

    def respawn(self, sample: FruitSample, along: float | None = None, x_jitter: float = 0.10) -> None:
        """Drop a fruit onto the belt at the upstream end.

        ``along`` overrides the along-the-line (Y) spawn position. The fruit is
        placed a few centimetres above the surface and falls onto it, so the
        physics engine never has to resolve an interpenetration.
        """
        cfg = self.cfg
        y = cfg.spawn_y if along is None else along
        if self.supply.scatter:
            x = self.rng.uniform(self.supply.x_min, self.supply.x_max)
            if along is None and self.supply.along_jitter > 0.0:
                y += self.rng.uniform(
                    -self.supply.along_jitter, self.supply.along_jitter
                )
        else:
            x = cfg.belt_center[0] + self.rng.uniform(-cfg.lateral_jitter, cfg.lateral_jitter)
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
        self._tray_dwell.clear()
        app_utils.update_app(steps=1)

    def release_next(self) -> FruitSample:
        """Randomize and drop the next queued fruit at the belt entrance.

        The cursor skips a fruit that is currently held or protected by an
        in-flight attempt: `respawn` teleports its sample upstream, and under the
        bimanual pipeline `update` runs while the other arm carries, so the
        feeder must never steal a payload (the same wrap-around teleport the
        video recorder measured, `logs/902_video_before.log`). Single-arm runs
        call `update` only between attempts, where no sample is held or
        protected, so their cursor sequence is unchanged.
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
        """
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
            if float(pos[2]) < self.cfg.belt_center[2] - 0.25:
                continue  # fell off
            if float(pos[1]) <= self.recycle_y:
                return sample  # downstream of the station: recycling is invisible
            if fallback is None:
                fallback = sample
        return fallback

    def update(self, sim_time: float) -> list[FruitSample]:
        """Release on schedule and recycle fruit that reached the downstream end."""
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
        self.enforce_transport()
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
            # not on the main belt, not on the floor. Suppress `fell_off` while it
            # is inside the discharge envelope, or it would be recycled mid-slide.
            fell_off = float(pos[2]) < self.cfg.belt_center[2] - 0.25
            if fell_off and not sample.held and self.cfg.on_output_discharge(pos):
                fell_off = False
            # Recycle fruit that reached the end of the line, or that fell off
            # the belt for any reason (small round fruit can escape).
            if along < self.cfg.despawn_y or fell_off:
                self.stats["fell_off" if fell_off else "reached_end"] += 1
                self.park(sample)
                self.active.remove(sample)
        return released

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

    def _release_gap(self) -> float:
        """One release gap [m] on the scattered line: dense-sheet pattern or uniform.

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

    def _release_clear(self, along: float) -> bool:
        """True when no live fruit already occupies `along` on the main belt."""
        for sample in self.active:
            if sample.parked or sample.held:
                continue
            pos = self.position(sample)
            if abs(float(pos[0]) - self.cfg.belt_center[0]) > 0.30:
                continue
            if abs(float(pos[1]) - float(along)) < 0.08:
                return False
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
        """
        cfg = self.cfg
        speed = max(abs(float(cfg.belt_speed)), 0.03)
        floor = float(cfg.pick_y) + 0.10
        released: list[FruitSample] = []
        while sim_time >= self._next_release and len(released) < self.supply.burst_max:
            period = self._release_period()
            late = float(sim_time) - float(self._next_release)
            along = float(cfg.spawn_y) - min(late * speed, 1.60)
            self._next_release += period
            if along < floor:
                self.stats["supply_skipped"] += 1
                continue
            if self._queue_depth() >= queue_max:
                self._next_release = max(self._next_release, sim_time + period)
                break
            if not self._release_clear(along):
                self.stats["supply_skipped"] += 1
                continue
            sample = self.release_next()
            if sample is None:
                break
            self.respawn(sample, along=along)
            released.append(sample)
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

    def enforce_transport(self, dt: float = 1.0 / 120.0) -> None:
        """Keep fruit moving on the belt.

        Transport itself is physical: the belt's surface velocity plus the rubber
        friction material carry the fruit, and the cleats push them along. This
        method only wakes a fruit that PhysX has put to sleep (a sleeping body
        ignores conveyor contact forces), so nothing freezes mid-belt.
        """
        if self.belt is not None:
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
        `FRUIT_SUPPLY_WAVE=1`, so the pre-load is the first wave), and stops
        filling once the next position would sit inside the station window
        (`pick_y + 0.12`), so the pre-load covers the selector's upstream
        window. `scatter=0` keeps the 0.30 m ladder bit-for-bit.
        """
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
