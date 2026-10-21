#!/usr/bin/env python3
"""Studio renders of the eight procedural fruit species (P29).

    scripts/run.sh scripts/29_fruit_showcase.py

Why this exists: the recorded demo frames are 424x240 with a fruit a few dozen
pixels across, so the per-species crops cut from them are blurry
(`logs/p29/fruit_sheet.png`, P29's first pass). The species are *procedural*, so
the clean image is a direct render of the same geometry rather than a
better crop.

What is rendered is the supply's own geometry - nothing is re-authored:

  * `meshes.FRUIT_SHAPES[category]` + `meshes.author_fruit(...)` /
    `meshes.author_stem(...)`, exactly the two calls `FruitSpawner._create_fruit`
    makes;
  * the diameter is the mid point of `SceneConfig.fruit_dimensions[category]`
    (the shipped per-species range), so the strawberry really is the smallest
    fruit in the scene and the apple the largest;
  * the colour is the first entry of the shape's palette - the same palette
    `_create_fruit` draws from, minus its per-instance jitter - so the eight
    thumbnails are the canonical look of each class;
  * surface noise, lobing and the stem are per-instance draws from a seeded
    `random.Random`, so a re-run reproduces the same fruit.

The scene is a neutral studio, not the sorting cell: a seamless 6 x 6 m matte
floor and the cell's own lighting rig (dome + sun + rect fill, the values in
`SortingScene._add_environment`, with the fill's distance rescaled), no arms,
belt or backdrop edge in the way. The fruit are authored as rigid bodies 1.5 mm
above the floor and settled for `FRUIT_SHOWCASE_SETTLE` ticks, so contact
shadows are real and nothing floats; they are then re-seated on the floor at
their planned grid station (the settle's contact penetration and lateral creep
are printed), which is a cosmetic correction of the solver, not of the geometry.

Two views:

  * a 4 x 2 grid lineup - one row of eight at 0.115 m pitch is 0.8 m wide, which
    at any framing that fits it leaves an apple ~27 px across, so the set is a
    compact grid instead;
  * one close-up per species, rendered with the other seven hidden (at 0.2-0.3 m
    a neighbour in the next grid row is inside the frame).

Both cameras are framed against the *rendered* fruit rather than a diameter
guess: each pass measures the saturation mask's bbox, recentres the aim on it
and rescales the eye distance, so a 3.3 cm lychee and a 6.6 cm apple fill the
same fraction of the frame with nothing clipped (the profiles are not spheres:
a pear is taller than wide, an apple's stem adds another 0.3-0.45 D).

Outputs (under `FRUIT_SHOWCASE_OUT`, default `logs/p29/`):

    fruit_<species>.png          1024x1024  one close-up per species
    fruit_showcase_wide.png      1600x1000  the eight as a 4 x 2 lineup
    fruit_showcase_sheet.png     2200x~2800 labelled contact sheet (4x2 + lineup)
    fruit_showcase_stats.txt     the per-image statistics

Every image is checked four ways: non-blank (std over the frame), the fruit is
actually in it (the saturation mask, since the studio is neutral grey), nothing
is clipped by the frame edge, and the subject is centred. The script exits
non-zero if a check fails.

Mesh density: `author_fruit(..., segments=_SEGMENTS)` defaults to 64 here against
the simulator's 28, because at 1024 px a 28-segment silhouette shows its facets.
The profile curve, per-vertex noise, lobing, colour and roughness are the shipped
ones - only the azimuthal tessellation is finer (`FRUIT_SHOWCASE_SEGMENTS=28`
renders the simulator's own density for comparison).

Knobs (all optional): `FRUIT_SHOWCASE_RES`, `_WIDE_RES`, `_SEGMENTS`,
`_PASSES`, `_SETTLE`, `_OUT`, `HEADLESS=0` to watch it.
"""

from __future__ import annotations

import os
import random
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

HEADLESS = os.environ.get("HEADLESS", "1") == "1"

from fruit_sorting.fdlimit import raise_fd_limit

# Raise the fd limit before Isaac Sim starts: this build opens ~2100
# `/dev/nvidiactl` descriptors on the first camera read and dies with
# `dup failed ... Too many open files` at the default limit.
raise_fd_limit()

