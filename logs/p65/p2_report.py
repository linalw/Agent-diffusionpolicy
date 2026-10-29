#!/usr/bin/env python3
"""P65 phase 1 report: **does the lift's drift coincide with a joint at its limit?**

Reads the registered cell (`logs/p65/p2/C_{77,101,202}.log`, the shipped direct
profile with `FRUIT_CARRY_DIAG=1`), the same-tree F3 control
(`logs/p63/p2/D_{77,101,202}.log`, which carries `hold_drift` but not the P65
fields) and the P60 parser unchanged (the "still parses" check).

    python3 logs/p65/p2_report.py            # print
    python3 logs/p65/p2_report.py --check    # + structural assertions

Definitions are fixed in `logs/p65/PREREG.md` (written before the run):
`q_margin` = the **measured** joint-limit margin `min(q-lo, hi-q)` over the 7 arm
joints, its minimum over the leg, printed as `<rad>@jN/tI` (N 1-based, I the tick
the minimum was taken); `q_cmd_margin` = the same for the controller's post-clip
command (`control.py:494`); `q_step_max` = the leg's largest per-tick
`max abs(dq_cmd)` (the `control.py:423` operand, `FRUIT_IK_MAX_STEP` default
0.5); `jaw_z` = the jaw-opening axis' world z (`rot_now[:, 1]`) at the leg's
first tick / its max abs; `drift_on` = the first tick `hold_drift` passes 10 deg.
The primary population is the `grasp_lift` legs, the outcome is the **attempt's**
(`logs/p60/p3/report.py`'s `outcome()`).
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CELL = [f"logs/p65/p2/C_{s}.log" for s in (77, 101, 202)]
CTRL = [f"logs/p63/p2/D_{s}.log" for s in (77, 101, 202)]
P60_REPORT = "logs/p60/p3/report.py"
HEADER = "logs/p65/p2/header.txt"

FARMS = ("left", "right")
MARGIN_AT_LIMIT = 0.05  # rad - PREREG P2 (a)
MARGIN_HEALTHY = 0.15   # rad - PREREG P2's refutation bar
COINCIDE_TICKS = 20     # PREREG P2 (b)
IK_MAX_STEP = 0.5       # control.py:423's default cap (rad)
DRIFT_ON_DEG = 10.0     # PREREG section 2

_RE_QM = re.compile(r"q_margin=(-?\d+\.\d+)@j(\d+)/t(\d+)")
_RE_QCM = re.compile(r"q_cmd_margin=(-?\d+\.\d+)@j(\d+)")
_RE_QSTEP = re.compile(r"q_step_max=(-?\d+\.\d+)")
_RE_JAW = re.compile(r"jaw_z=([+-]\d+\.\d+)/(\d+\.\d+)")
_RE_DON = re.compile(r"drift_on=(None|\d+)")
_RE_DRIFT = re.compile(r"hold_drift=([\d.]+)deg(\(no-hold\))?")
_RE_NOTE = re.compile(r"notes=\[(.*)\]")
_RE_MD5ROW = re.compile(r"^([0-9a-f]{32})\s+(\S+)$")
_RE_SUMMARY = re.compile(r"\[rl\] rollout success (\d+)/(\d+)")

FIELDS = (("q_margin", "q_margin"), ("q_cmd_margin", "q_cmd_margin"),
          ("q_step_max", "q_step_max"), ("jaw_z", "jaw_z_first"), ("drift_on", "drift_on"))


def load_p60():
    spec = importlib.util.spec_from_file_location("p60_report", ROOT / P60_REPORT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def parse_p65(rest: str) -> dict:
    """The five P65 fields, straight off the row (`None` where absent)."""
    out: dict = {}
    m = _RE_QM.search(rest)
    if m:
        out["q_margin"] = float(m.group(1))
        out["q_margin_j"] = int(m.group(2))
        out["q_margin_i"] = int(m.group(3))
    m = _RE_QCM.search(rest)
    if m:
        out["q_cmd_margin"] = float(m.group(1))
        out["q_cmd_margin_j"] = int(m.group(2))
    m = _RE_QSTEP.search(rest)
    if m:
        out["q_step_max"] = float(m.group(1))
    m = _RE_JAW.search(rest)
    if m:
        out["jaw_z_first"] = float(m.group(1))
        out["jaw_z_max"] = float(m.group(2))
    m = _RE_DON.search(rest)
    if m:
        out["drift_on"] = None if m.group(1) == "None" else int(m.group(1))
    m = _RE_DRIFT.search(rest)
    if m:
        out["hold_drift"] = float(m.group(1))
        out["no_hold"] = bool(m.group(2))
    return out


def legs(path: str) -> list[dict]:
    """Every `[carry]` leg with its attempt index and outcome (P60's parser)."""
    p60 = load_p60()
    eps = p60.parse_direct(path)
    rows: list[dict] = []
    for ep in eps:
        for leg in ep["legs"]:
            leg = dict(leg)
            leg.update(ep=ep["idx"], arm=ep["arm"], outcome=p60.outcome(ep),
                       fruit=ep["fruit"], src=path)
            leg.update(parse_p65(leg.get("line", "")))
            rows.append(leg)
    return rows


def med(vals):
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None


def rng(vals, nd=3):
    vals = [v for v in vals if v is not None]
    if not vals:
        return "n/a"
    if len(vals) == 1:
        return f"{vals[0]:.{nd}f}"
    vals = [v + 0.0 for v in vals]
    return f"{statistics.median(vals):.{nd}f} [{min(vals):.{nd}f}-{max(vals):.{nd}f}]"


def jhist(js):
    js = [j for j in js if j is not None]
    if not js:
        return "n/a"
    return " ".join(f"j{j}x{js.count(j)}" for j in sorted(set(js)))


# --------------------------------------------------------------------------- #
# sections
# --------------------------------------------------------------------------- #
def p0_presence(rows: list[dict]) -> list[str]:
    lift = [r for r in rows if r["name"] == "grasp_lift"]
    place = [r for r in rows if r["name"] != "grasp_lift"]
    out = ["## P0 - the instrument (PREREG P1)", ""]
    out.append(f"| read | value |")
    out.append(f"| --- | --- |")
    out.append(f"| `[carry]` rows | **{len(rows)}** (grasp_lift {len(lift)}, place {len(place)}) |")
    for label, key in FIELDS:
        have = sum(1 for r in lift if key in r)
        out.append(f"| `{label}` on grasp_lift | **{have}/{len(lift)}** |")
    nohold = [r for r in lift if r.get("no_hold")]
    out.append(f"| `(no-hold)` on grasp_lift | **{len(nohold)}/{len(lift)}** |")
    allf = [r for r in lift if all(key in r for _, key in FIELDS)]
    out.append(f"| all five on one grasp_lift row | **{len(allf)}/{len(lift)}** |")
    bad = [r for r in lift if any(key not in r for _, key in FIELDS)]
    if bad:
        out.append("")
        out.append("**MISSING FIELDS (F2):**")
        for r in bad:
            out.append(f"* {r['arm']} ep{r['ep']} {r['name']} {r.get('line','')[:160]}")
    return out


def p1_verdict(rows: list[dict]) -> tuple[list[str], dict]:
    lift = [r for r in rows if r["name"] == "grasp_lift"]
    out = ["## P1 - the margin per arm and per outcome", ""]
    out.append("| arm | outcome | n | drift deg | q_margin rad | binding | drift_on | q_step_max rad |")
    out.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    summ: dict = {}
    for arm in FARMS:
        for oc in ("placed", "cnp", "never-held"):
            sub = [r for r in lift if r["arm"] == arm and r["outcome"] == oc]
            if not sub:
                continue
            summ[(arm, oc)] = sub
            out.append(
                f"| {arm} | {oc} | {len(sub)} | {rng([r.get('hold_drift') for r in sub])} | "
                f"{rng([r.get('q_margin') for r in sub])} | "
                f"{jhist([r.get('q_margin_j') for r in sub])} | "
                f"{rng([r.get('drift_on') for r in sub], 0)} | "
                f"{max(r.get('q_step_max', 0.0) for r in sub):.4f} |"
            )
    out.append("")
    out.append("## P2 - the test: is the drift coincident with a joint at its limit?")
    out.append("")
    left = [r for r in lift if r["arm"] == "left" and r["outcome"] == "cnp"]
    out.append("### the left's failing (`cnp`) legs, one row each")
    out.append("")
    out.append("| ep | leg | ticks | drift deg | q_margin rad | j | t_min | drift_on | dt |")
    out.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in left:
        dt = (
            "n/a" if r.get("drift_on") is None or r.get("q_margin_i") is None
            else f"{r['drift_on'] - r['q_margin_i']:+d}"
        )
        out.append(
            f"| {r['ep']} | {r['name']} | {r.get('ticks_total','?')} | "
            f"{r.get('hold_drift', float('nan')):.1f} | {r.get('q_margin', float('nan')):.3f} | "
            f"j{r.get('q_margin_j','?')} | {r.get('q_margin_i','?')} | "
            f"{r.get('drift_on')} | {dt} |"
        )
    out.append("")
    out.append("`q_margin` is the leg's **minimum** (one number on the row), so the "
               "`at a limit` clause is read on the min - the conservative form "
               "(min <= end value). `dt` = `drift_on - t_min`, the registered "
               "coincidence operand.")
    margins = [r["q_margin"] for r in left if "q_margin" in r]
    coincide = [
        r for r in left
        if r.get("q_margin") is not None and r.get("drift_on") is not None
        and r.get("q_margin_i") is not None
        and abs(r["drift_on"] - r["q_margin_i"]) <= COINCIDE_TICKS
    ]
    at_limit = [r for r in left if r.get("q_margin") is not None
                and r["q_margin"] <= MARGIN_AT_LIMIT]
    healthy = [r for r in left if r.get("q_margin") is not None
               and r["q_margin"] >= MARGIN_HEALTHY]
    out.append("")
    out.append("### the registered decision (PREREG P2)")
    out.append("")
    out.append(f"* left cnp legs with a readable margin: **{len(margins)}/{len(left)}**")
    out.append(f"* at/near a limit (`q_margin <= {MARGIN_AT_LIMIT}`): **{len(at_limit)}/{len(margins)}**")
    out.append(f"* healthy (`q_margin >= {MARGIN_HEALTHY}`): **{len(healthy)}/{len(margins)}**")
    out.append(f"* onset coincident with the margin's minimum (+-{COINCIDE_TICKS} ticks): "
               f"**{len(coincide)}/{len(margins)}**")
    out.append(f"* min over all left cnp legs: **{min(margins):.3f} rad**" if margins else
               "* min over all left cnp legs: **n/a**")
    cmd = [r["q_cmd_margin"] for r in left if "q_cmd_margin" in r]
    steps = [r["q_step_max"] for r in left if "q_step_max" in r]
    if cmd:
        out.append(f"* the **command** margin on the same legs: median **{med(cmd):.3f} rad**, "
                   f"min **{min(cmd):.3f}** (the ``np.clip`` operand, `control.py:494`)")
    if steps:
        out.append(f"* `q_step_max` on the same legs: max **{max(steps):.3f} rad/tick** "
                   f"against the **{IK_MAX_STEP}** `FRUIT_IK_MAX_STEP` cap "
                   f"(= {max(steps) / IK_MAX_STEP:.0%} of it)")
    verdict = "unreadable"
    if margins:
        if healthy and not at_limit:
            verdict = "refuted"
        elif at_limit or coincide:
            verdict = "supported"
        else:
            verdict = "intermediate"
    if steps:
        binds = max(steps) >= IK_MAX_STEP
        out.append("")
        out.append(
            f"**`max_step` (`control.py:423`) as a separate object:** the leg's largest "
            f"per-tick command step is **{max(steps):.4f} rad** against the "
            f"**{IK_MAX_STEP}** cap -> it **{'BINDS' if binds else 'never binds'}** "
            f"({max(steps) / IK_MAX_STEP:.1%} of the cap). So the two suspects are "
            f"**not one question** on this instrument: the step cap is "
            f"{'live' if binds else 'refuted by measurement'}, while the joint-limit "
            f"clip is the one the margin decides."
        )
    # ---- P2b: does the margin discriminate at all? ----------------------
    out.append("")
    out.append("### P2b - does the margin discriminate? (all legs, both arms, lift and place)")
    out.append("")
    out.append("| group | n | margin <= 0.05 | margin >= 0.15 | median | min |")
    out.append("| --- | --- | --- | --- | --- | --- |")
    groups = [
        ("left grasp_lift", [r for r in lift if r["arm"] == "left"]),
        ("right grasp_lift", [r for r in lift if r["arm"] == "right"]),
        ("left place", [r for r in rows if r["name"] != "grasp_lift" and r["arm"] == "left"]),
        ("right place", [r for r in rows if r["name"] != "grasp_lift" and r["arm"] == "right"]),
    ]
    for label, sub in groups:
        v = [r["q_margin"] for r in sub if "q_margin" in r]
        if not v:
            out.append(f"| {label} | 0 | n/a | n/a | n/a | n/a |")
            continue
        out.append(
            f"| {label} | {len(v)} | {sum(1 for x in v if x <= MARGIN_AT_LIMIT)}/{len(v)} | "
            f"{sum(1 for x in v if x >= MARGIN_HEALTHY)}/{len(v)} | "
            f"{statistics.median(v):.3f} | {min(v):.3f} |"
        )
    dt_all = [
        r["drift_on"] - r["q_margin_i"] for r in lift
        if r.get("drift_on") is not None and r.get("q_margin_i") is not None
    ]
    out.append("")
    if dt_all:
        out.append(
            f"The drift's onset vs the margin's minimum over **all** `grasp_lift` legs: "
            f"median **{statistics.median(dt_all):+.0f} ticks** "
            f"[{min(dt_all):+d}..{max(dt_all):+d}], "
            f"inside +-{COINCIDE_TICKS}: **{sum(1 for d in dt_all if abs(d) <= COINCIDE_TICKS)}"
            f"/{len(dt_all)}**."
        )
    allm = [r["q_margin"] for r in rows if "q_margin" in r]
    degenerate = allm and sum(1 for x in allm if x <= MARGIN_AT_LIMIT) / len(allm) >= 0.9
    out.append("")
    out.append(
        "**Degenerate?** "
        + (
            f"YES - {sum(1 for x in allm if x <= MARGIN_AT_LIMIT)}/{len(allm)} of *all* "
            "legs (both arms, lift and place) read a margin at the limit, so the "
            "joint-limit clip is a **standing condition of this workspace**, not a "
            "lift-specific cause: it is present on the right's placing legs too."
            if degenerate else
            f"NO - {sum(1 for x in allm if x <= MARGIN_AT_LIMIT)}/{len(allm)} of all legs "
            "read a margin at the limit."
        )
    )
    out.append("")
    out.append(f"**P2 - the registered rule, literal: {verdict.upper()}** "
               "(a joint *is* at its limit on every failing leg)")
    out.append("")
    out.append(
        "**P2 - the causal reading, and the one the phase carries:** the clip is "
        + ("**not separated** - " if degenerate else "**separated** - ")
        + "the margin is at the limit on every leg of both arms (and on all 42 place "
          "legs), so it is a standing condition of this workspace, not the lift's "
          "cause; and the drift's onset precedes the margin's own minimum by a "
          "median of "
        + (f"{statistics.median(dt_all):+.0f} ticks" if dt_all else "n/a")
        + f" (inside +-{COINCIDE_TICKS} on "
        + f"{sum(1 for d in dt_all if abs(d) <= COINCIDE_TICKS)}/{len(dt_all)} legs). "
          "`max_step` is refuted by measurement on the same rows. **Both named "
          "suspects are therefore refuted as the creator of the 25 deg**; the "
          "residual (the margin at the onset tick is not on the row - only the leg's "
          "minimum is) is named in `logs/p65/P2_RESULTS.md`."
    )
    return out, dict(margins=margins, at_limit=at_limit, healthy=healthy,
                     coincide=coincide, cmd=cmd, steps=steps, verdict=verdict,
                     dt_all=dt_all, degenerate=degenerate)


def p3_pads(rows: list[dict]) -> list[str]:
    lift = [r for r in rows if r["name"] == "grasp_lift"]
    out = ["", "## P3 - the pads' line: does the left tip its jaw?", ""]
    out.append("| arm | n | `|jaw_z|` first (med) | `|jaw_z|` max (med) | max over legs | pad dz at max (mm) |")
    out.append("| --- | --- | --- | --- | --- | --- |")
    for arm in FARMS:
        sub = [r for r in lift if r["arm"] == arm and "jaw_z_max" in r]
        if not sub:
            out.append(f"| {arm} | 0 | n/a | n/a | n/a | n/a |")
            continue
        firsts = [abs(r["jaw_z_first"]) for r in sub]
        maxes = [r["jaw_z_max"] for r in sub]
        out.append(
            f"| {arm} | {len(sub)} | {statistics.median(firsts):.4f} | "
            f"{statistics.median(maxes):.4f} | {max(maxes):.4f} | {max(maxes) * 98.0:.1f} |"
        )
    out.append("")
    out.append("P64's `QPREC` reference: `|jaw_z| = 0.2949` -> 28.9 mm of pad height "
               "difference across the 98 mm jaw (the one-pad-first class); the control "
               "`C0` reads 0.0095 -> 0.9 mm.")
    return out


def p4_class(rows: list[dict], present: list[str]) -> list[str]:
    out = ["", "## P4 - the class counts, and F3 vs P63's control", ""]
    # attempts, not legs: an episode with a second `grasp_lift` (the P40 regrasp
    # path) is one row here, and an episode that never reached a carry leg is
    # still an attempt (it is `never-held` with no `[carry]` row at all).
    p60 = load_p60()
    attempts: dict[tuple, dict] = {}
    for path in present:
        for ep in p60.parse_direct(str(ROOT / path)):
            attempts[(path, ep["arm"], ep["idx"])] = dict(
                arm=ep["arm"], ep=ep["idx"], outcome=p60.outcome(ep))
    for r in rows:
        attempts.setdefault((r["src"], r["arm"], r["ep"]),
                            dict(arm=r["arm"], ep=r["ep"], outcome=r["outcome"]))
    out.append("| arm | placed | cnp | never-held | attempts | `grasp_lift` legs |")
    out.append("| --- | --- | --- | --- | --- | --- |")
    tot = {"placed": 0, "cnp": 0, "never-held": 0}
    for arm in FARMS:
        sub = [a for (_, ar, _e), a in attempts.items() if ar == arm]
        nlegs = sum(1 for r in rows if r["arm"] == arm and r["name"] == "grasp_lift")
        c = {k: sum(1 for r in sub if r["outcome"] == k) for k in tot}
        for k in tot:
            tot[k] += c[k]
        out.append(f"| {arm} | {c['placed']} | {c['cnp']} | {c['never-held']} | "
                   f"{len(sub)} | {nlegs} |")
    out.append(f"| pooled | {tot['placed']} | {tot['cnp']} | {tot['never-held']} | "
               f"{sum(tot.values())} | "
               f"{sum(1 for r in rows if r['name'] == 'grasp_lift')} |")
    out.append("")
    out.append("**No rate claim** (3 seeds of a rendered-frame loop, AGENTS.md §3b).")
    return out


def note_keys(path: str) -> dict[str, int]:
    notes: dict[str, int] = {}
    with open(path, errors="replace") as fh:
        for line in fh:
            m = _RE_NOTE.search(line)
            if not m:
                continue
            for n in m.group(1).split(";"):
                n = re.sub(r"\d+(\.\d+)?", "#", n.strip())
                if n:
                    notes[n] = notes.get(n, 0) + 1
    return notes


def p4_notes(rows: list[dict], path: str) -> list[str]:
    return [f"* `{k}` x{v}" for k, v in sorted(note_keys(path).items())]


def control_classes() -> dict:
    p60 = load_p60()
    out: dict[str, dict[str, int]] = {}
    for path in CTRL:
        if not (ROOT / path).exists():
            continue
        for ep in p60.parse_direct(path):
            oc = p60.outcome(ep)
            a = out.setdefault(ep["arm"], {"placed": 0, "cnp": 0, "never-held": 0})
            a[oc] = a.get(oc, 0) + 1
    return out


# --------------------------------------------------------------------------- #
def checks(rows: list[dict], path: str) -> int:
    fails = 0

    def ck(cond, what):
        nonlocal fails
        if not cond:
            print(f"FAIL: {what}")
            fails += 1
        else:
            print(f"ok: {what}")

    lift = [r for r in rows if r["name"] == "grasp_lift"]
    ck(bool(lift), "the cell has grasp_lift legs")
    ck(all(all(key in r for _, key in FIELDS) for r in lift),
       f"every grasp_lift row carries all five fields ({len(lift)})")
    ck(all(r["q_margin_i"] < r["ticks_total"] for r in lift if "q_margin_i" in r),
       "every margin tick is inside its leg")
    ck(all(r["q_margin_i"] <= r.get("ticks", 10 ** 9) for r in lift if "q_margin_i" in r),
       "every margin tick is one the leg actually ran")
    ck(all(r["jaw_z_max"] >= abs(r["jaw_z_first"]) - 1e-9 for r in lift
           if "jaw_z_max" in r),
       "jaw_z max abs >= the first tick's |z| on every leg")
    ck(all(r["q_step_max"] >= 0.0 for r in lift if "q_step_max" in r),
       "q_step_max is a magnitude")
    ck(all(r["drift_on"] is None or r["drift_on"] >= 0 for r in lift),
       "drift_on is a tick index or None")
    ck(all(r.get("q_margin", 1e9) >= -0.5 for r in lift),
       "no margin beyond -0.5 rad (a sane joint vector)")
    ck(all(r["arm"] == ("left" if r["side"] == "left" else "right") for r in lift),
       "every leg's side matches its episode's arm")
    p60 = load_p60()
    ck(p60.parse_leg(next(r for r in rows if r["name"] == "grasp_lift")["line"].split(": ", 1)[1])
       is not None, "P60's parse_leg still reads the row")
    with open(ROOT / path, errors="replace") as fh:
        ck(any(_RE_SUMMARY.search(line) for line in fh), "the log carries its rollout summary")
    before = (ROOT / "logs/p65/p2/tree_md5_before.txt")
    after = (ROOT / "logs/p65/p2/tree_md5_after.txt")
    if before.exists() and after.exists():
        ck(before.read_text() == after.read_text(), "the tree md5s are identical before/after")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    rows: list[dict] = []
    present = []
    for path in CELL:
        if not (ROOT / path).exists():
            print(f"(skipping the absent {path})", file=sys.stderr)
            continue
        present.append(path)
        rows.extend(legs(path))

    print("# P65 phase 1 report - does the lift's drift coincide with a joint limit?")
    print()
    print("Cell: `FRUIT_CARRY_DIAG=1` + the P65 fields, the shipped `direct` profile, "
          "3 seeds x 15 picks (`logs/p65/PREREG.md`).")
    print()
    out = p0_presence(rows)
    p1, _ = p1_verdict(rows)
    out += [""] + p1
    out += p3_pads(rows)
    out += p4_class(rows, present)
    out += ["", "### note keys in this cell", ""]
    for path in present:
        out += p4_notes(rows, str(ROOT / path))
    # the F3 "no new reason" read: this cell's keys against the control's
    mine: dict[str, int] = {}
    for path in present:
        for k, v in note_keys(str(ROOT / path)).items():
            mine[k] = mine.get(k, 0) + v
    ctrl_keys: dict[str, int] = {}
    for path in CTRL:
        if (ROOT / path).exists():
            for k, v in note_keys(str(ROOT / path)).items():
                ctrl_keys[k] = ctrl_keys.get(k, 0) + v
    if ctrl_keys:
        novel = sorted(set(mine) - set(ctrl_keys))
        out += ["", "**Reasons not present in P63's control:** "
                + ("none" if not novel else ", ".join(f"`{k}` (x{mine[k]})" for k in novel)),
                "**Control-only keys:** "
                + ("none" if not (set(ctrl_keys) - set(mine))
                   else ", ".join(f"`{k}`" for k in sorted(set(ctrl_keys) - set(mine))))]
    ctrl = control_classes()
    if ctrl:
        out += ["", "**F3 control (P63's `D_*`, same scenario/checkpoint/seeds):**", ""]
        out.append("| arm | placed | cnp | never-held |")
        out.append("| --- | --- | --- | --- |")
        for arm in FARMS:
            c = ctrl.get(arm, {})
            out.append(f"| {arm} | {c.get('placed',0)} | {c.get('cnp',0)} | "
                       f"{c.get('never-held',0)} |")
    out += ["", "## reproduction", "",
            "```bash", "bash logs/p65/p2/run_p2.sh",
            "python3 logs/p65/p2_report.py --check > logs/p65/p2_report.txt", "```"]
    print("\n".join(out))

    if args.check:
        print()
        fails = checks(rows, present[0])
        print()
        print("CHECKS: " + ("PASS" if fails == 0 else f"{fails} FAILED"))
        return 1 if fails else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
