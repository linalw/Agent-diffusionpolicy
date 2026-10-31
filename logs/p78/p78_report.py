#!/usr/bin/env python3
"""P78 report: the **site-scoped** clamp force (left `place*` legs) and its dose.

Reads `logs/p78/direct/<arm>_<seed>.log` for the ladder (`C` = the scope unset,
i.e. the shipped 10 N build cap; `S30`/`S45`/`S60` = the runtime cap at 30/45/60 N
on the left arm's `place*` legs only) and prints:

* **§0 the manipulation check** - the armed run's own row, the per-leg
  `raise`/`restore` read-backs, and the **delivered** `force_min` split by leg
  class: `place*` (the scoped site) against `grasp_lift` (which must stay at the
  shipped ~9.7-10 N, the site-scoping proof);
* **§1 the leg census** per cell - carry legs, escapes (`clean_slip_max > 100 mm`
  with a pinch), the `> 800 mm` form, legs **pried** to the stop
  (`sep_max >= 95 mm`), never-held legs;
* **§2 / §2b** every escape and every pried leg, one row each;
* **§3 the mode split** - `sep_max - dia` per escape leg (P77's radial-vs-axial
  discriminator: `>= +13 mm` radial, `<= +10 mm` axial);
* **§4 the strawberry** legs (the binding class) with the crush guards;
* **§5 the counts** per cell (a report, not a rate);
* **§6 the ladder** - D1-D5 evaluated per rung against C (PREREG §3);
* **§7 the guards** - the right, the note classes, the landing class, the cycle;
* **§8 the blast radius** (PREREG §4) if `logs/p78/b1_*` / `b2_*` exist.

`--check` asserts the manipulation check per arm class and that every cell has its
15 episodes and its `[carry]` rows - so a printed table cannot silently drop legs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

OPEN_STOP_MM = 98.1
AT_STOP_MM = 95.0
ESCAPE_MM = 100.0
STRICT_ESCAPE_MM = 800.0
CRUSH_INTERFERENCE_MM = 15.0
CRUSH_FORCE_N = 35.0
#: PREREG §3 D6 (a descriptor, not a gate): P77's radial/axial split.
RADIAL_MM = 13.0
AXIAL_MM = 10.0
#: PREREG §3 D5.
CYCLE_MARGIN = 1.05
#: PREREG §3 D4.
RIGHT_MARGIN = 1

#: The shipped-cap archive the blast-radius run is read against (P76 §8).
ARCHIVE_ACCEPT = ROOT / "logs/p76/accept_noharm_full.log"
ARCHIVE_ACCEPT_LINES = 346
ARCHIVE_ACCEPT_MD5 = "d0079a237202e2f9b0e152655af32a77"
TWOLINE_REF_MD5 = "eb697f23"

RE_EP_START = re.compile(
    r"\[rl\] episode (\d+): (\w+) grade=(\w) d=([\d.]+)cm bin=(-?\d+) arm=(\w+)"
)
RE_EP_END = re.compile(
    r"\[rl\] episode (\d+): (\w+) d=([\d.]+)cm bin=(-?\d+) arm=(\w+) "
    r"success=(\w+) grasped=(\w+) placed=(\w+) ticks=(\d+).*?notes=(\[.*?\])(?= presentation=)"
)
RE_CARRY = re.compile(r"\[carry\] (\w+) (\w+): ticks=(\d+)/(\d+)")
RE_SCOPE_ROW = re.compile(
    r"\[drive\] finger cap scope: (\S+) x ([\d.]+) N \(runtime, ([^)]*)\)"
)
RE_SCOPE_LEG = re.compile(
    r"\[drive\] (\w+) (\w+) finger cap (raise|restore): ([\d.]+) -> ([\d.]+) N "
    r"\(readback ([\d.]+|n/a) N\)"
)
RE_ANY_NUM = re.compile(r"\d+(?:\.\d+)?")


def num(field: str, key: str) -> float | None:
    m = re.search(rf"\b{re.escape(key)}=(-?[\d.]+)", field)
    return None if m is None else float(m.group(1))


def field_of(line: str, key: str) -> str | None:
    m = re.search(rf"\b{re.escape(key)}=(\S+)", line)
    return None if m is None else m.group(1)


def _f(value, spec: str) -> str:
    if value is not None:
        return format(value, spec)
    m = re.match(r"([<>]?)\+?(\d+)", spec)
    return f"{'n/a':>{int(m.group(2))}}" if m else "n/a"


def md5_of(lines: list[str]) -> str:
    return hashlib.md5(("\n".join(lines) + "\n").encode()).hexdigest()


def _log_comb(n: int, k: int) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher_exact(a: int, b: int, c: int, d: int) -> float:
    n = a + b + c + d
    r1, c1 = a + b, a + c
    denom = _log_comb(n, c1)

    def p(x: int) -> float:
        return math.exp(_log_comb(r1, x) + _log_comb(n - r1, c1 - x) - denom)

    lo, hi = max(0, c1 - (n - r1)), min(r1, c1)
    obs = p(a)
    total = sum(prob for prob in (p(x) for x in range(lo, hi + 1))
                if prob <= obs * (1 + 1e-12))
    return min(1.0, total)


class Leg:
    def __init__(self, line: str, episode: dict) -> None:
        head = RE_CARRY.search(line)
        self.side, self.name = head.group(1), head.group(2)
        self.ticks = int(head.group(3))
        self.episode = episode
        self.slip = num(line, "clean_slip_max") or 0.0
        self.sep_loss = num(line, "sep@loss")
        self.sep_end = num(line, "sep_end")
        self.dia = num(line, "dia")
        m = re.match(r"([\d.]+)@t(\d+)", field_of(line, "sep_max") or "")
        self.sep_max = float(m.group(1)) if m else None
        self.fmax = num(line, "fmax")
        self.fmin = num(line, "force_min")
        self.contacts_onset = num(line, "contacts@onset")

    @property
    def never_held(self) -> bool:
        return self.fmax is None or self.fmax == 0.0

    @property
    def escape(self) -> bool:
        return self.slip > ESCAPE_MM and not self.never_held

    @property
    def strict_escape(self) -> bool:
        return self.slip > STRICT_ESCAPE_MM and not self.never_held

    @property
    def at_stop(self) -> bool:
        return self.sep_max is not None and self.sep_max >= AT_STOP_MM

    @property
    def physical(self) -> bool:
        return self.slip < 10_000.0

    @property
    def beyond_width(self) -> float | None:
        if self.sep_max is None or self.dia is None:
            return None
        return self.sep_max - self.dia

    @property
    def mode(self) -> str:
        b = self.beyond_width
        if b is None:
            return "n/a"
        if b >= RADIAL_MM:
            return "radial"
        if b <= AXIAL_MM:
            return "axial"
        return "between"

    @property
    def loss_interference(self) -> float | None:
        if self.sep_loss is None or self.dia is None:
            return None
        return self.sep_loss - self.dia

    @property
    def crush_c1(self) -> bool:
        i = self.loss_interference
        return (i is not None and i <= -CRUSH_INTERFERENCE_MM
                and self.physical and not self.never_held)

    @property
    def crush_c2(self) -> bool:
        return bool(self.escape and self.fmin is not None and self.fmin >= CRUSH_FORCE_N)

    def row(self) -> str:
        return (
            f"    {self.episode['species']:<12}{self.episode['dia']:>5.1f}cm "
            f"{self.side:<5}{self.name:<11}"
            f"slip={self.slip:8.1f} sep_max={_f(self.sep_max, '6.1f')}"
            f" dia={_f(self.dia, '6.1f')} max-dia={_f(self.beyond_width, '>+7.1f')}"
            f" [{self.mode:<7}]"
            f" fmax={_f(self.fmax, '>6.2f')} fmin={_f(self.fmin, '>6.2f')}"
            f"{' STOP' if self.at_stop else ''}"
        )


class Run:
    def __init__(self, arm: str, seed: str, path: Path, rollouts: Path | None = None) -> None:
        self.arm, self.seed, self.path = arm, seed, path
        self.rollouts = rollouts or (ROOT / "logs/p78/rollouts")
        self.lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        self.scope_token = None
        self.scope_cap = None
        self.scope_legs: list[tuple] = []
        for line in self.lines:
            m = RE_SCOPE_ROW.search(line)
            if m and self.scope_token is None:
                self.scope_token, self.scope_cap = m.group(1), float(m.group(2))
            m = RE_SCOPE_LEG.search(line)
            if m:
                self.scope_legs.append((m.group(1), m.group(2), m.group(3),
                                        float(m.group(4)), float(m.group(5)),
                                        m.group(6)))
        self.episodes: list[dict] = []
        self.legs: list[Leg] = []
        current = None
        for line in self.lines:
            m = RE_EP_START.search(line)
            if m and "success=" not in line:
                current = {
                    "index": int(m.group(1)), "species": m.group(2),
                    "grade": m.group(3), "dia": float(m.group(4)),
                    "bin": int(m.group(5)), "arm": m.group(6), "outcome": None,
                }
                self.episodes.append(current)
                continue
            m = RE_EP_END.search(line)
            if m and current is not None:
                current["outcome"] = {
                    "success": m.group(6) == "True",
                    "grasped": m.group(7) == "True",
                    "placed": m.group(8) == "True",
                    "ticks": int(m.group(9)),
                    "notes": m.group(10),
                }
                continue
            if "[carry]" in line and RE_CARRY.search(line):
                if current is None:
                    current = {
                        "index": -1, "species": "?", "grade": "?", "dia": float("nan"),
                        "bin": -1, "arm": "?", "outcome": None,
                    }
                    self.episodes.append(current)
                self.legs.append(Leg(line, current))
        for e in self.episodes:
            if e["outcome"] is None:
                e["outcome"] = {"success": False, "grasped": False, "placed": False,
                                "ticks": 0, "notes": "['no outcome row']"}

    def manifest(self) -> dict:
        base = self.rollouts / f"{self.arm}_{self.seed}"
        paths = sorted(base.glob("*/manifest.json"))
        if not paths:
            return {}
        return json.loads(paths[0].read_text(encoding="utf-8"))

    @property
    def armed(self) -> bool:
        return self.scope_token is not None

    def force_medians(self) -> tuple[float | None, float | None]:
        """(place* force_min median, grasp_lift force_min median) for `left`."""
        def med(prefix: str) -> float | None:
            vals = [leg.fmin for leg in self.legs
                    if leg.side == "left" and leg.name.startswith(prefix)
                    and leg.fmin is not None and leg.fmin > 0]
            return statistics.median(vals) if vals else None
        return med("place"), med("grasp")

    def force_medians_max(self) -> float | None:
        """The median of the `place*` legs' peak tactile force (`fmax`).

        The cap bounds the drive, so a held leg's peak is the clamp read; the
        leg *minimum* (`force_min`) is the leg's weakest moment and is set by
        contact transients, not by the cap (RESULTS §0.1).
        """
        vals = [leg.fmax for leg in self.legs
                if leg.side == "left" and leg.name.startswith("place")
                and leg.fmax is not None and leg.fmax > 0]
        return statistics.median(vals) if vals else None

    @property
    def placed(self) -> list[dict]:
        return [e for e in self.episodes if e["outcome"]["placed"]]

    def split(self) -> dict[str, int]:
        out = {"placed": 0, "cnp": 0, "never-held": 0}
        for e in self.episodes:
            o = e["outcome"]
            if o["placed"]:
                out["placed"] += 1
            elif o["grasped"]:
                out["cnp"] += 1
            else:
                out["never-held"] += 1
        return out

    def side(self, which: str) -> list[dict]:
        return [e for e in self.episodes if e["arm"] == which]

    def side_placed(self, which: str) -> int:
        return sum(1 for e in self.side(which) if e["outcome"]["placed"])

    def side_cnp(self, which: str) -> int:
        return sum(1 for e in self.side(which)
                   if e["outcome"]["grasped"] and not e["outcome"]["placed"])

    def side_never(self, which: str) -> int:
        return sum(1 for e in self.side(which) if not e["outcome"]["grasped"])

    def legs_on(self, which: str) -> list[Leg]:
        return [leg for leg in self.legs if leg.side == which]

    def notes_of(self, placed: bool) -> list[str]:
        return [e["outcome"]["notes"] for e in self.episodes
                if e["outcome"]["placed"] is placed]


def note_key(note: str) -> str:
    m = re.search(r"'(.*)'", note)
    text = m.group(1) if m else note.strip("[]")
    return RE_ANY_NUM.sub("#", text)[:80]


def report(arms: list[str], seeds: list[str], check: bool,
           logdir: Path, rollouts: Path) -> int:
    runs: list[Run] = []
    missing = []
    for seed in seeds:
        for arm in arms:
            path = logdir / f"{arm}_{seed}.log"
            if not path.exists():
                missing.append(path.name)
                continue
            runs.append(Run(arm, seed, path, rollouts))
    if missing:
        print(f"(missing cells: {', '.join(missing)})")

    print("=" * 116)
    print("P78 - the site-scoped clamp force (left `place*` legs) and its dose")
    print(f"PREREG 01077e1a; C = the scope unset (shipped 10 N), "
          f"S<n> = FRUIT_FINGER_MAXFORCE_SCOPE=place-left SCOPED=<n>")
    print("=" * 116)

    # ---- 0. manipulation check ---------------------------------------
    print("\n## 0. The manipulation check (PREREG §1): did the cap reach the drive,")
    print("   on the scoped site only?")
    print("   `place*` fmin/fmax = the leg's MINIMUM and MAXIMUM tactile force. The cap")
    print("   bounds the drive, so the leg MAX is the clamp read; the leg MIN is the")
    print("   leg's weakest moment, set by contact transients, not by the cap (§0.1 in")
    print("   RESULTS.md - the recorded PREREG correction).")
    bad = 0
    print(f"  {'arm':<5}{'seed':<6}{'armed row':<16}{'raise/restore rows':<22}"
          f"{'place* fmin':<13}{'place* fmax':<13}{'lift fmin':<12}"
          f"{'manifest scope':<16}{'evaluable'}")
    for run in runs:
        man = run.manifest()
        phys = man.get("physics", {})
        sc = phys.get("finger_cap_scope")
        rb = phys.get("finger_drive", {}).get("readback_matches")
        place_f, lift_f = run.force_medians()
        place_max = run.force_medians_max()
        n_raise = sum(1 for r in run.scope_legs if r[2] == "raise")
        n_rest = sum(1 for r in run.scope_legs if r[2] == "restore")
        rb_ok = all(abs(float(r[5]) - r[4]) < 1e-6
                    for r in run.scope_legs if r[5] != "n/a")
        if run.arm == "C":
            ok = (not run.armed and not run.scope_legs
                  and (sc is None) and (lift_f is None or lift_f < 15.0)
                  and (place_f is None or place_f < 15.0))
        else:
            cap = float(run.arm[1:])
            ok = (run.armed and abs((run.scope_cap or 0.0) - cap) < 1e-6
                  and n_raise == n_rest >= 1 and rb_ok
                  and place_f is not None and place_f >= 0.75 * cap
                  and place_max is not None and place_max <= 1.10 * cap
                  and (lift_f is None or lift_f < 15.0)
                  and sc is not None and abs(sc["arms"].get("left", 0.0) - cap) < 1e-6)
        # every scoped run must also restore to the shipped cap at the manifest
        if run.arm != "C" and rb is False:
            ok = False
        bad += 0 if ok else 1
        armed = ("(off, unset)" if not run.armed
                 else f"{run.scope_token} x {run.scope_cap:.0f}")
        if sc is None:
            sc_txt = "null"
        else:
            sc_txt = "left {:.0f}".format(sc["arms"].get("left", float("nan")))
        print(f"  {run.arm:<5}{run.seed:<6}{armed:<16}"
              f"{f'{n_raise}/{n_rest}':<22}{_f(place_f, '.2f'):<13}"
              f"{_f(place_max, '.2f'):<13}{_f(lift_f, '.2f'):<12}"
              f"{sc_txt:<16}"
              f"{'yes' if ok else 'NO'}")
    print("  the scoped contract: `place*` fmin >= 75 % and fmax <= 110 % of the cap")
    print("  (P41's law plus the transient band), `grasp_lift` < 15 N (the PICK keeps")
    print("  the shipped cap - the site-scoping proof), every raise paired with a")
    print("  restore whose read-back is the value asked for, readback_matches true.")

    # ---- 1. leg census ------------------------------------------------
    print("\n## 1. The leg census (PREREG §3)")
    print(f"   escape = clean_slip_max > {ESCAPE_MM:.0f} mm with a pinch;"
          f" pried = sep_max >= {AT_STOP_MM:.0f} mm of the {OPEN_STOP_MM:.1f} mm stop")
    print(f"  {'arm':<5}{'seed':<6}{'side':<6}{'legs':<6}{'escape':<8}{'>800mm':<8}"
          f"{'pried':<7}{'never-held':<12}{'sep_max max':<12}")
    pooled: dict[tuple[str, str], dict[str, int]] = {}
    for run in runs:
        for side in ("left", "right"):
            legs = run.legs_on(side)
            esc = [l for l in legs if l.escape]
            agg = pooled.setdefault((run.arm, side),
                                    {"legs": 0, "esc": 0, "pried": 0, "never": 0})
            agg["legs"] += len(legs)
            agg["esc"] += len(esc)
            agg["pried"] += sum(1 for l in legs if l.at_stop)
            agg["never"] += sum(1 for l in legs if l.never_held)
            print(f"  {run.arm:<5}{run.seed:<6}{side:<6}{len(legs):<6}{len(esc):<8}"
                  f"{sum(1 for l in esc if l.strict_escape):<8}"
                  f"{sum(1 for l in legs if l.at_stop):<7}"
                  f"{sum(1 for l in legs if l.never_held):<12}"
                  f"{_f(max((l.sep_max for l in legs if l.sep_max is not None), default=None), '.1f')}")
    print("\n  --- pooled per arm (the mechanism denominators)")
    print(f"  {'arm':<5}{'side':<6}{'legs':<6}{'escape':<8}{'pried':<7}{'never-held':<12}")
    for arm in arms:
        for side in ("left", "right"):
            a = pooled.get((arm, side), {"legs": 0, "esc": 0, "pried": 0, "never": 0})
            print(f"  {arm:<5}{side:<6}{a['legs']:<6}{a['esc']:<8}{a['pried']:<7}"
                  f"{a['never']:<12}")

    # ---- 2. escape legs ------------------------------------------------
    print("\n## 2. Every escape leg (clean_slip_max > 100 mm, pinched)")
    for run in runs:
        esc = [l for l in run.legs if l.escape]
        print(f"\n  --- {run.arm} seed {run.seed}: {len(esc)} escape leg(s)")
        for leg in esc:
            print(leg.row())
        if not esc:
            print("    (none)")
    print("\n## 2b. Every pried leg (sep_max >= 95 mm, escape or not)")
    for run in runs:
        pried = [l for l in run.legs if l.at_stop]
        print(f"\n  --- {run.arm} seed {run.seed}: {len(pried)} pried leg(s)")
        for leg in pried:
            print(leg.row())
        if not pried:
            print("    (none)")

    # ---- 3. the mode split --------------------------------------------
    print("\n## 3. The mode split on the escape legs - `sep_max - dia` (P77 §2)")
    print(f"   radial = >= +{RADIAL_MM:.0f} mm beyond the fruit's own width (an expulsion")
    print(f"   through an opening gap); axial = <= +{AXIAL_MM:.0f} mm (the pads closed on it")
    print("   and the payload walked out along the tool axis)")
    print(f"  {'arm':<5}{'seed':<6}{'escapes':<9}{'radial':<8}{'axial':<7}{'between':<9}"
          f"{'max-dia range'}")
    for run in runs:
        esc = [l for l in run.legs if l.escape]
        vals = [l.beyond_width for l in esc if l.beyond_width is not None]
        print(f"  {run.arm:<5}{run.seed:<6}{len(esc):<9}"
              f"{sum(1 for l in esc if l.mode == 'radial'):<8}"
              f"{sum(1 for l in esc if l.mode == 'axial'):<7}"
              f"{sum(1 for l in esc if l.mode == 'between'):<9}"
              f"{(_f(min(vals), '+.1f') + ' .. ' + _f(max(vals), '+.1f')) if vals else 'n/a'}")

    # ---- 4. the strawberry --------------------------------------------
    print("\n## 4. The smallest fruit (the binding class), with the crush guards")
    print(f"  {'arm':<5}{'seed':<6}{'fruit':<12}{'dia':>6}{'sep@loss':>10}"
          f"{'loss-dia':>10}{'sep_max':>9}{'max-dia':>9}{'fmax':>8}{'fmin':>8}"
          f"{'slip':>9}  outcome")
    for run in runs:
        for leg in run.legs:
            if leg.dia is None or not leg.name.startswith("grasp"):
                continue
            if leg.episode["species"] != "strawberry" and leg.dia > 36.0:
                continue
            print(f"  {run.arm:<5}{run.seed:<6}{leg.episode['species']:<12}"
                  f"{leg.dia:>6.1f}{_f(leg.sep_loss, '>10.1f')}"
                  f"{_f(leg.loss_interference, '>+10.1f')}{_f(leg.sep_max, '>9.1f')}"
                  f"{_f(leg.beyond_width, '>+9.1f')}"
                  f"{_f(leg.fmax, '>8.2f')}{_f(leg.fmin, '>8.2f')}{leg.slip:>9.1f}"
                  f"  {'placed' if leg.episode['outcome']['placed'] else 'LOST'}"
                  f"{' CRUSH' if (leg.crush_c1 or leg.crush_c2) else ''}")

    # ---- 5. counts -----------------------------------------------------
    print("\n## 5. The counts, per cell - a REPORT, not a rate (PREREG §3)")
    print(f"  {'arm':<5}{'seed':<6}{'n':<4}{'placed':<8}{'left':<9}{'right':<9}"
          f"{'cnp':<6}{'never':<7}{'ticks/att':<11}{'arm mix L/R'}")
    for run in runs:
        n = len(run.attempts if hasattr(run, "attempts") else run.episodes)
        la = len(run.side("left"))
        ra = n - la
        ticks = [e["outcome"]["ticks"] for e in run.episodes if e["outcome"]["ticks"]]
        print(f"  {run.arm:<5}{run.seed:<6}{n:<4}{len(run.placed):<8}"
              f"{run.side_placed('left')}/{la:<7}{run.side_placed('right')}/{ra:<7}"
              f"{run.split()['cnp']:<6}{run.split()['never-held']:<7}"
              f"{statistics.median(ticks) if ticks else 0:<11.0f}{la}/{ra}")

    # ---- 6. the ladder -------------------------------------------------
    print("\n## 6. The ladder: D1-D5 per rung against C (PREREG §3)")
    print("   the per-cell rows below are informational; the RULE is evaluated on the")
    print("   POOLED arm (every cell of the rung against every cell of C), because the")
    print("   mechanism denominators are leg counts and a single 15-pick cell is one")
    print("   draw of a non-reproducible branch. See the pooled verdict block.")
    print(f"\n  {'rung':<6}{'seed':<6}{'L placed':<12}{'R placed':<12}{'cycle':<9}"
          f"{'pried':<8}{'crush':<7}")
    for run in runs:
        ticks = statistics.median([e["outcome"]["ticks"] for e in run.episodes
                                   if e["outcome"]["ticks"]] or [0])
        crush = sum(1 for l in run.legs if l.crush_c1 or l.crush_c2)
        pried = sum(1 for l in run.legs if l.side == "left" and l.at_stop)
        lp = "{}/{}".format(run.side_placed("left"), len(run.side("left")))
        rp = "{}/{}".format(run.side_placed("right"), len(run.side("right")))
        print(f"  {run.arm:<6}{run.seed:<6}{lp:<12}{rp:<12}"
              f"{ticks:<9.0f}{pried:<8}{crush:<7}")

    def arm_pool(arm: str) -> dict:
        rs = [r for r in runs if r.arm == arm]
        ticks = [statistics.median([e["outcome"]["ticks"] for e in r.episodes
                                    if e["outcome"]["ticks"]] or [0]) for r in rs]
        return {
            "left": sum(r.side_placed("left") for r in rs),
            "left_n": sum(len(r.side("left")) for r in rs),
            "right": sum(r.side_placed("right") for r in rs),
            "right_n": sum(len(r.side("right")) for r in rs),
            "esc": pooled.get((arm, "left"), {}).get("esc", 0),
            "legs": pooled.get((arm, "left"), {}).get("legs", 0),
            "pried": pooled.get((arm, "left"), {}).get("pried", 0),
            "crush": sum(1 for r in rs for l in r.legs if l.crush_c1 or l.crush_c2),
            "cycle": statistics.median(ticks) if ticks else 0,
        }

    base = arm_pool("C")
    print(f"\n  --- the pooled verdict (C: left {base['left']}/{base['left_n']},"
          f" right {base['right']}/{base['right_n']}, escapes {base['esc']}/{base['legs']},"
          f" pried {base['pried']}, crush {base['crush']}, cycle {base['cycle']:.0f})")
    print(f"  {'rung':<6}{'L placed':<12}{'escapes':<15}{'pried':<13}{'right':<12}"
          f"{'cycle':<10}{'crush':<7}{'D1-D5'}")
    verdicts: dict[str, dict[str, bool]] = {}
    for arm in arms:
        if arm == "C":
            continue
        p = arm_pool(arm)
        d1 = p["left"] >= base["left"]
        d2 = (p["esc"] * 3 <= base["esc"]) if base["esc"] else None
        d2 = bool(d2) and (p["pried"] * 3 <= base["pried"])
        d3 = p["crush"] == 0
        d4 = p["right"] >= base["right"] - RIGHT_MARGIN
        d5 = p["cycle"] <= base["cycle"] * CYCLE_MARGIN
        verdicts[arm] = {"D1": d1, "D2": d2, "D3": d3, "D4": d4, "D5": d5}
        bits = "".join("+" if v else "-" for v in (d1, d2, d3, d4, d5))
        lp_txt = "{}/{}".format(p["left"], p["left_n"])
        rp_txt = "{}/{}".format(p["right"], p["right_n"])
        esc_txt = "{}/{}".format(p["esc"], p["legs"])
        print(f"  {arm:<6}{lp_txt:<12}{esc_txt:<15}{p['pried']:<13}"
              f"{rp_txt:<12}{p['cycle']:<10.0f}{p['crush']:<7}{bits}")
    print("\n  D1 placed >= C (pooled); D2 escapes AND pries <= 1/3 of C (pooled legs);")
    print("  D3 zero crush legs across the rung's cells; D4 right within 1; D5 cycle")
    print("  (median of cell medians) <= +5 %.")
    dominate = [a for a, v in verdicts.items() if all(v.values())]
    print(f"  -> rungs satisfying D1-D5: {', '.join(dominate) if dominate else 'none'}")
    for arm, v in sorted(verdicts.items()):
        fails = [k for k, ok in v.items() if not ok]
        if fails:
            print(f"     {arm} fails: {', '.join(fails)}")

    # ---- 7. guards ------------------------------------------------------
    print("\n## 7. The guards")
    print("\n  --- the note strings on non-placed episodes (digits normalised out)")
    for arm in arms:
        agg: dict[str, dict[str, int]] = {}
        for r in runs:
            if r.arm != arm:
                continue
            for e in r.episodes:
                if e["outcome"]["placed"]:
                    continue
                k = note_key(e["outcome"]["notes"])
                if k.startswith("intercept trigger"):
                    k = "(no reason note; the class is read from grasped/placed)"
                rec = agg.setdefault(k, {"left": 0, "right": 0})
                rec[e["arm"]] += 1
        print(f"  {arm}:")
        if not agg:
            print("    (no failure)")
        for k, rec in sorted(agg.items(), key=lambda kv: -(kv[1]["left"] + kv[1]["right"])):
            print(f"    {rec['left']:>3}L {rec['right']:>3}R  {k}")

    def reason_keys(arm: str, side: str | None = None) -> set[str]:
        keys = set()
        for r in runs:
            if r.arm != arm:
                continue
            for e in r.episodes:
                if e["outcome"]["placed"]:
                    continue
                if side is not None and e["arm"] != side:
                    continue
                k = note_key(e["outcome"]["notes"])
                if not k.startswith("intercept trigger"):
                    keys.add(k)
        return keys
    for arm in arms:
        if arm == "C":
            continue
        new = sorted(reason_keys(arm, "right") - reason_keys("C", "right"))
        print(f"\n  --- new RIGHT failure reasons in {arm} (not seen in C): "
              + (", ".join(new) if new else "none"))

    print("\n  --- the landing class (the payload went nowhere)")
    keys = ("did not land", "fell off the line", "discharged")
    for arm in arms:
        counts = {k: 0 for k in keys}
        for r in runs:
            if r.arm != arm:
                continue
            for e in r.episodes:
                for k in keys:
                    if k in e["outcome"]["notes"] and not e["outcome"]["placed"]:
                        counts[k] += 1
        print(f"  {arm}: " + ", ".join(f"{k} {v}" for k, v in counts.items()))

    print("\n  --- cycle ticks (median per cell; a cost read, not a rate)")
    for arm in arms:
        vals = []
        for r in runs:
            if r.arm != arm:
                continue
            t = [e["outcome"]["ticks"] for e in r.episodes if e["outcome"]["ticks"]]
            if t:
                vals.append(statistics.median(t))
        print(f"  {arm}: {', '.join(f'{v:.0f}' for v in vals)}"
              f" (median of medians {statistics.median(vals) if vals else 0:.0f})")

    # ---- 8. the blast radius -------------------------------------------
    print("\n## 8. The blast radius (PREREG §4) - the scope ARMED on both scripted paths")
    b1 = ROOT / "logs/p78/b1_accept_armed.log"
    if b1.exists():
        def fruit_only(path: Path) -> list[str]:
            return [l for l in path.read_text(encoding="utf-8", errors="replace").splitlines()
                    if l.startswith("[fruit]")]
        lines, ref = fruit_only(b1), fruit_only(ARCHIVE_ACCEPT)
        same = sum(1 for x, y in zip(lines, ref) if x == y)
        print(f"  B1 scripted acceptance, scope armed: {len(lines)} [fruit] lines"
              f" (archive {ARCHIVE_ACCEPT_LINES}); md5 {md5_of(lines)}"
              f" (archive {ARCHIVE_ACCEPT_MD5})")
        print(f"     identical at the same index: {same}/{min(len(lines), len(ref))}"
              f"  -> {'BYTE-IDENTICAL' if lines == ref else 'DIFFERS'}")
        drv = ROOT / "logs/p78/b1_accept_armed.driver"
        if drv.exists():
            text = drv.read_text(encoding="utf-8", errors="replace")
            fp = [l.strip() for l in text.splitlines() if "fingerprint:" in l]
            print(f"     fingerprint: {'; '.join(fp) if fp else '(not reported)'}")
            sc = [l.strip() for l in lines + text.splitlines() if "finger cap scope" in l]
            print(f"     scope row in the scripted run: {sc[0][:110] if sc else 'ABSENT'}")
    else:
        print("  B1 scripted acceptance, scope armed: (not run)")
    b2 = ROOT / "logs/p78/b2_twoline_armed.log"
    if b2.exists():
        gate = ROOT / "logs/p78/b2_twoline_armed.gate"
        text = b2.read_text(encoding="utf-8", errors="replace")
        fruit = [l for l in text.splitlines() if l.startswith("[fruit]")]
        print(f"  B2 two-line, scope armed: {len(fruit)} [fruit] lines"
              f" (reference {TWOLINE_REF_MD5}, NOT re-recorded)")
        if gate.exists():
            g = gate.read_text(encoding="utf-8", errors="replace").splitlines()
            fp = [l.strip() for l in g if "fingerprint:" in l]
            verdict = [l for l in g if l.startswith("190:")]
            print(f"     fingerprint: {'; '.join(fp) if fp else '(not reported)'}")
            print(f"     gate: {'; '.join(v[:120] for v in verdict) or '(no verdict line)'}")
    else:
        print("  B2 two-line, scope armed: (not run)")

    # ---- the check ------------------------------------------------------
    if check:
        problems = []
        if bad:
            problems.append(f"{bad} cell(s) whose cap did not reach the scoped site")
        for run in runs:
            if len(run.episodes) != 15:
                problems.append(f"{run.arm}_{run.seed}: {len(run.episodes)} episodes, expected 15")
            if not run.legs:
                problems.append(f"{run.arm}_{run.seed}: no [carry] rows parsed")
        if problems:
            print("\nCHECK FAILED:")
            for p in problems:
                print(f"  - {p}")
            return 1
        print(f"\nCHECK OK: every cell's cap reached the scoped site only, all "
              f"{len(runs)} cells carry 15 episodes, and all "
              f"{sum(len(r.legs) for r in runs)} [carry] rows parsed.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="C S30 S45 S60")
    ap.add_argument("--seeds", default="77")
    ap.add_argument("--dir", default=None)
    ap.add_argument("--rollouts", default=None)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    def resolve(p: str | None, default: Path) -> Path:
        if p is None:
            return default
        path = Path(p)
        return path if path.is_absolute() else (ROOT / path)

    return report(args.arms.split(), args.seeds.split(), args.check,
                  resolve(args.dir, ROOT / "logs/p78/direct"),
                  resolve(args.rollouts, ROOT / "logs/p78/rollouts"))


if __name__ == "__main__":
    sys.exit(main())