_OUT_DIR = os.environ.get("FRUIT_SHOWCASE_OUT", "logs/p29")
_RES = tuple(int(v) for v in os.environ.get("FRUIT_SHOWCASE_RES", "1024,1024").split(","))
_WIDE_RES = tuple(
    int(v) for v in os.environ.get("FRUIT_SHOWCASE_WIDE_RES", "1600,1000").split(",")
)
_SEGMENTS = int(os.environ.get("FRUIT_SHOWCASE_SEGMENTS", "64"))
_PASSES = int(os.environ.get("FRUIT_SHOWCASE_PASSES", "24"))
_SETTLE = int(os.environ.get("FRUIT_SHOWCASE_SETTLE", "90"))

simulation_app = SimulationApp({"headless": HEADLESS, "width": 1280, "height": 720})

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pxr import Gf, Usd, UsdGeom, UsdPhysics, UsdShade

import isaacsim.core.experimental.utils.app as app_utils
import isaacsim.core.experimental.utils.stage as stage_utils
from isaacsim.core.experimental.objects import DistantLight, DomeLight, RectLight
from isaacsim.core.rendering_manager import RenderingManager
from isaacsim.core.simulation_manager import SimulationManager
from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import look_at_quat, to_numpy
from fruit_sorting.meshes import (
    FRUIT_SHAPES,
    author_fruit,
    author_stem,
    fruit_contact_stiffness,
    fruit_density,
    make_material,
)

#: The eight species in the supply's pool, in a stable (alphabetical) order so
#: the sheet's cells and the filenames do not depend on dict iteration.
SPECIES = ["apple", "kiwi", "lychee", "orange", "peach", "pear", "strawberry", "tomato"]

#: The set is a 2 x 4 grid: one row of eight 0.11 m apart is 0.8 m wide, which
#: at any framing that fits it makes an apple ~27 px across (`logs/p29/smoke7`),
#: while a 4 x 2 grid is 0.5 m square and shows the fruit at a readable size.
GRID_COLUMNS = 4
GRID_PITCH = 0.17

#: Camera optics. OpenUSD optics are in tenths of a scene unit, so on a metre
#: stage 0.085 is an 85 mm lens and 0.036 is a 36 mm sensor.
HERO_FOCAL = 0.085
HERO_APERTURE = 0.036
#: Eye distance per fruit diameter for the close-ups. At this focal length the
#: visible width is 0.4235 * distance, so 3.4 diameters puts the fruit at ~69 %
#: of the frame width - the same framing for a 3.7 cm strawberry and a 6.6 cm
#: apple.
HERO_DIAMETERS = 3.4
#: Fraction of the frame the close-up's longest silhouette side fills.
HERO_FILL = 0.72
HERO_AZIMUTH_DEG = 24.0
HERO_ELEVATION_DEG = 22.0

WIDE_FOCAL = 0.060
WIDE_APERTURE = 0.036
#: Fraction of the frame the whole 8-fruit set fills in the lineup shot.
WIDE_FILL = 0.84
WIDE_AZIMUTH_DEG = 0.0
WIDE_ELEVATION_DEG = 30.0

SHEET_CELL = 512
SHEET_PAD = 40
SHEET_GAP = 24
SHEET_LABEL = 62

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_BOOK = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def say(msg: str) -> None:
    """Print and flush (Kit's fast shutdown drops buffered stdout)."""
    print(f"[p29] {msg}", flush=True)


# --------------------------------------------------------------------------- #
# Studio
# --------------------------------------------------------------------------- #
def _box(stage, path: str, size: tuple[float, float, float], center, colour, roughness=0.85):
    """A unit cube scaled to `size` and translated to `center`, with a material."""
    prim = UsdGeom.Cube.Define(stage, path)
    prim.GetSizeAttr().Set(1.0)
    xform = UsdGeom.Xformable(prim)
    xform.ClearXformOpOrder()
    xform.AddTranslateOp().Set(Gf.Vec3d(*center))
    xform.AddScaleOp().Set(Gf.Vec3f(*size))
    material = make_material(stage, f"{path}_mat", colour, roughness)
    UsdShade.MaterialBindingAPI.Apply(prim.GetPrim()).Bind(material)
    return prim


