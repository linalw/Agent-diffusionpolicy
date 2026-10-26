"""P44 phase 1 - CAP_CENSUS: every cap that limits how fast this cell moves.

Offline, read-only: parses the shipped USD drives and the `[motion]`/`[cycle]`
rows of the given logs, and re-derives every leg's duration from the *real*
`fruit_sorting.motion` model (that module imports numpy only, no Isaac). No
simulator, no `src/` write.

    python3 logs/p44/cap_census.py                 # the default battery set
    python3 logs/p44/cap_census.py --log <file>    # one battery (repeatable)
    python3 logs/p44/cap_census.py --write         # logs/p44/CAP_CENSUS_out.txt

Sections
  A  the drives: USD authoring vs runtime units, tau = c/k, the joint velocity
     and effort limits, the gain knobs, and the cap register (knob/default/site)
  B  per leg: measured ticks vs the ticks the shipped caps predict, and which of
     v_max / a_max / j_max binds
  C  the `[cycle]` per-phase means, per battery + the shipped-branch means
  D  the fixed tick budgets (open-loop clocks) and the share of their phase
  E  headroom: what each cap would buy and which term binds next
  F  do the joint velocity / effort limits bind?
  G  the following error and the two cap classes (clock vs convergence)
  H  the ranked "raise the cap" candidates

Reading rules inherited from `logs/p43/RATE_LEDGER.md`: a count is one draw of an
attractor, `[cycle]` `descent` is `wait + descent`, and the two-line's
`s/attempt` is a batch span divided by two concurrent arms.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import statistics as stats
import sys
from collections import Counter
from dataclasses import dataclass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

import numpy as np  # noqa: E402

from fruit_sorting.motion import (  # noqa: E402
    TrajectoryLimits,
    accel_budget,
    cone_scale,
    jerk_limited,
)

CONTROL_DT = 1.0 / 120.0
USD = os.path.join(ROOT, "assets", "openarm_flat", "openarm_flat_deinst.usda")
#: shipped defaults of the two grip-side knobs the cone is built from
MU_SAFETY = 0.6
GRIPPER_MU = 2.0
MU_EFF = MU_SAFETY * GRIPPER_MU

DEFAULT_LOGS = [
    # the shipped single-arm branch (P41 record; P43's d0 stream is identical)
    "logs/p41/p2/accept_profile.log",
    "logs/p41/p2/pear_profile.log",
    # the shipped two-line branch
    "logs/p41/p2/twoline_profile.log",
    # the shipped single-arm branch *with* `[cycle]` marks (P43 phase 2)
    "logs/p43/p2/d0_accept_A_s5.log",
]
DEFAULT_INDEXED = ["logs/fast/16_accept_indexed_v7.log"]
#: the pre-dynamic (indexed descent into the belt) end-gap reference
HISTORIC_END = ["logs/161_accept_endmetric.log"]

# `carry` rows: leg, distance, ticks, then several independent fields whose order
# changes between the shipped and the P41+ rows (`cone=` sits before `ends |v|=`).
CARRY_HEAD = re.compile(r"\[motion\] carry (?P<leg>\w+): (?P<d>[\d.]+) cm, (?P<ticks>\d+) ticks")


def parse_carry(line: str) -> dict | None:
    head = CARRY_HEAD.search(line)
    if head is None:
        return None
    vmax = re.findall(r"\|v\|max=([\d.]+) m/s", line)
    amax = re.findall(r"\|a\|max=([\d.]+) m/s\^2", line)
    cmd = re.search(r"\|v\|cmd=([\d.]+) \|a\|cmd=([\d.]+)", line)
    ends = re.search(r"ends \|v\|=([\d.]+)/([\d.]+) m/s", line)
    cone = re.search(r"cone=([\d.]+)x budget", line)
    win = re.search(r"a_win5=([\d.]+) m/s\^2", line)
    return {
        "leg": head.group("leg"),
        "d": float(head.group("d")) / 100.0,
        "ticks": float(head.group("ticks")),
        "vcmd": float(cmd.group(1)) if cmd else 0.0,
        "acmd": float(cmd.group(2)) if cmd else 0.0,
        "vact": float(vmax[-1]) if vmax else 0.0,   # the last is the achieved hand speed
        "aact": float(amax[-1]) if amax else 0.0,
        "v_end": float(ends.group(2)) if ends else 0.0,
        "cone": float(cone.group(1)) if cone else 0.0,
        "win": float(win.group(1)) if win else 0.0,
    }


APPROACH = re.compile(
    r"\[motion\] approach\((?P<mode>\w+)\): (?P<d>[\d.]+) cm, (?P<ticks>\d+) samples:"
    r".*?\|v\|max=(?P<vact>[\d.]+) m/s, \|a\|max=(?P<aact>[\d.]+) m/s\^2"
    r".*?ends \|v\|=(?P<v0>[\d.]+)/(?P<v1>[\d.]+) m/s"
    r"(?:.*?end=(?P<end>[\d.]+) mm)?"
)
CYCLE = re.compile(r"\[cycle\] attempt \d+: (?P<body>.*)")
PHASE = re.compile(r"(\w+)=([\d.]+)s")
PICKPOSE = re.compile(r"at pick pose after ([\d.]+) s \(residual=([\d.]+) m\)")
ARRIVAL = re.compile(r"fruit at pick point .*after (\d+) steps")
WAITED = re.compile(r"dynamic descent: waited (\d+) ticks")
CLOSE_T = re.compile(r"dynamic close: sustained contact after (\d+) ticks")
PLACE_LOW = re.compile(r"place low: .*?, (\d+) ticks")
STATS = re.compile(r"\[stats\] attempts=(\d+) successes=(\d+).*?sim=([\d.]+)s")


# --------------------------------------------------------------------------- #
# A. the drives
# --------------------------------------------------------------------------- #
@dataclass
class Joint:
    name: str
    kind: str
    stiffness: float | None
    damping: float | None
    max_force: float | None
    lo: float | None
    hi: float | None
    max_vel: float | None
    inertia: float | None


def _fl(block: str, attr: str) -> float | None:
    # `attr` is a regex fragment (`drive:\w+:physics:stiffness`), not escaped.
    match = re.search(rf"float {attr} = ([-\d.eE+]+)", block)
    return None if match is None else float(match.group(1))


def parse_usd(path: str = USD) -> list[tuple[int, Joint]]:
    """Every joint block of the shipped flat OpenArm asset, in authoring units."""
    with open(path, "r", encoding="utf-8") as handle:
        lines = handle.readlines()
    text = "".join(lines)
    out: list[tuple[int, Joint]] = []
    head = re.compile(r'def Physics(\w+?)Joint "([^"]+)"')
    for match in head.finditer(text):
        start = match.end()
        nxt = re.search(r"\n {12}def ", text[start: start + 4000])
        block = text[start: start + (nxt.start() if nxt else 4000)]
        line_no = text[: match.start()].count("\n") + 1
        out.append(
            (
                line_no,
                Joint(
                    name=match.group(2),
                    kind=match.group(1),
                    stiffness=_fl(block, r"drive:\w+:physics:stiffness"),
                    damping=_fl(block, r"drive:\w+:physics:damping"),
                    max_force=_fl(block, r"drive:\w+:physics:maxForce"),
                    lo=_fl(block, r"physics:lowerLimit"),
                    hi=_fl(block, r"physics:upperLimit"),
                    max_vel=_fl(block, r"physxJoint:maxJointVelocity"),
                    inertia=_fl(block, r"physics:JointEquivalentInertia"),
                ),
            )
        )
    return out


def section_a(joints: list[tuple[int, Joint]]) -> None:
    print("=" * 96)
    print("A. THE DRIVES  (assets/openarm_flat/openarm_flat_deinst.usda, authoring units)")
    print("=" * 96)
    print("The USD authors every arm drive PER DEGREE; Isaac reads them back PER RADIAN")
    print("(x 57.29578, verified at runtime in logs/164_gains_probe.log).\n")
    deg = math.pi / 180.0
    print(f"{'joint':26s} {'line':>5s} {'k[deg]':>7s} {'k[rad]':>9s} {'c[rad]':>8s} "
          f"{'tau':>6s} {'Fmax':>5s} {'sat.err':>8s} {'vlim':>7s} {'vlim':>7s} {'range[deg]':>16s}")
    print(f"{'':26s} {'':>5s} {'N/m|Nm/deg':>7s} {'':>9s} {'Ns/m|Nms/rad':>8s} "
          f"{'s':>6s} {'':>5s} {'':>8s} {'deg/s':>7s} {'rad/s':>7s}")
    for line_no, joint in joints:
        if joint.name.startswith(("openarm_left_", "openarm_right_")):
            pass
        if joint.kind == "Prismatic":
            if joint.stiffness is None:
                continue
            print(f"{joint.name:26s} {line_no:5d} {joint.stiffness:7.0f} {'[N/m]':>9s} "
                  f"{(joint.damping or 0):8.0f} {'-':>6s} {str(joint.max_force):>5s} "
                  f"{(joint.max_force / joint.stiffness * 1e3 if joint.stiffness else 0):7.2f}m "
                  f"{str(joint.max_vel):>7s} {'-':>7s} "
                  f"{'0..44 mm':>16s}")
            continue
        if joint.stiffness is None or joint.name.endswith(("_hand", "_ee_tcp_joint")):
            continue
        k_rad = joint.stiffness / deg
        c_rad = (joint.damping or 0.0) / deg
        tau = c_rad / k_rad if k_rad else float("inf")
        sat = (joint.max_force / k_rad * 1e3) if (joint.max_force and k_rad) else float("nan")
        vdeg = joint.max_vel or 0.0
        print(f"{joint.name:26s} {line_no:5d} {joint.stiffness:7.0f} {k_rad:9.1f} {c_rad:8.1f} "
              f"{tau:6.3f} {joint.max_force:5.0f} {sat:7.2f}m {vdeg:7.1f} {vdeg * deg:7.2f} "
              f"{joint.lo:7.1f}..{joint.hi:7.1f}")
    print("\n`sat.err` = maxForce / k[rad]: the joint error at which the drive saturates.")
    print("`tau` = c/k: the closed-loop following error for a ramp at v is ~v*tau (G).")

    print("\nA2. THE GAIN KNOBS  (control.py)")
    print("  FRUIT_TUNE_GAINS      default \"0\"  control.py:214   =1 -> set_dof_gains(k, c, arm_dofs)")
    print("  FRUIT_ARM_STIFFNESS   default 1500  control.py:215   only read when TUNE_GAINS=1")
    print("  FRUIT_ARM_DAMPING     default 60    control.py:216   only read when TUNE_GAINS=1")
    print("  finger profile        k=1e5 c=2000  control.py:234-236 (P41 `finger_damp02`,")
    print("                        c/k = 0.02; FRUIT_FINGER_STIFFNESS=0 restores the asset's 1e6/100)")
    print("  No script or shell driver in the tree sets FRUIT_TUNE_GAINS: the *shipped* arm")
    print("  drive is the asset's own k=22918 / c=4583 (tau 0.200 s) and the tuned pair is")
    print("  an opt-in experiment (measured null on the descent's arrival, logs/165).")
    for k, c in ((22918.312, 4583.663), (1500.0, 60.0)):
        print(f"    k={k:9.1f} c={c:8.1f}  tau={c / k:6.3f} s  v*tau at 0.15 m/s = "
              f"{0.15 * c / k * 1000:5.2f} mm   at 0.35 m/s = {0.35 * c / k * 1000:5.2f} mm")

    print("\nA3. THE CAP REGISTER  (shipped defaults; a * is a two-line-scoped default)")
    print(f"  {'knob':34s} {'default':>9s}  {'site':22s} bounds")
    for knob, default, site, bounds in CAP_REGISTER:
        print(f"  {knob:34s} {default:>9s}  {site:22s} {bounds}")


CAP_REGISTER = [
    ("FRUIT_CARRY_VMAX", "0.38", "motion.py:174", "every carry leg's speed cap [m/s]"),
    ("FRUIT_CARRY_AMAX", "2.0", "motion.py:175", "every carry leg's accel cap [m/s^2]"),
    ("FRUIT_CARRY_JMAX", "25", "motion.py:176", "jerk cap [m/s^3]; cone sets j=10a when it binds"),
    ("FRUIT_LIFT_VMAX", "0.18", "tasks.py:3379", "indexed/policy grasp_lift speed"),
    ("FRUIT_LIFT_AMAX", "1.0", "tasks.py:3380", "indexed/policy grasp_lift accel"),
    ("FRUIT_DYNAMIC_LIFT_VMAX", "0.30", "tasks.py:3399", "dynamic grasp_lift speed (the shipped line)"),
    ("FRUIT_DYNAMIC_LIFT_AMAX", "1.0", "tasks.py:3402", "dynamic grasp_lift accel"),
    ("FRUIT_DYNAMIC_PLACE_VMAX", "0.35", "tasks.py:3424", "dynamic place0/place1 speed (0 = off)"),
    ("FRUIT_DYNAMIC_PLACE_AMAX", "1.089", "tasks.py:3427", "dynamic place accel (0 = off)"),
    ("FRUIT_PLACE_LOW_VMAX", "0.30", "tasks.py:12191", "the release's vertical drop speed"),
    ("FRUIT_PLACE_LOW_AMAX", "2.0", "tasks.py:12192", "the release's drop accel (cone clips to 1.962)"),
    ("FRUIT_PLACE_LOW_STEPS", "40", "tasks.py:12123", "drop ramp floor; the profile length wins"),
    ("FRUIT_DYNAMIC_APPROACH_VMAX", "0.15", "tasks.py:5937,9352", "dynamic descent speed"),
    ("FRUIT_APPROACH_AMAX", "0.8", "tasks.py:9354", "dynamic descent accel"),
    ("FRUIT_APPROACH_VMAX", "0.03", "tasks.py:13083,13103", "indexed (policy-handover) descent speed"),
    ("FRUIT_MU_SAFETY", "0.6", "tasks.py:3366,12193", "cone scale: mu_eff = 0.6 x gripper.mu(2.0)"),
    ("FRUIT_IK_DAMPING", "0.05", "control.py:145", "damped-LS lambda; regularisation only"),
    ("FRUIT_IK_GAIN", "1.0", "control.py:146", "dq multiplier (1.0 = no cap)"),
    ("FRUIT_IK_MAX_STEP", "0.5", "control.py:147,423", "per-tick |dq| clamp [rad] (joint space)"),
    ("FRUIT_IK_RATE", "0.0", "control.py:479", "per-tick |dq| rate cap (0 = off)"),
    ("FRUIT_IK_WARN", "0.0", "control.py:486", "reporting only"),
    ("FRUIT_HOVER_STEP", "0.04", "tasks.py:8282", "hover move's |dq| clamp [rad] (grasp.py: 0.20)"),
    ("FRUIT_DYNAMIC_HOVER_MOVE", "300", "tasks.py:8285", "hover move's max iterations"),
    ("FRUIT_DYNAMIC_HOVER_SETTLE", "20", "tasks.py:8299", "post-hover fixed hold [ticks]"),
    ("FRUIT_PREPOSE_TICKS", "45", "tasks.py:8179", "pre-pose joint blend length [ticks]"),
    ("FRUIT_DYNAMIC_CLOSE_FAST", "24", "tasks.py:9692", "close ramp before contact [ticks]"),
    ("FRUIT_DYNAMIC_CLOSE_LOAD", "60", "tasks.py:9693", "close ramp after contact [ticks]"),
    ("FRUIT_DYNAMIC_HOLD", "48", "tasks.py:10537", "post-close hold [ticks]"),
    ("FRUIT_DYNAMIC_PROBE_TICKS", "40/60*", "tasks.py:8861", "test-lift probe length [ticks]"),
    ("FRUIT_RELEASE_DWELL", "20", "tasks.py:11799", "release dwell [ticks]"),
    ("FRUIT_RELEASE_PAD_HOLD", "3", "tasks.py:11805", "ticks per pad-ramp step (40 steps)"),
    ("FRUIT_RELEASE_FINGER_HOLD", "3", "tasks.py:11818", "ticks per finger-ramp step (16 steps)"),
    ("FRUIT_HAND_VMAX", "0.0", "kinematic_gripper.py:219", "pad speed cap (0 = off; capping measured worse)"),
    ("FRUIT_CARRY_HOLD_QUAT", "0", "tasks.py:3344", "hold the wrist attitude through the carry"),
    ("FRUIT_WRIST_VMAX", "0.15", "actuated_gripper.py:263", "actuated-hand wrist only (not the shipped jaw)"),
]


# --------------------------------------------------------------------------- #
# the profile model
# --------------------------------------------------------------------------- #
def leg_limits(leg: str, indexed: bool, two_line: bool = False) -> tuple[TrajectoryLimits, np.ndarray, str]:
    """(limits, direction, note) for one `[motion] carry` leg.

    Mirrors `tasks.py::_grasp_carry_place_impl` (3366-3430): the per-leg caps are
    applied first, then `limited_by_cone` (which also rewrites j_max and v_max).
    """
    limits = TrajectoryLimits.from_env(CONTROL_DT)
    direction = np.array([0.0, 0.0, 1.0])
    note = "carry"
    if leg == "grasp_lift":
        limits.v_max = float(os.environ.get("FRUIT_LIFT_VMAX", "0.18")) if indexed else 0.30
        limits.a_max = 1.0
        note = "lift"
    elif leg.startswith("place"):
        direction = np.array([1.0, 0.0, 0.3])
        if not indexed:
            limits.v_max = min(limits.v_max, 0.35)
            limits.a_max = min(limits.a_max, 1.089)
        note = "place"
    return limits.limited_by_cone(direction, MU_EFF), direction, note


def binding(distance: float, limits: TrajectoryLimits) -> tuple[str, float, float, float]:
    """(which term binds, T_v, T_a, T_j) for a one-directional jerk-limited move."""
    v = max(limits.v_max, 1e-3)
    a = max(limits.a_max, 1e-3)
    j = max(limits.j_max, 1e-3)
    t_v = 1.875 * distance / v
    t_a = math.sqrt(5.774 * distance / a)
    t_j = (60.0 * distance / j) ** (1.0 / 3.0)
    wins = {"v_max": t_v, "a_max": t_a, "j_max": t_j}
    return max(wins, key=wins.get), t_v, t_a, t_j


def ticks_for(distance: float, limits: TrajectoryLimits) -> int:
    positions, _, _ = jerk_limited(max(distance, 1e-3), limits)
    return len(positions)


def read(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def mean(values, default=0.0):
    values = list(values)
    return stats.mean(values) if values else default


# --------------------------------------------------------------------------- #
# B. the legs
# --------------------------------------------------------------------------- #
def section_b(logs: list[str], indexed: set[str]) -> dict:
    print()
    print("=" * 96)
    print("B. THE LEG IS THE CAP, NOT THE SERVO - measured ticks vs the modelled profile")
    print("=" * 96)
    print("`ticks` is how many times the leg steps the sim, and the leg steps once per")
    print("profile sample: the modelled length IS the leg. A match means the cap sets the")
    print("duration and the servo only has to keep up inside it.\n")
    rows: dict[tuple[str, str], list[dict]] = {}
    approaches: dict[tuple[str, str], list[dict]] = {}
    for path in logs:
        tag = os.path.basename(path)
        is_indexed = path in indexed
        for line in read(path).splitlines():
            carry = parse_carry(line)
            if carry:
                leg = carry["leg"]
                distance = carry["d"]
                limits, _direction, _note = leg_limits(leg, is_indexed)
                which, _tv, _ta, _tj = binding(distance, limits)
                model = ticks_for(distance, limits)
                rows.setdefault((leg, tag), []).append(
                    {
                        "d": distance,
                        "ticks": carry["ticks"],
                        "model": float(model),
                        "binds": which,
                        "ref": 1.875 * distance / (model * CONTROL_DT),
                        "cap": limits.v_max,
                        "ach": carry["vact"],
                        "aact": carry["aact"],
                        "vcmd": carry["vcmd"],
                        "ref_v": 1.875 * distance / (model * CONTROL_DT),
                        "cone": carry["cone"],
                        "win": carry["win"] / max(carry["acmd"], 1e-9),
                    }
                )
            match = APPROACH.search(line)
            if match:
                distance = float(match.group("d")) / 100.0
                limits = TrajectoryLimits.from_env(CONTROL_DT)
                limits.v_max = 0.03 if is_indexed else float(
                    os.environ.get("FRUIT_DYNAMIC_APPROACH_VMAX", "0.15"))
                limits.a_max = 0.8
                which, _tv, _ta, _tj = binding(distance, limits)
                model = ticks_for(distance, limits)
                approaches.setdefault(("approach", tag), []).append(
                    {
                        "d": distance,
                        "ticks": float(match.group("ticks")),
                        "model": float(model),
                        "binds": which,
                        "ref": 1.875 * distance / (model * CONTROL_DT),
                        "cap": limits.v_max,
                        "ach": float(match.group("vact")),
                        "aact": float(match.group("aact")),
                        "end": float(match.group("end") or 0.0),
                        "vend": float(match.group("v1")),
                    }
                )
    print(f"{'log / leg':46s} {'n':>3s} {'d[cm]':>6s} {'ticks':>6s} {'model':>6s} "
          f"{'d%':>6s} {'binds':>6s} {'ref/cap':>7s} {'cone':>5s} {'awin/cmd':>8s}")
    for (leg, tag), items in sorted(rows.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        d = mean(i["d"] for i in items) * 100
        t = mean(i["ticks"] for i in items)
        m = mean(i["model"] for i in items)
        which = Counter(i["binds"] for i in items).most_common(1)[0][0]
        print(f"{tag[:28] + ' / ' + leg:46s} {len(items):3d} {d:6.1f} {t:6.1f} {m:6.1f} "
              f"{(t - m) / max(m, 1) * 100:+5.1f}% {which:>6s} "
              f"{mean(i['ref'] for i in items) / max(mean(i['cap'] for i in items), 1e-9):7.2f} "
              f"{mean(i['cone'] for i in items):5.2f} {mean(i['win'] for i in items):8.2f}")
    print(f"\n{'log / leg':46s} {'n':>3s} {'d[cm]':>6s} {'ticks':>6s} {'model':>6s} "
          f"{'d%':>6s} {'binds':>6s} {'ref/cap':>7s} {'ach/ref':>7s} {'end[mm]':>7s} {'v_end':>6s}")
    for (leg, tag), items in sorted(approaches.items(), key=lambda kv: kv[0][1]):
        d = mean(i["d"] for i in items) * 100
        t = mean(i["ticks"] for i in items)
        m = mean(i["model"] for i in items)
        which = Counter(i["binds"] for i in items).most_common(1)[0][0]
        print(f"{tag[:28] + ' / ' + leg:46s} {len(items):3d} {d:6.1f} {t:6.1f} {m:6.1f} "
              f"{(t - m) / max(m, 1) * 100:+5.1f}% {which:>6s} "
              f"{mean(i['ref'] for i in items) / max(mean(i['cap'] for i in items), 1e-9):7.2f} "
              f"{mean(i['ach'] for i in items) / max(mean(i['ref'] for i in items), 1e-9):7.2f} "
              f"{mean(i['end'] for i in items):7.1f} {mean(i['vend'] for i in items):6.3f}")
    print("\n`ref/cap` = the profile's own peak speed / the cap it was given (1.00 = the cap")
    print("sets the leg's length). `cone` is the measured acceleration in cone budgets and")
    print("`awin/cmd` the 5-tick smoothed acceleration as a multiple of the commanded peak")
    print("(>1 is the servo's following-error transient, the W8-B/AGENTS carry report - a")
    print("carry leg's own |v|max is the hand, so it is not used as a payload speed here).")
    return rows, approaches


# --------------------------------------------------------------------------- #
# C. the cycle
# --------------------------------------------------------------------------- #
ORDER = ["prepose", "hover", "descent", "close", "grip", "lift",
         "place", "release", "return", "end"]


def cycles(path: str) -> list[dict[str, float]]:
    out = []
    for line in read(path).splitlines():
        match = CYCLE.search(line)
        if match:
            out.append({k: float(v) for k, v in PHASE.findall(match.group("body"))})
    return out


def section_c(logs: list[str]) -> None:
    print()
    print("=" * 96)
    print("C. THE `[cycle]` PHASES  (s per attempt; only logs run with FRUIT_CYCLE_REPORT=1)")
    print("=" * 96)
    table = {}
    for path in logs:
        rows = cycles(path)
        if rows:
            table[os.path.basename(path)] = rows
    if not table:
        print("no `[cycle]` rows in the given logs")
        return
    head = "  ".join(f"{p[:8]:>8s}" for p in ORDER)
    print(f"{'log':30s} {'n':>3s}  {head}  {'total':>7s}")
    for tag, rows in table.items():
        total = mean(r.get("total", 0.0) for r in rows)
        cells = "  ".join(f"{mean(r[p] for r in rows if p in r):8.2f}" for p in ORDER)
        n = max(len([r for r in rows if p in r]) for p in ORDER)
        print(f"{tag[:30]:30s} {len(rows):3d}  {cells}  {total:7.2f}")
        print(f"{'':30s} {'':3s}  " + "  ".join(
            f"{mean(r[p] for r in rows if p in r) / total * 100:7.1f}%" if any(p in r for r in rows)
            else f"{'-':>8s}" for p in ORDER))
    ship = table.get("d0_accept_A_s5.log")
    if ship:
        total = mean(r.get("total", 0.0) for r in ship)
        print("\nThe shipped single-arm branch (`d0_accept_A_s5.log`; its 387 non-`[bed]`")
        print("`[fruit]` lines are byte-identical to `post_revert_accept_unset.log`, i.e. the")
        print("shipped tree's acceptance stream):")
        for p in ORDER:
            values = [r[p] for r in ship if p in r]
            if not values:
                continue
            print(f"  {p:9s} {mean(values):5.2f} s  {mean(values) / total * 100:5.1f} %  n={len(values)}")
        print(f"  {'TOTAL':9s} {total:5.2f} s")


# --------------------------------------------------------------------------- #
# D. the clocks
# --------------------------------------------------------------------------- #
CLOCKS = [
    ("pre-feed drive catch-up", 20, "tasks.py:1958 _catch_up_drive", "prepose"),
    ("pre-pose joint blend", 45, "tasks.py:8179 FRUIT_PREPOSE_TICKS", "prepose"),
    ("pre-pose settle", 20, "tasks.py:8245 app_utils.update_app(steps=20)", "prepose"),
    ("hover settle hold", 20, "tasks.py:8299 FRUIT_DYNAMIC_HOVER_SETTLE", "hover"),
    ("close fast ramp", 24, "tasks.py:9692 FRUIT_DYNAMIC_CLOSE_FAST", "close"),
    ("close load ramp", 60, "tasks.py:9693 FRUIT_DYNAMIC_CLOSE_LOAD", "close"),
    ("post-close hold", 48, "tasks.py:10537 FRUIT_DYNAMIC_HOLD", "close"),
    ("probe (test lift)", 60, "tasks.py:8861 FRUIT_DYNAMIC_PROBE_TICKS (two-line)", "grip"),
    ("release dwell", 20, "tasks.py:11799 FRUIT_RELEASE_DWELL", "release"),
    ("release pad ramp", 40 * 3, "tasks.py:11805 40 steps x FRUIT_RELEASE_PAD_HOLD 3", "release"),
    ("release finger ramp", 16 * 3, "tasks.py:11818 16 steps x FRUIT_RELEASE_FINGER_HOLD 3", "release"),
]


def section_d(phase_mean: dict[str, float]) -> None:
    print()
    print("=" * 96)
    print("D. THE FIXED TICK BUDGETS  (open-loop holds: not motion caps, but clocks)")
    print("=" * 96)
    print(f"{'block':24s} {'ticks':>6s} {'s':>6s}  phase     site")
    for name, ticks, site, phase in CLOCKS:
        print(f"{name:24s} {ticks:6d} {ticks * CONTROL_DT:6.2f}  {phase:9s} {site}")
    for phase in ("prepose", "hover", "close", "release", "grip"):
        total = sum(t for _n, t, _s, p in CLOCKS if p == phase)
        if phase not in phase_mean:
            continue
        share = total * CONTROL_DT / phase_mean[phase] * 100 if phase_mean[phase] else 0.0
        print(f"\n  `[cycle] {phase}` = {phase_mean[phase]:.2f} s; the clocks own "
              f"{total * CONTROL_DT:.2f} s ({share:.0f} %).")
    print("\nThe release's inner 1.57 s (RATE_LEDGER 4.5 called it unnamed) is these three")
    print("hold budgets: 20 + 120 + 48 = 188 ticks = 1.57 s of pure open-loop hold, with the")
    print("pads re-commanded at the same gap every PAD_HOLD-th tick.")


# --------------------------------------------------------------------------- #
# E. headroom
# --------------------------------------------------------------------------- #
def section_e(rows: dict, approaches: dict) -> None:
    print()
    print("=" * 96)
    print("E. HEADROOM - what each cap would buy, and what binds next")
    print("=" * 96)
    print("Leg geometry is the *measured* mean of the shipped two-arm corpus; `now` is the")
    print("shipped profile. Seconds saved against `now` are in brackets.\n")
    legs = []
    for leg, limits in (
        ("grasp_lift", leg_limits("grasp_lift", False)[0]),
        ("place0", leg_limits("place0", False)[0]),
        ("approach", _approach_limits(0.15)),
    ):
        source = approaches if leg == "approach" else rows
        d = [i["d"] for (lg, _t), items in source.items() if lg == leg for i in items]
        if d:
            legs.append((leg, mean(d), limits))
    rungs = ((1.25, 1.0), (1.5, 1.0), (2.0, 1.0), (1.0, 1.5), (1.0, 2.0), (2.0, 2.0))
    tags = ("v x1.25", "v x1.5", "v x2", "a x1.5", "a x2", "both x2")
    print(f"{'leg':14s} {'d[cm]':>6s} {'now':>10s} " + " ".join(f"{t:>11s}" for t in tags))
    for name, distance, limits in legs:
        base = ticks_for(distance, limits)
        cells = []
        for v_scale, a_scale in rungs:
            variant = TrajectoryLimits(
                v_max=limits.v_max * v_scale,
                a_max=limits.a_max * a_scale,
                j_max=limits.j_max * max(v_scale, a_scale),
                dt=CONTROL_DT,
            )
            ticks = ticks_for(distance, variant)
            cells.append(f"{ticks:4d}({(base - ticks) * CONTROL_DT:4.2f})")
        print(f"{name:14s} {distance * 100:6.1f} {base:4d}(0.00) " + " ".join(f"{c:>11s}" for c in cells))
    print("\nA column that stops moving is a cap that has stopped binding. The v-only")
    print("ceiling (where a_max takes over), per leg:")
    for name, distance, limits in legs:
        ceiling = 1.875 * distance / math.sqrt(5.774 * distance / limits.a_max)
        print(f"  {name:14s} a_max={limits.a_max:5.3f} -> v_max can rise to {ceiling:5.3f} m/s "
              f"({ceiling / limits.v_max:4.2f}x)")
    print(f"\nThe friction cone (mu_eff = {MU_SAFETY} x {GRIPPER_MU} = {MU_EFF}):")
    for direction, tag in (
        (np.array([0.0, 0.0, 1.0]), "lift, +z"),
        (np.array([1.0, 0.0, 0.3]), "place, horizontal+rise"),
        (np.array([0.0, 0.0, -1.0]), "descent / drop, -z"),
    ):
        unit = direction / np.linalg.norm(direction)
        print(f"  accel_budget({tag:24s}) = {accel_budget(unit, MU_EFF):6.3f} m/s^2 at mu_eff "
              f"{MU_EFF}   ({accel_budget(unit, 0.45):6.3f} at 0.45)")
    print("  cone_scale(vertical 9.81 m/s^2) =", f"{cone_scale(np.array([0.0, 0.0, 9.81]), MU_EFF):.3f}")
    print("  NOTE: at mu_eff 0.45 the +z budget is 0.000 by construction (N = m g, no squeeze),")
    print("  so that column is the model leaving its own validity - the physical worst-fruit")
    print("  margin is the measured 1.20x of P40 (4.42 N pinch), not a cone acceleration.")


def _approach_limits(v: float) -> TrajectoryLimits:
    limits = TrajectoryLimits.from_env(CONTROL_DT)
    limits.v_max = v
    limits.a_max = 0.8
    return limits


# --------------------------------------------------------------------------- #
# F. joint limits
# --------------------------------------------------------------------------- #
LEVERS = {"joint1": 0.500, "joint2": 0.440, "joint3": 0.300, "joint4": 0.154,
          "joint5": 0.0955, "joint6": 0.1205, "joint7": 0.0375}


def section_f(joints: list[tuple[int, Joint]], peak_tool: float, peak_a: float) -> None:
    print()
    print("=" * 96)
    print("F. DO THE JOINT VELOCITY / EFFORT LIMITS BIND?")
    print("=" * 96)
    deg = math.pi / 180.0
    print(f"The fastest reference the profile asks for is {peak_tool:.3f} m/s (an indexed")
    print(f"`place1` |v|cmd; the dynamic line's fastest is 0.343 m/s), under the 0.38 m/s")
    print(f"FRUIT_CARRY_VMAX cap. The descent's measured TCP acceleration")
    print(f"peak is {peak_a:.2f} m/s^2, and `need` below is the joint acceleration that asks for.")
    print("A joint's tool speed contribution = omega x lever (levers are the nominal")
    print("openarm link offsets, an order-of-magnitude check, not a kinematic solve).\n")
    print(f"{'joint':8s} {'vlim[deg/s]':>11s} {'vlim[rad/s]':>11s} {'lever[m]':>8s} "
          f"{'tool[m/s]':>9s} {'x cap':>6s} {'x peak':>6s} {'Fmax[Nm]':>8s} {'I[kgm2]':>8s} "
          f"{'F/I[rad/s2]':>11s} {'need':>6s}")
    worst_v, worst_a = 9e9, 9e9
    for line_no, joint in joints:
        if not joint.name.startswith("openarm_left_joint"):
            continue
        key = re.sub(r"openarm_left_", "", joint.name)
        wlim = (joint.max_vel or 0.0) * deg
        lever = LEVERS.get(key, 0.0)
        accel = (joint.max_force or 0.0) / (joint.inertia or 1.0)
        need = peak_a / lever if lever else 0.0
        ratio_v = wlim * lever / 0.38 if wlim else 0.0
        ratio_v2 = wlim * lever / max(peak_tool, 1e-9) if wlim else 0.0
        ratio_a = accel / need if need else 0.0
        worst_v = min(worst_v, ratio_v2)
        worst_a = min(worst_a, ratio_a)
        print(f"{key:8s} {joint.max_vel or 0:11.1f} {wlim:11.2f} {lever:8.3f} "
              f"{wlim * lever:9.2f} {ratio_v:6.1f} {ratio_v2:6.1f} {joint.max_force or 0:8.0f} "
              f"{joint.inertia or 0:8.4f} {accel:11.0f} {need:6.1f}")
    print(f"\nTightest velocity margin: {worst_v:.1f}x the fastest reference "
          f"({peak_tool:.3f} m/s) at that joint's lever.")
    print("joint4 / joint7 can carry 0.79-0.84 m/s at their levers against the 0.38 m/s")
    print("the profile can ever ask for, so no joint velocity limit is reachable.")
    print(f"Tightest effort margin: {worst_a:.1f}x the torque the descent's measured "
          f"{peak_a:.2f} m/s^2 would need at that lever (joint5, the thin wrist).")
    print("`need` = a_max / lever, the joint acceleration a Cartesian a_max asks for;")
    print("`F/I` is an upper bound (the torque is shared across the chain).")
    print("\nWhat the effort cap *does* do: the drive saturates at `sat.err` = 1.75 mrad")
    print("(j1/2), 1.18 mrad (j3/4) or 0.31 mrad (j5/6/7) of error, and the measured")
    print("8.1-10.4 mm tool lag at a ~0.3 m lever is ~30 mrad - 17-95x past saturation. So on")
    print("every real leg the arm drive is a *torque source*, not a stiffness, which is")
    print("why `sat.err` is not a speed number and why the gains are not a rate lever.")


# --------------------------------------------------------------------------- #
# G. following error and the two cap classes
# --------------------------------------------------------------------------- #
def section_g(logs: list[str], historic: list[str]) -> None:
    print()
    print("=" * 96)
    print("G. THE FOLLOWING ERROR, AND THE TWO CAP CLASSES (clock vs convergence)")
    print("=" * 96)
    print("A leg whose duration is a profile length is *clocked*: the ticks are fixed by")
    print("`jerk_limited`, so the drive's bandwidth can only change how *well* the leg")
    print("tracks, never how long it takes. `end=` is that tracking error:")
    print(f"\n{'log':34s} {'n':>3s} {'endmin':>7s} {'median':>7s} {'endmax':>7s} {'v_end':>7s} "
          f"{'v_end*tau':>10s}   [mm]")
    for path in logs + historic:
        ends, vends = [], []
        for line in read(path).splitlines():
            match = APPROACH.search(line)
            if match:
                ends.append(float(match.group("end") or 0.0))
                vends.append(float(match.group("v1")))
        if not ends:
            continue
        print(f"{os.path.basename(path)[:34]:34s} {len(ends):3d} {min(ends):7.1f} "
              f"{stats.median(ends):7.1f} {max(ends):7.1f} {mean(vends):7.3f} "
              f"{mean(vends) * 0.200 * 1000:9.1f}")
    print("\n`v_end*tau` is the first-order bound on the following error at the leg's end")
    print("with the asset's tau = 0.200 s. The historical corpus (logs/161, the indexed")
    print("descent commanded into the belt) reads 42-88 mm with v_end 0.002-0.013 m/s - that")
    print("gap is a *boundary stop*, not a lag, and logs/165 measured it unchanged under")
    print("FRUIT_TUNE_GAINS=1 (36-98 mm), which is why the gains are not a speed lever.")
    print("\nThe convergence-bound blocks (duration set by tau and the move's tolerance):")
    print("  hover 0.74-0.86 s = move_to(max_steps=300, tol 0.008 m) from ~6 cm above the")
    print("  pick point + the 20-tick settle; return 0.50-0.67 s = the same loop to `ready`.")
    print("  Both are *not* profile-clocked, so these are the only blocks a drive gain could")
    print("  shorten - and `FRUIT_HOVER_STEP` 0.04 rad/tick is not what bounds them: 0.04 rad")
    print("  at a 0.3 m lever is 12 mm/tick, i.e. the 6 cm hover is ~5 ticks of travel")
    print("  against the 82-103 measured. The binder is the 8 mm tolerance under tau.")
    print("\nThe finger drive's own following error at the close (P40, logs/p40/EFFORT_READ.md")
    print("`err` = drive_target - position): 3.95-7.57 mm (median 5.59) at k = 1e6 N/m, i.e.")
    print("the authored k*err is 4-8 kN and the 10 N/joint cap clips every row; at the P41")
    print("profile (k = 1e5) the same err is 40-76x the 0.1 mm saturation error. The finger")
    print("cap is therefore *not* the limiter - the delivered pinch is (9.8 N of 20).")


# --------------------------------------------------------------------------- #
# H. candidates
# --------------------------------------------------------------------------- #
def section_h() -> None:
    print()
    print("=" * 96)
    print("H. THE RANKED CANDIDATES (see CAP_CENSUS.md sections 5-7 for the measured risk)")
    print("=" * 96)
    for line in (
        "1. FRUIT_DYNAMIC_PLACE_VMAX 0.35 -> 0.52-0.61 (tasks.py:3424)",
        "   moves: place0/place1, 3.35 s of the single arm / 3.21 s of the two-line",
        "   gain: -1.09 s at 0.52, -1.38 s at the 0.61 a_max ceiling",
        "   risk: the place is loaded for its whole length; Gate-19 (0.20/0.25/0.30/0.35 ->",
        "   7/7/8/9 of 10) is monotone and is the only speed evidence; >0.35 unswept",
        "2. FRUIT_RELEASE_PAD_HOLD/FINGER_HOLD 3 -> 2 (tasks.py:11805/11818)",
        "   moves: release 2.04 s (single) / 2.30 s (two-line), 188 clocks = 1.57 s",
        "   gain: -0.33 s (pad) -0.13 s (finger) -0.17 s (dwell 20 -> 0) = -0.63 s",
        "   risk: the release-induced ejection the debug flag exists for; 3 -> 1 is -1.02 s",
        "3. FRUIT_DYNAMIC_LIFT_AMAX 1.0 -> 1.9 + VMAX 0.30 -> 0.36 (tasks.py:3402/3399)",
        "   moves: lift 1.82 s (164 ticks = 1.37 s of profile)",
        "   gain: -0.23 s (v alone, a then binds at 1.2x) / -0.56 s (both x2)",
        "   risk: the grip-critical leg; the vertical cone budget is 1.962 so a <= 1.9",
        "4. FRUIT_DYNAMIC_APPROACH_VMAX 0.15 -> 0.25 (tasks.py:5937/9352)",
        "   moves: 0.74 s of descent motion + the lead it sets (t_desc enters the handover)",
        "   gain: ~-0.2 s motion, ~-0.1 s wait; risk: reach boundary, ach/ref 0.75",
        "5. FRUIT_TUNE_GAINS=1 (k 1500 / c 60): NOT a rate lever (every leg is clocked);",
        "   it is the only lever on the two convergence loops and on the 8-11 mm end-gap,",
        "   and its measured effect there is untested (logs/165 tested the boundary gap).",
    ):
        print(line)
    print("\nCannot help: joint velocity limits, joint effort limits, the arm drive gains")
    print("(rate), FRUIT_IK_MAX_STEP/GAIN/RATE, FRUIT_HAND_VMAX, the cone on lift/place,")
    print("FRUIT_HOVER_STEP, the close/hold clocks (grip class), the belt speed, the supply.")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", action="append", default=None)
    parser.add_argument("--indexed-log", action="append", default=None,
                        help="a log recorded on the indexed/policy-handover caps")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    logs = [os.path.join(ROOT, p) for p in (args.log or DEFAULT_LOGS)]
    indexed = {os.path.join(ROOT, p) for p in (args.indexed_log or DEFAULT_INDEXED)}
    logs += sorted(indexed)
    logs = [p for p in dict.fromkeys(logs) if os.path.exists(p)]
    joints = parse_usd()
    handle = saved = out = None
    if args.write:
        out = os.path.join(ROOT, "logs", "p44", "CAP_CENSUS_out.txt")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        handle = open(out, "w", encoding="utf-8")
        saved, sys.stdout = sys.stdout, handle
    try:
        print(f"tree: {ROOT}")
        print(f"logs: {[os.path.basename(p) for p in logs]}")
        section_a(joints)
        rows, approaches = section_b(logs, indexed)
        section_c(logs)
        ship = cycles(os.path.join(ROOT, "logs/p43/p2/d0_accept_A_s5.log")) or cycles(
            os.path.join(ROOT, "logs/p41/p2/twoline_profile.log"))
        phase_mean = {p: mean(r[p] for r in ship if p in r) for p in ORDER}
        section_d(phase_mean)
        section_e(rows, approaches)
        # the *reference* peak the profile asks for, and the TCP's measured peak on
        # the one leg whose measured |v|/|a| is the payload-free TCP (the descent)
        vpeak = max([i["vcmd"] for items in rows.values() for i in items]
                    + [i["ach"] for items in approaches.values() for i in items] or [0.0])
        apeak = max([i["aact"] for items in approaches.values() for i in items] or [0.0])
        section_f(joints, vpeak, apeak)
        section_g(logs, [os.path.join(ROOT, p) for p in HISTORIC_END])
        section_h()
    finally:
        if args.write:
            sys.stdout = saved
            handle.close()
            print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
