#!/usr/bin/env python3
"""P40 phase 1 - the grip force chain, measured from existing logs (offline).

Three corpora, all read-only:

  * `[acq]` rows (`FRUIT_ACQ_DIAG=1`, `tasks.py:9838-9869`): the only rows that
    print both the **frozen commanded gap** (`freeze=D mm@Nt`) and the
    **measured world-pose jaw separation** at the end of the close
    (`span=90.0->X mm`). Their difference is the one honest
    achieved-vs-commanded gap in the record.
  * `force servo:` rows (`tasks.py:2380-2400`): the carry-phase force band, the
    servo's reference, its trips and its commanded/measured separation.
  * the per-attempt `force=` / `N=` field: `result.max_tactile_force`
    (`tasks.py:10046`, `tasks.py:10300`), printed by `scripts/20_pick_place.py:350`.

It also does the slip-margin arithmetic: mass from `fruits.py`, the carry
profile's acceleration from `motion.TrajectoryLimits`, and the friction-cone
budget from `motion.accel_budget`.

Usage:
    python3 logs/p40/grip_census.py
    python3 logs/p40/grip_census.py --log <file>      # one log, verbose
"""

from __future__ import annotations

import argparse
import glob
import math
import os
import re
import statistics as st
import sys

G = 9.81

# --------------------------------------------------------------------------- #
# The rows.
# --------------------------------------------------------------------------- #
ACQ_SPAN = re.compile(r"span=(?P<open>[\d.]+)->(?P<closed>[\d.]+)mm")
ACQ_FREEZE = re.compile(r"freeze=(?:(?P<depth>[\d.]+)mm@(?P<tick>\d+)t|(?P<none>none))")
ACQ_CONTACT = re.compile(r"contact=(?:@(?P<tick>\d+)t\([^)]*\)mm F=(?P<f>[\d.]+)N|(?P<none>NONE))")
ACQ_FMAX = re.compile(r"Fmax=(?P<f>[\d.]+)")
ACQ_ARM = re.compile(r"\[acq\] (?P<arm>\w+) idx=(?P<idx>\d+)")
ACQ_STAGES = re.compile(
    r"setup\[premove=(?P<pre>[\d.]+) axis=(?P<axis>[\d.]+) hover=(?P<hover>[\d.]+) "
    r"wait=(?P<wait>[\d.]+) catchup=(?P<catchup>[\d.]+)\]s"
)
CARRY_CONE = re.compile(
    r"\[motion\] carry (?P<leg>[a-z0-9_]+): (?P<cm>[\d.]+) cm, (?P<ticks>\d+) ticks.*?"
    r"cone=(?P<cone>[\d.]+)x budget \((?P<over>\d+) pct over\)"
)
CARRY_ROW = re.compile(
    r"\[carry\] (?P<arm>\w+) (?P<leg>[a-z0-9_]+): ticks=(?P<ticks>\d+)/\d+ "
    r"clean_slip_max=(?P<slip>[\d.]+)mm in-hand_vmax=(?P<vmax>[\d.]+) "
    r"onset_row=(?P<onset>\d+) force@onset=(?P<fonset>[\d.]+)N sep@onset=(?P<sep>[\d.]+)mm "
    r"contacts@onset=(?P<contacts>\d+) min_contacts=(?P<minc>\d+) force_min=(?P<fmin>[\d.]+)N "
    r"loss_row=(?P<loss>-?\d+) guard=(?P<guard>\d+)"
    r"(?: events=(?P<events>\d+) holds=(?P<holds>\d+) reseat=(?P<reseat>[\d.]+)mm "
    r"relief=(?P<relief>\d+) gap_start=(?P<gap_start>[\d.]+)mm)?"
)
SERVO = re.compile(
    r"force servo: (?P<arm>\w+): ref=(?P<ref>[\d.]+)N F\[(?P<lo>[\d.]+),(?P<hi>[\d.]+)\]N "
    r"gap=(?P<gap>[\d.]+)mm sep=(?P<sep>[\d.]+)mm closed=(?P<closed>[\d.]+)mm "
    r"opened=(?P<opened>[\d.]+)mm trips=(?P<trips>\d+)"
)
FREEZE = re.compile(
    r"dynamic close: sustained contact after (?P<ticks>\d+) ticks \(force=(?P<f>[\d.]+) N, "
    r"span=(?P<span>[\d.]+) mm\); freezing the closing command at (?P<depth>[\d.]+) mm"
)
RUN_FORCE = re.compile(
    r"grasped=(?P<g>\w+) placed=(?P<p>\w+) lift=[+-][\d.]+(?: m|) force=(?P<f>[\d.]+) N"
)
SUM_FORCE = re.compile(r"N=(?P<f>[\d.]+) sim=")