def build_studio(stage) -> None:
    """Seamless neutral floor, lit with the cell's own rig.

    The light values are `SortingScene._add_environment`'s (dome 140, sun 620
    with a 2.5 deg angular size, one rect fill). Two things differ, both because
    this studio is a product set rather than a cell:

    * there is no backdrop box - the floor is 6 x 6 m and the cameras look down
      at 15-22 deg, so the whole frame is floor and there is no horizon or wall
      edge to clip (`logs/p29/smoke.log`'s first pass had the wall's dark band
      across the top of the lineup);
    * the fill sits 1.5 m in front of the row on the camera axis instead of
      3.4 m away, so its intensity follows the inverse-square ratio rather than
      copying a number that would blow out at this distance.
    """
    floor = _box(
        stage, "/World/Studio/Floor", (6.0, 6.0, 0.02), (0.0, 1.5, -0.01),
        (0.30, 0.31, 0.33), roughness=0.9,
    )
    UsdPhysics.CollisionAPI.Apply(floor.GetPrim())

    dome = DomeLight("/World/Studio/Dome", positions=[0.0, 0.2, 2.0])
    dome.set_intensities(200.0)
    dome.set_colors([0.72, 0.80, 0.92])

    sun = DistantLight("/World/Studio/Sun", positions=[3.5, -3.0, 6.0])
    sun.set_intensities(500.0)
    sun.set_colors([1.0, 0.96, 0.90])
    if hasattr(sun, "set_angles"):
        sun.set_angles(4.0)
    if hasattr(sun, "set_color_temperatures"):
        sun.set_color_temperatures(5400.0)

    fill_eye = (0.0, -1.5, 1.10)
    fill = RectLight(
        "/World/Studio/Fill",
        positions=[fill_eye],
        orientations=[look_at_quat(fill_eye, (0.0, 0.0, 0.03))],
    )
    fill.set_intensities(1500.0)
    fill.set_colors([0.95, 0.97, 1.0])
    say(
        "studio: 6x6 m floor + dome(200) + sun(500, 4deg) + rect fill(1500) "
        f"at {fill_eye}"
    )


def _fruit_physics_material(stage, path: str, friction: float, restitution: float):
    """The fruit's physics material - the shipped fields of `_create_fruit`."""
    material = UsdShade.Material.Define(stage, path)
    api = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    api.CreateStaticFrictionAttr().Set(friction)
    api.CreateDynamicFrictionAttr().Set(friction)
    api.CreateRestitutionAttr().Set(float(restitution))
    return material


# --------------------------------------------------------------------------- #
# Fruit
# --------------------------------------------------------------------------- #
def author_species(
    stage, category: str, index: int, cfg: SceneConfig, x: float, y: float
) -> dict:
    """Author one species at (x, y) resting on the floor and return its record."""
    shape = FRUIT_SHAPES[category]
    lo, hi = cfg.fruit_dimensions[category]
    diameter = 0.5 * (lo + hi)
    rng = random.Random(1000 + index)
    base = shape.colors[0]
    colour = tuple(float(np.clip(c, 0.0, 1.0)) for c in base)

    path = f"/World/Fruit/{category}"
    mesh = author_fruit(stage, path, shape, diameter, rng, colour, segments=_SEGMENTS)
    author_stem(stage, f"{path}/stem", shape, diameter, rng)

    # Sit the fruit on the floor: the authored profile's own lowest point,
    # plus 1.5 mm so the settle is a drop and never an interpenetration.
    points = np.asarray(mesh.GetPointsAttr().Get(), dtype=np.float32)
    rest_z = -float(points[:, 2].min()) + 0.0015
    xform = UsdGeom.Xformable(mesh)
    xform.ClearXformOpOrder()
    xform.AddTranslateOp().Set(Gf.Vec3d(float(x), float(y), rest_z))

    prim = mesh.GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(prim)
    mass = float(
        fruit_density(shape) * (4.0 / 3.0) * np.pi * (diameter / 2.0) ** 3 * 0.82
    )
    UsdPhysics.MassAPI.Apply(prim).CreateMassAttr().Set(mass)
    friction = float(0.5 * (shape.friction[0] + shape.friction[1]))
    material = _fruit_physics_material(stage, f"{path}_physmat", friction, 0.05)
    UsdShade.MaterialBindingAPI.Apply(prim).Bind(
        material, UsdShade.Tokens.weakerThanDescendants, "physics"
    )

    triangles = len(mesh.GetFaceVertexIndicesAttr().Get()) // 3
    return {
        "points": points.astype(np.float64),
        "category": category,
        "diameter": diameter,
        "colour": colour,
        "roughness": shape.roughness,
        "verts": int(points.shape[0]),
        "tris": int(triangles),
        "mass": mass,
        "friction": friction,
        "stiffness": fruit_contact_stiffness(shape),
        "placed": np.array([x, y, rest_z]),
        "path": path,
    }


def world_points(stage, path: str, points: np.ndarray) -> np.ndarray:
    """The authored mesh points in world space (physics writes the prim's xform).

    USD stores row-vector matrices, so the 3x3 block is transposed relative to
    the column-vector convention numpy uses.
    """
    matrix = np.array(
        UsdGeom.Xformable(stage.GetPrimAtPath(path)).ComputeLocalToWorldTransform(
            Usd.TimeCode.Default()
        )
    )
    rotation = matrix[:3, :3].T
    translation = matrix[3, :3]
    return points @ rotation.T + translation


# --------------------------------------------------------------------------- #
# Cameras and frames
# --------------------------------------------------------------------------- #
def make_camera(path: str, size, focal: float, aperture: float):
    """A camera + RGB sensor. `size` is (width, height), the way screens read.

    `CameraSensor` takes `resolution` in OpenCV order, `(height, width)`
    (`camera_sensor.py`), so the tuple is flipped here and nowhere else. Only the
    horizontal aperture is set: the sensor's `enforce_square_pixels` derives the
    vertical one from the render aspect, which is what keeps a 16:9 line-up from
    being squeezed by a square film back.
    """
    width, height = size
    eye = (0.0, -1.0, 0.2)
    camera = RtxCamera(
        path, tick_rate=0.0, positions=[eye], orientations=[look_at_quat(eye, (0.0, 0.0, 0.0))]
    )
    camera.camera.set_focal_lengths(focal)
    camera.camera.set_apertures((aperture, aperture))
    camera.camera.set_focus_distances(1.0)
    camera.camera.set_clipping_ranges(0.005, 50.0)
    sensor = CameraSensor(camera, resolution=(height, width), annotators=["rgb"])
    say(f"camera {path} res={width}x{height} focal={focal * 1000:.0f}mm")
    return camera, sensor