#: `fruits.py:953-955` / `:977` - the shipped mass model. `density * 4/3 pi r^3
#: * 0.82`, with the per-class shipped density from `meshes.FRUIT_SHAPES`.
MASS_DENSITY = {
    "apple": 850.0, "pear": 880.0, "orange": 900.0, "tomato": 780.0,
    "peach": 820.0, "kiwi": 900.0, "lychee": 850.0, "strawberry": 700.0,
}
#: `assets.py:439-456` - the shipped diameter band per class [m].
DIAMETER = {
    "strawberry": (0.030, 0.045), "lychee": (0.028, 0.038), "kiwi": (0.050, 0.068),
    "tomato": (0.050, 0.068), "apple": (0.062, 0.070), "orange": (0.060, 0.070),
    "peach": (0.058, 0.070), "pear": (0.058, 0.070),
}
SHAPE_FACTOR = 0.82


def mass_of(cls: str, diameter: float) -> float:
    return MASS_DENSITY[cls] * (4.0 / 3.0) * math.pi * (diameter / 2.0) ** 3 * SHAPE_FACTOR


def pct(values: list[float], q: float) -> float:
    values = sorted(values)
    if not values:
        return float("nan")
    k = (len(values) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return values[lo] if lo == hi else values[lo] + (values[hi] - values[lo]) * (k - lo)


def band(values: list[float]) -> str:
    if not values:
        return "-"
    return (f"min {min(values):.2f} / p25 {pct(values, .25):.2f} / med {st.median(values):.2f} / "
            f"p75 {pct(values, .75):.2f} / max {max(values):.2f}  (n={len(values)})")


# --------------------------------------------------------------------------- #
def read_rows(paths: list[str]) -> dict:
    out = {"acq": [], "servo": [], "freeze": [], "run_force": [], "outcome": [], "cone": [],
           "carry": []}
    for path in paths:
        try:
            handle = open(path, "r", encoding="utf-8", errors="replace")
        except OSError:
            continue
        with handle:
            for line in handle:
                if "[acq]" in line:
                    row = {"path": path}
                    for rx, keys in ((ACQ_ARM, ("arm", "idx")), (ACQ_STAGES, None)):
                        m = rx.search(line)
                        if m:
                            row.update({k: (float(v) if k not in ("arm",) else v)
                                        for k, v in m.groupdict().items() if v is not None})
                    m = ACQ_SPAN.search(line)
                    if m:
                        row["span_open"] = float(m.group("open"))
                        row["span_closed"] = float(m.group("closed"))
                    m = ACQ_FREEZE.search(line)
                    if m:
                        row["freeze_depth"] = float(m.group("depth")) if m.group("depth") else None
                        row["freeze_tick"] = int(m.group("tick")) if m.group("tick") else None
                    m = ACQ_CONTACT.search(line)
                    if m:
                        row["contact_force"] = float(m.group("f")) if m.group("f") else None
                    m = ACQ_FMAX.search(line)
                    if m:
                        row["fmax"] = float(m.group("f"))
                    out["acq"].append(row)
                    continue
                if "force servo" in line:
                    m = SERVO.search(line)
                    if m:
                        d = m.groupdict()
                        out["servo"].append(
                            {k: (float(v) if k != "arm" else v) for k, v in d.items()}
                        )
                    continue
                if "[carry]" in line:
                    m = CARRY_ROW.search(line)
                    if m:
                        out["carry"].append(
                            {k: (v if k in ("arm", "leg") else float(v))
                             for k, v in m.groupdict().items() if v is not None}
                        )
                    continue
                if "[motion] carry" in line:
                    m = CARRY_CONE.search(line)
                    if m:
                        out["cone"].append({k: (v if k == "leg" else float(v))
                                            for k, v in m.groupdict().items()})
                    continue
                if "dynamic close: sustained contact" in line:
                    m = FREEZE.search(line)
                    if m:
                        d = m.groupdict()
                        out["freeze"].append({k: float(v) for k, v in d.items()})
                    continue
                if "[run] attempt" in line or "[biarm] result" in line:
                    m = RUN_FORCE.search(line)
                    if m:
                        out["run_force"].append(float(m.group("f")))
                        out["outcome"].append(
                            {
                                "place": float(m.group("f")),
                                "g": m.group("g") == "True",
                                "p": m.group("p") == "True",
                                "path": path,
                            }
                        )
                        continue
                    m = SUM_FORCE.search(line)
                    if m:
                        out["run_force"].append(float(m.group("f")))
    return out


# --------------------------------------------------------------------------- #
def report_acq(rows: list[dict], label: str) -> list[str]:
    contact = [r for r in rows if r.get("freeze_depth") and r.get("span_closed")]
    if not contact:
        return [f"* `{label}`: no `[acq]` rows with a freeze"]
    off = [r["span_closed"] - r["freeze_depth"] for r in contact]
    out = [f"* `{label}`: **{len(rows)}** `[acq]` rows, **{len(contact)}** of them with a "
           f"frozen close (`freeze=Dmm@Nt`) and a measured span",
           f"  * measured span at the close end: {band([r['span_closed'] for r in contact])} mm",
           f"  * frozen commanded gap: {band([r['freeze_depth'] for r in contact])} mm",
           f"  * **achieved - commanded** (`span_closed - freeze_depth`): {band(off)} mm "
           f"({100.0 * sum(1 for v in off if v > 1.0) / len(off):.0f} % of rows are > 1 mm wide)",
           f"  * contact-detection force: {band([r['contact_force'] for r in contact if r.get('contact_force')])} N",
           f"  * close `Fmax`: {band([r['fmax'] for r in contact if r.get('fmax')])} N"]
    return out


def report_servo(rows: list[dict], label: str) -> list[str]:
    if not rows:
        return []
    lo = [r["lo"] for r in rows]
    hi = [r["hi"] for r in rows]
    ref = [r["ref"] for r in rows]
    off = [r["sep"] - r["gap"] for r in rows]
    trips = [r["trips"] for r in rows]
    out = [f"* `{label}`: **{len(rows)}** carry-phase `force servo` rows (one per grip)",
           f"  * carried force band low/high: F_min {band(lo)} N; F_max {band(hi)} N",
           f"  * servo reference `ref` (median of the grip's first 48 samples, capped at 4.0 N): "
           f"{band(ref)} N",
           f"  * `sep - gap` (the joint-model separation minus the command, what R6-B read "
           f"as 'interference'): {band(off)} mm",
           f"  * servo trips per grip: {band([float(t) for t in trips])} "
           f"({sum(1 for t in trips if t == 0)} of {len(trips)} grips never tripped)"]
    return out


def report_headline(rows: list[float], label: str) -> list[str]:
    if not rows:
        return []
    return [f"* `{label}`: **{len(rows)}** per-attempt `force=`/`N=` values: {band(rows)} N",
            f"  * at or below 5 N: {100.0 * sum(1 for f in rows if f <= 5.0) / len(rows):.0f} %; "
            f"> 10 N: {100.0 * sum(1 for f in rows if f > 10.0) / len(rows):.0f} %; "
            f"0 N (no contact): {100.0 * sum(1 for f in rows if f < 0.01) / len(rows):.0f} %"]


def report_cone(rows: list[dict], label: str) -> list[str]:
    """How much of the friction cone the *command* already uses.

    `cone=` is `MotionMonitor`'s `|a + g| / (mu_eff g)` (`motion.py:313-318`) with
    `mu_eff = FRUIT_MU_SAFETY * mu = 0.6 * 2.0 = 1.2` (`tasks.py:2878`). 1.0 means
    the leg's own commanded peak sits exactly at the model's cone; the same leg at
    a lower real `mu_eff` is over it by `1.2 / mu_eff`.
    """
    if not rows:
        return []
    by_leg: dict[str, list[float]] = {}
    for r in rows:
        by_leg.setdefault(r["leg"], []).append(r["cone"])
    out = [f"* `{label}`: friction-cone usage of the carry legs "
           f"(`|a+g| / (mu_eff g)`, model `mu_eff` = 1.2)", "",
           "| leg | n | median | max | legs over 1.0 | at `mu_eff` 0.45 the same leg is |",
           "| --- | --- | --- | --- | --- | --- |"]
    for leg in sorted(by_leg):
        vals = by_leg[leg]
        over = sum(1 for v in vals if v > 1.0)
        out.append(f"| {leg} | {len(vals)} | {st.median(vals):.2f} | {max(vals):.2f} | "
                   f"{over} | {st.median(vals) * 1.2 / 0.45:.1f}x the cone |")
    return out


def report_carry(rows: list[dict], label: str) -> list[str]:
    """The `[carry]` rows: does the force at the grip's onset predict retention?

    `clean_slip_max` is W8-B's frame-free payload slip; the W8-B split is
    clean <= 1.43 mm vs escapes >= 17.9 mm, so 2 mm is the separating line.
    """
    if not rows:
        return []
    lift = [r for r in rows if r["leg"] == "grasp_lift"]
    # W8-B's population: the legs that actually took a load. A leg whose grip
    # never held (force at onset 0, one contact or none) is the reach-cliff /
    # no-contact class, excluded from the slip split in `logs/w8/B_RESULTS.md`.
    slip = [r for r in lift if r["slip"] >= 2.0]
    touched = [r for r in slip if r["contacts"] >= 1]
    out = [f"* `{label}`: **{len(rows)}** `[carry]` rows, {len(lift)} of them `grasp_lift`",
           f"  * `clean_slip_max` on the lift leg, **all** lift legs: {band([r['slip'] for r in lift])} mm "
           f"- **the live row is not a retention verdict on the lift leg** (see the note below)",
           f"  * of the {len(lift)} lift legs, {len(touched)} crossed the 2 mm line *with contact* "
           f"(the W8-B escape population) and {sum(1 for r in slip if r['contacts'] == 0)} "
           f"crossed it with no contact at all (never-held class)",
           f"  * force at onset, escapes with contact: {band([r['fonset'] for r in touched])} N "
           f"(W8-B's `logs/w8/B_RESULTS.md` reads median 4.90 N on its 31)",
           f"  * **single-sided contact at onset**: "
           f"{sum(1 for r in touched if r['contacts'] == 1)}/{len(touched)} of them; two-sided "
           f"{sum(1 for r in touched if r['contacts'] >= 2)}/{len(touched)}",
           f"  * achieved - commanded at the leg start (`sep@onset - gap_start`): "
           f"{band([r['sep'] - r['gap_start'] for r in touched if 'gap_start' in r])} mm"]
    return out


def report_outcome(rows: list[dict], label: str) -> list[str]:
    """Is the reported grip force a *discriminator* between placed and failed?"""
    placed = [r["place"] for r in rows if r["p"]]
    cnp = [r["place"] for r in rows if not r["p"] and r["g"]]
    nog = [r["place"] for r in rows if not r["g"]]
    if not (placed or cnp or nog):
        return []
    out = [f"* `{label}`: grip force by outcome", "",
           "| outcome | n | median N | p25 | p75 |", "| --- | --- | --- | --- | --- |"]
    for name, vals in (("placed", placed), ("carried-not-placed", cnp),
                       ("no grasp (no contact)", nog)):
        if vals:
            out.append(f"| {name} | {len(vals)} | {st.median(vals):.2f} | {pct(vals, .25):.2f} | "
                       f"{pct(vals, .75):.2f} |")
    return out


# --------------------------------------------------------------------------- #
def slip_margin() -> list[str]:
    """The arithmetic: capacity `mu*N` vs what the carry actually demands."""
    out = ["", "## The slip-margin arithmetic", ""]
    n_meas = 4.4   # the measured carry force (this census)
    out += [
        "Required tangential force `|F_t| = m |a + g|`, with the mass from "
        "`fruits.py:977` (`rho * 4/3 pi r^3 * 0.82`) at each class's mid diameter:",
        "",
        "| class | d (mm) | m (g) | m g (N) | +1.0 m/s^2 (N) | +5.83 m/s^2 (N) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    rows = {}
    for cls, (lo, hi) in DIAMETER.items():
        d = 0.5 * (lo + hi)
        m = mass_of(cls, d)
        rows[cls] = (d, m)
        out.append(f"| {cls} | {d * 1000:.1f} | {m * 1000:.1f} | {m * G:.2f} | "
                   f"{m * (G + 1.0):.2f} | {m * (G + 5.83):.2f} |")
    heavy = max(rows, key=lambda k: rows[k][1])
    m_heavy, d_heavy = rows[heavy][1], rows[heavy][0]
    req_static = m_heavy * G
    req_acc = m_heavy * (G + 5.83)
    out += [
        "",
        f"The heaviest class is **{heavy}** at {m_heavy * 1000:.0f} g ({d_heavy * 1000:.0f} mm), so the "
        f"worst-case demand is **{m_heavy * G:.2f} N** static and "
        f"**{m_heavy * (G + 5.83):.2f} N** at the largest single-tick acceleration the carry legs "
        f"report (`|a|max` 5.83 m/s^2, `logs/p39/p3/accept_C.log`; the *commanded* profile caps are "
        f"`FRUIT_DYNAMIC_LIFT_AMAX`=1.0 and `FRUIT_DYNAMIC_PLACE_AMAX`=1.089, `tasks.py:2913/2939`)",
        "",
        f"Capacity at the measured `N = {n_meas:.1f} N` (`mu_eff * N`, `mu_eff` = the friction the "
        f"pad-fruit pair actually combines to):",
        "",
        f"| `mu_eff` | where it comes from | capacity (N) | margin vs {req_static:.2f} N | "
        f"margin vs {req_acc:.2f} N |",
        "| --- | --- | --- | --- | --- |",
    ]
    for mu, why in (
        (0.45, "`min` combine x the lowest fruit mu (`meshes.py` pear/apple 0.45)"),
        (1.05, "`min` combine x the highest fruit mu (kiwi 1.05)"),
        (1.20, "`FRUIT_MU_SAFETY` 0.6 x `FRUIT_FINGER_MU` 2.0 (the carry profile's own model)"),
        (1.49, "`average` combine, (2.0 + 0.97)/2"),
        (2.00, "`max` combine"),
    ):
        cap = mu * n_meas
        out.append(f"| {mu:.2f} | {why} | {cap:.2f} | {cap / req_static:.1f}x | {cap / req_acc:.1f}x |")
    out += [
        "",
        f"**Normal force for a target margin** (at the {req_acc:.2f} N transient demand):",
        "",
        "| `mu_eff` | N for 2x (N) | N for 5x (N) | inside the 10 N/joint cap? |",
        "| --- | --- | --- | --- |",
    ]
    for mu in (0.45, 1.05, 1.20, 1.49, 2.00):
        n2, n5 = 2 * req_acc / mu, 5 * req_acc / mu
        out.append(f"| {mu:.2f} | {n2:.1f} | {n5:.1f} | "
                   f"{'both' if n5 <= 10 else ('2x only' if n2 <= 10 else 'neither')} |")
    out += [
        "",
        f"The measured `N` is **4.4 N**, i.e. {4.4 / 10:.0%} of one joint's 10 N cap "
        f"(`drive:linear:physics:maxForce = 10`, "
        f"`assets/openarm_flat/openarm_flat_deinst.usda:3802`) - **the shipped pinch does not "
        f"reach the actuator's limit**: its force is set by where the close's freeze stops, "
        f"not by the drive cap (see GRIP_CENSUS.md section 2).",
    ]
    return out


# --------------------------------------------------------------------------- #
CORPORA = [
    ("the shipped acceptance (P39 C)", "logs/p39/p3/accept_C.log"),
    ("the pear battery (P39 C)", "logs/p39/p3/pear_C.log"),
    ("the two-line control (P39)", "logs/p39/p3/twoline_C.log"),
    ("the bed battery (P32 A0)", "logs/p32/A0_bed_twoline_1.log"),
    ("a current diagnostic acceptance", "logs/p8/55_accept_control_diag.log"),
]

ACQ_CORPORA = [
    ("the WS-4.2 N=5 A/B, A arms", sorted(glob.glob("logs/p18b/N5_fix/A_*.log"))),
    ("the WS-4.2 N=5 A/B, B arms", sorted(glob.glob("logs/p18b/N5_fix/B_*.log"))),
    ("the R7-A edge-band probes", sorted(glob.glob("logs/r7/A_*.log"))),
]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log")
    args = ap.parse_args(argv)
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if os.path.basename(os.getcwd()) != os.path.basename(root):
        os.chdir(root)

    print("# P40 grip census - the rows")
    for label, path in CORPORA:
        if not os.path.exists(path):
            print(f"\n* `{label}`: MISSING `{path}`")
            continue
        rows = read_rows([path])
        print(f"\n## {label}  (`{path}`)")
        for line in report_headline(rows["run_force"], "per-attempt force"):
            print(line)
        for line in report_servo(rows["servo"], "carry"):
            print(line)
        if rows["freeze"]:
            f = [r["f"] for r in rows["freeze"]]
            t = [r["ticks"] for r in rows["freeze"]]
            span = [r["span"] for r in rows["freeze"]]
            depth = [r["depth"] for r in rows["freeze"]]
            print(f"* close freeze: **{len(f)}** rows; force at the freeze {band(f)} N; "
                  f"{band(t)} ticks after the close start")
            print(f"  * `span` at the freeze {band(span)} mm, frozen command {band(depth)} mm, "
                  f"**span - command {band([a - b for a, b in zip(span, depth)])} mm**")
        for line in report_cone(rows["cone"], label):
            print(line)
        for line in report_carry(rows["carry"], label):
            print(line)
        for line in report_outcome(rows["outcome"], label):
            print(line)
        # achieved vs commanded jaw separation (acq)
        if not rows["acq"]:
            print("* no `[acq]` rows in this log (needs `FRUIT_ACQ_DIAG=1`)")

    print("\n## the achieved-vs-commanded jaw separation (`[acq]` corpus)")
    for label, paths in ACQ_CORPORA:
        rows = read_rows(paths)
        print(f"\n### {label}")
        for line in report_acq(rows["acq"], label):
            print(line)

    # the pooled per-attempt force over the whole log tree
    all_logs = sorted(glob.glob("logs/**/*.log", recursive=True))
    pooled = read_rows(all_logs)
    print("\n## pooled over every log in the tree")
    for line in report_headline(pooled["run_force"], "per-attempt force (all logs)"):
        print(line)
    for line in report_servo(pooled["servo"], "carry (all logs)"):
        print(line)
    print()
    for line in report_carry(pooled["carry"], "all logs"):
        print(line)
    print()
    for line in report_cone(pooled["cone"], "all logs"):
        print(line)
    print()
    for line in report_outcome(pooled["outcome"], "all logs"):
        print(line)

    print("\n".join(slip_margin()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