def render_rgb(sensor, label: str, passes: int | None = None) -> np.ndarray | None:
    """Converge the view and return its RGB frame.

    Two repo rules meet here: `RenderingManager.render()` must run before
    `get_data` (the first annotated frame after `play()` can be empty), and TAA
    needs several passes before a still is clean - one pass leaves the edges
    crawling. `update_app(steps=0)` is the pump that services the sensor
    callbacks without advancing physics, which matters because the poses set
    here are the ones in the picture.
    """
    # A camera moved with `set_world_poses` does not reach the render product
    # until the app pumps: the first frame batch after a move renders the *old*
    # pose (measured on the first framing pass, logs/p29), so flush one frame and
    # drain its buffer before the passes that count.
    RenderingManager.render()
    app_utils.update_app(steps=0)
    sensor.get_data("rgb")

    for attempt in range(6):
        for _ in range(max(1, (passes or _PASSES) // 2)):
            RenderingManager.render()
        app_utils.update_app(steps=0)
        array = to_numpy(sensor.get_data("rgb"))
        if array is not None:
            array = np.asarray(array)
            if array.ndim == 4:
                array = array[0]
            if array.ndim == 3 and array.shape[2] >= 3 and array.size:
                return array[..., :3].astype(np.uint8)
        say(f"{label}: no frame on attempt {attempt + 1} (got {None if array is None else np.shape(array)})")
    return None


def fruit_mask(rgb: np.ndarray) -> np.ndarray:
    """Saturation mask: the studio is neutral grey, every species is coloured."""
    a = rgb.astype(np.float32) / 255.0
    return (a.max(axis=2) - a.min(axis=2) > 0.16) & (a.max(axis=2) > 0.06)


def mask_bbox(rgb: np.ndarray):
    """(x0, y0, x1, y1) of the fruit mask, or None."""
    ys, xs = np.nonzero(fruit_mask(rgb))
    if xs.size == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def stats(rgb: np.ndarray) -> dict:
    """Mean/std, a colour mask for the fruit, its bbox and the Laplacian variance."""
    a = rgb.astype(np.float32) / 255.0
    fruit = fruit_mask(rgb)
    fraction = float(fruit.mean())
    ys, xs = np.nonzero(fruit)
    bbox = None
    offset = (0.0, 0.0)
    if xs.size:
        bbox = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
        offset = (
            float(0.5 * (xs.min() + xs.max()) - 0.5 * (rgb.shape[1] - 1)),
            float(0.5 * (ys.min() + ys.max()) - 0.5 * (rgb.shape[0] - 1)),
        )
    grey = a.mean(axis=2)
    laplacian = (
        -4.0 * grey[1:-1, 1:-1]
        + grey[:-2, 1:-1]
        + grey[2:, 1:-1]
        + grey[1:-1, :-2]
        + grey[1:-1, 2:]
    )
    return {
        "mean": tuple(float(v) for v in a.mean(axis=(0, 1))),
        "std": tuple(float(v) for v in a.std(axis=(0, 1))),
        "std_grey": float(grey.std()),
        "fruit_fraction": fraction,
        "bbox": bbox,
        "offset": offset,
        "sharpness": float(laplacian.var()) * 1e3,
    }


def stats_line(label: str, rgb: np.ndarray, s: dict) -> str:
    return (
        f"{label:22s} {rgb.shape[1]}x{rgb.shape[0]} "
        f"mean=({s['mean'][0]:.2f},{s['mean'][1]:.2f},{s['mean'][2]:.2f}) "
        f"std=({s['std'][0]:.2f},{s['std'][1]:.2f},{s['std'][2]:.2f}) "
        f"fruit={100.0 * s['fruit_fraction']:5.1f}% "
        f"bbox={s['bbox']} off=({s['offset'][0]:+.0f},{s['offset'][1]:+.0f})px "
        f"sharp={s['sharpness']:.2f}"
    )


# --------------------------------------------------------------------------- #
# Contact sheet
# --------------------------------------------------------------------------- #
def _font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def build_sheet(cells: list[dict], wide: np.ndarray | None, path: str) -> None:
    """Label a 4x2 grid of the close-ups, with the lineup strip underneath."""
    columns = 4
    rows = (len(cells) + columns - 1) // columns
    width = SHEET_PAD * 2 + SHEET_CELL * columns + SHEET_GAP * (columns - 1)
    grid_height = rows * (SHEET_CELL + SHEET_LABEL) + SHEET_GAP * (rows - 1)
    title_height = 128
    wide_height = 0
    wide_caption = 0
    if wide is not None:
        wide_height = int(round((width - 2 * SHEET_PAD) * wide.shape[0] / wide.shape[1]))
        wide_caption = 54
    height = (
        title_height + grid_height + wide_height + wide_caption + 2 * SHEET_PAD
        + (SHEET_GAP + 44 if wide is not None else 0)
    )

    sheet = Image.new("RGB", (width, height), (18, 20, 24))
    draw = ImageDraw.Draw(sheet)
    draw.text(
        (SHEET_PAD, SHEET_PAD),
        "Procedural fruit - Isaac Sim render",
        font=_font(FONT_BOLD, 44),
        fill=(238, 240, 244),
    )
    draw.text(
        (SHEET_PAD, SHEET_PAD + 62),
        "8 supply species, authored geometry (meshes.author_fruit / author_stem), "
        f"mid-range diameter, {_RES[0]}x{_RES[1]} per species",
        font=_font(FONT_BOOK, 21),
        fill=(150, 156, 166),
    )

    top = title_height + SHEET_PAD
    for index, cell in enumerate(cells):
        column, row = index % columns, index // columns
        x = SHEET_PAD + column * (SHEET_CELL + SHEET_GAP)
        y = top + row * (SHEET_CELL + SHEET_LABEL + SHEET_GAP)
        tile = Image.fromarray(cell["rgb"]).resize(
            (SHEET_CELL, SHEET_CELL), Image.LANCZOS
        )
        sheet.paste(tile, (x, y))
        label_font = _font(FONT_BOLD, 29)
        detail_font = _font(FONT_BOOK, 21)
        draw.text(
            (x + 2, y + SHEET_CELL + 6),
            f"{cell['category']}  ({cell['diameter'] * 100:.1f} cm)",
            font=label_font,
            fill=(235, 238, 242),
        )
        draw.text(
            (x + 2, y + SHEET_CELL + 38),
            f"RGB {cell['colour'][0]:.2f},{cell['colour'][1]:.2f},{cell['colour'][2]:.2f}"
            f"  rough {cell['roughness']:.2f}",
            font=detail_font,
            fill=(136, 142, 152),
        )

    if wide is not None:
        y = top + grid_height + SHEET_GAP + 44
        tile = Image.fromarray(wide).resize(
            (width - 2 * SHEET_PAD, wide_height), Image.LANCZOS
        )
        sheet.paste(tile, (SHEET_PAD, y))
        draw.text(
            (SHEET_PAD, y + wide_height + 12),
            "lineup: the eight species at their shipped mid-range diameter, "
            f"{_WIDE_RES[0]}x{_WIDE_RES[1]}",
            font=_font(FONT_BOOK, 21),
            fill=(150, 156, 166),
        )

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    sheet.save(path)
    say(f"saved {path} ({width}x{height})")


# --------------------------------------------------------------------------- #
def main() -> int:
    cfg = SceneConfig()
    out_dir = _OUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    stage_utils.create_new_stage()
    stage = stage_utils.get_current_stage()
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    if not stage.GetPrimAtPath("/World").IsValid():
        stage.DefinePrim("/World", "Xform")

    build_studio(stage)

    # A 4 x 2 grid centred on the origin: columns along +x, rows along +y.
    columns = GRID_COLUMNS
    rows = (len(SPECIES) + columns - 1) // columns
    fruit = []
    for index, category in enumerate(SPECIES):
        column, row = index % columns, index // columns
        x = (column - 0.5 * (columns - 1)) * GRID_PITCH
        y = (row - 0.5 * (rows - 1)) * GRID_PITCH
        record = author_species(stage, category, index, cfg, x, y)
        fruit.append(record)
        say(
            f"authored {category:11s} d={record['diameter'] * 100:5.2f} cm "
            f"mass={record['mass'] * 1000:5.1f} g mu={record['friction']:.2f} "
            f"colour={tuple(round(c, 2) for c in record['colour'])} "
            f"verts={record['verts']} tris={record['tris']}"
        )

    hero_camera, hero_sensor = make_camera(
        "/World/HeroCamera", _RES, HERO_FOCAL, HERO_APERTURE
    )
    wide_camera, wide_sensor = make_camera(
        "/World/WideCamera", _WIDE_RES, WIDE_FOCAL, WIDE_APERTURE
    )

    # Settle: the fruit are rigid bodies 1.5 mm above the floor.
    SimulationManager.set_backend("torch")
    SimulationManager.switch_physics_engine("physx")
    SimulationManager.set_physics_dt(1.0 / 120.0)
    app_utils.play(commit=True)
    SimulationManager.step(steps=_SETTLE)
    app_utils.update_app(steps=0)
    say(f"settled {_SETTLE} ticks ({_SETTLE / 120.0:.2f} s)")

    # The settle is a *dropped* rigid body, so it lands with PhysX's contact
    # penetration (a 2-5 mm cut into the floor, measured in logs/p29) and a few
    # millimetres of solver creep along x/y (2-13 mm on the facet-edged meshes).
    # Both are reported, then undone by re-seating each body on the floor at its
    # planned station: the images are meant to show the geometry, not the
    # contact solver, and at 1024 px a 3 mm sink on a 33 mm lychee is ~90 px of
    # the fruit. The settle still decides the resting *attitude*, which is what
    # it is here for.
    for record in fruit:
        points = record["points"]
        settled = world_points(stage, record["path"], points)
        sink = float(settled[:, 2].min())
        drift = float(np.hypot(settled[:, 0].mean() - record["placed"][0],
                               settled[:, 1].mean() - record["placed"][1]))
        translate = UsdGeom.Xformable(
            stage.GetPrimAtPath(record["path"])
        ).GetTranslateOp()
        current = np.array(translate.Get(), dtype=float)
        translate.Set(
            Gf.Vec3d(
                float(record["placed"][0]),
                float(record["placed"][1]),
                float(current[2] - sink),
            )
        )
        seated = world_points(stage, record["path"], points)
        record["centre"] = 0.5 * (seated.min(axis=0) + seated.max(axis=0))
        record["height"] = float(seated[:, 2].max() - seated[:, 2].min())
        say(
            f"settled {record['category']:11s} penetration={-sink * 1000:5.2f} mm "
            f"creep={drift * 1000:5.2f} mm -> seated z="
            f"{seated[:, 2].min() * 1000:+.3f}..{seated[:, 2].max() * 1000:.2f} mm"
        )

    # --- framing --------------------------------------------------------- #
    # Both shots are framed against the rendered fruit instead of a size guess:
    # the profiles are not spheres (a pear is taller than wide, an apple's stem
    # adds another 0.3-0.45 D) and aiming at the prim origin put the apple 48 px
    # off centre with its top cut off (`logs/p29/smoke.log`). Each pass measures
    # the saturation mask's bbox, recentres the aim on it and rescales the eye
    # distance so the subject fills `fill` of the frame. Two corrections are
    # enough; the last pass is the image that is kept.
    def frame(camera, sensor, centre, direction, distance, fill, label, focal, aperture):
        back = direction / np.linalg.norm(direction)
        # Camera basis for look_at_quat's convention: X right, Y up, Z back.
        right = np.cross([0.0, 0.0, 1.0], back)
        right /= np.linalg.norm(right)
        up = np.cross(back, right)
        half_fov = np.arctan(aperture / (2.0 * focal))
        centre = np.array(centre, dtype=float)
        rgb = None
        for iteration in range(3):
            eye = centre + distance * direction
            camera.set_world_poses(
                positions=[eye], orientations=[look_at_quat(eye, centre)]
            )
            # The correction passes only need a mask, so they do not pay for the
            # full TAA convergence.
            rgb = render_rgb(
                sensor, f"{label}#{iteration}", passes=_PASSES if iteration == 2 else 6
            )
            if rgb is None:
                raise RuntimeError(f"{label}: the camera returned no frame")
            box = mask_bbox(rgb)
            if box is None:
                raise RuntimeError(f"{label}: no fruit in the frame")
            width, height = rgb.shape[1], rgb.shape[0]
            extent = max(box[2] - box[0] + 1, box[3] - box[1] + 1) / float(width)
            du = 0.5 * (box[0] + box[2]) - 0.5 * (width - 1)
            dv = 0.5 * (box[1] + box[3]) - 0.5 * (height - 1)
            # The pan is measured at the distance this frame was taken at, so it
            # uses that distance for the pixel size; the rescale is applied after
            # it. (Using the new distance for both overshot: the correction
            # factor reaches 1.4 on the first pass.)
            world_per_px = 2.0 * distance * np.tan(half_fov) / width
            factor = min(2.0, max(0.5, extent / fill))
            say(
                f"  {label:16s} pass {iteration}: d={distance * 100:5.1f} cm "
                f"fill={extent:.2f} off=({du:+.0f},{dv:+.0f})px -> x{factor:.3f}"
            )
            centre = centre + right * (du * world_per_px) - up * (dv * world_per_px)
            distance *= factor
        return rgb, centre, distance

    def unit(azimuth_deg, elevation_deg):
        azimuth = np.radians(azimuth_deg)
        elevation = np.radians(elevation_deg)
        return np.array(
            [
                np.sin(azimuth) * np.cos(elevation),
                -np.cos(azimuth) * np.cos(elevation),
                np.sin(elevation),
            ]
        )

    # --- the lineup ------------------------------------------------------- #
    # Aim at the set's own centre: the middle of the grid at half the tallest
    # fruit's height, so the two rows sit on the frame's centre line.
    group_centre = np.array(
        [
            0.5 * (fruit[0]["centre"][0] + fruit[GRID_COLUMNS - 1]["centre"][0]),
            0.5 * (fruit[0]["centre"][1] + fruit[-1]["centre"][1]),
            0.5 * max(r["height"] for r in fruit),
        ]
    )
    wide, _, wide_distance = frame(
        wide_camera,
        wide_sensor,
        group_centre,
        unit(WIDE_AZIMUTH_DEG, WIDE_ELEVATION_DEG),
        1.2,
        WIDE_FILL,
        "lineup",
        WIDE_FOCAL,
        WIDE_APERTURE,
    )
    wide_stats = stats(wide)
    wide_path = os.path.join(out_dir, "fruit_showcase_wide.png")
    Image.fromarray(wide).save(wide_path)
    say(f"saved {wide_path}")
    # Does the paused-timeline assumption hold - i.e. did the renders move the
    # bodies, which would undo the re-seat and put the contact sink back?
    lowest = min(
        float(world_points(stage, r["path"], r["points"])[:, 2].min()) for r in fruit
    )
    say(f"floor contact after the lineup render: {lowest * 1000:+.3f} mm (0 = untouched)")
    wide_line = stats_line("lineup", wide, wide_stats)
    say(wide_line)
    lines = [wide_line]
    if wide_stats["std_grey"] < 0.02 or wide_stats["fruit_fraction"] < 0.010:
        raise RuntimeError(
            "the lineup is blank or does not show the set "
            f"(std={wide_stats['std_grey']:.3f}, "
            f"fruit={100.0 * wide_stats['fruit_fraction']:.2f}% of the frame)"
        )

    # --- one close-up per species ---------------------------------------- #
    # Each close-up renders its species alone. At 0.2-0.3 m the neighbour in the
    # next grid row is inside the frame (measured: the apple's shot had the
    # orange in it, which also drove the framing loop with two masks), and a
    # single subject is what a species thumbnail should show anyway. Visibility
    # is a render property, so the rigid bodies and their poses are untouched.
    def show_only(keep: str | None) -> None:
        for record in fruit:
            imageable = UsdGeom.Imageable(stage.GetPrimAtPath(record["path"]))
            if keep is None or record["category"] == keep:
                imageable.MakeVisible()
            else:
                imageable.MakeInvisible()

    cells = []
    for record in fruit:
        show_only(record["category"])
        rgb, _, camera_distance = frame(
            hero_camera,
            hero_sensor,
            record["centre"],
            unit(HERO_AZIMUTH_DEG, HERO_ELEVATION_DEG),
            HERO_DIAMETERS * record["diameter"],
            HERO_FILL,
            record["category"],
            HERO_FOCAL,
            HERO_APERTURE,
        )
        record["camera_distance"] = camera_distance
        s = stats(rgb)
        path = os.path.join(out_dir, f"fruit_{record['category']}.png")
        Image.fromarray(rgb).save(path)
        line = stats_line(record["category"], rgb, s)
        say(f"saved {path}")
        say(line)
        lines.append(line)
        cells.append({**record, "rgb": rgb, "stats": s})
        if s["std_grey"] < 0.02 or s["fruit_fraction"] < 0.02:
            raise RuntimeError(
                f"{record['category']}: the frame is blank or the fruit is missing "
                f"(std={s['std_grey']:.3f}, fruit={100.0 * s['fruit_fraction']:.2f}%)"
            )
        if s["bbox"] is None or min(s["bbox"][0], s["bbox"][1]) < 2 or max(
            s["bbox"][2], s["bbox"][3]
        ) > rgb.shape[1] - 3:
            raise RuntimeError(
                f"{record['category']}: the fruit is clipped by the frame "
                f"(bbox={s['bbox']} of {rgb.shape[1]}x{rgb.shape[0]})"
            )
        limit = 0.04 * rgb.shape[1]
        if max(abs(s["offset"][0]), abs(s["offset"][1])) > limit:
            raise RuntimeError(
                f"{record['category']}: off centre by {s['offset']} px "
                f"(limit {limit:.0f})"
            )
        if s["fruit_fraction"] > 0.60:
            raise RuntimeError(
                f"{record['category']}: the mask covers "
                f"{100.0 * s['fruit_fraction']:.0f}% of the frame - more than one "
                "subject or a saturated background"
            )
    show_only(None)

    sheet_path = os.path.join(out_dir, "fruit_showcase_sheet.png")
    build_sheet(cells, wide, sheet_path)

    stats_path = os.path.join(out_dir, "fruit_showcase_stats.txt")
    with open(stats_path, "w", encoding="utf-8") as fh:
        fh.write(
            f"script      scripts/29_fruit_showcase.py\n"
            f"hero        {_RES[0]}x{_RES[1]}  focal {HERO_FOCAL * 1000:.0f} mm  "
            f"segments {_SEGMENTS}  passes {_PASSES}  settle {_SETTLE} ticks\n"
            f"wide        {_WIDE_RES[0]}x{_WIDE_RES[1]}  focal {WIDE_FOCAL * 1000:.0f} mm\n"
            f"sheet       {sheet_path}\n\n"
        )
        for line in lines:
            fh.write(line + "\n")
        fh.write("\nspecies geometry\n")
        for record in fruit:
            fh.write(
                f"{record['category']:11s} d={record['diameter'] * 100:5.2f} cm "
                f"colour=({record['colour'][0]:.2f},{record['colour'][1]:.2f},"
                f"{record['colour'][2]:.2f}) rough={record['roughness']:.2f} "
                f"verts={record['verts']} tris={record['tris']} "
                f"mass={record['mass'] * 1000:.1f} g mu={record['friction']:.2f}\n"
            )
    say(f"saved {stats_path}")
    say("DONE")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except BaseException:
        os.makedirs(_OUT_DIR, exist_ok=True)
        with open(os.path.join(_OUT_DIR, "traceback.txt"), "w", encoding="utf-8") as fh:
            traceback.print_exc(file=fh)
        say(f"FAILED - see {_OUT_DIR}/traceback.txt")
        code = 1
    finally:
        app_utils.pause()
        simulation_app.close()
    raise SystemExit(code)
