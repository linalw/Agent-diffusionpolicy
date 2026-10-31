#!/usr/bin/env python3
"""P79 report: **where** P77's 60 N count win comes from - the pick or the place.

Reads `logs/p79/direct/<arm>_<seed>.log` for the three arms (`C` = the scope
unset, i.e. the shipped 10 N build cap; `G30`/`G60` = the runtime cap on the left
arm's single `grasp_lift` leg; the place transfer and the right arm untouched)
and prints:

* **§0 the manipulation check / site proof** (`PREREG.md` §4) - the armed run's
  own row, one `raise`+`restore` per left `grasp_lift` leg and **zero** on any
  `place*` leg or the right arm, the **delivered** force by leg class
  (`grasp_lift` peak tracks the cap; `place*` stays in C's band), and the
  manifest's `physics.finger_cap_scope.sites` + `readback_matches`;
* **§1 the leg census** per cell and pooled - legs, escapes
  (`clean_slip_max > 100 mm` with a pinch), the `> 800 mm` form, legs **pried**
  to the stop (`sep_max >= 95 mm`), never-held legs (`fmax == 0`);
* **§2 the counts** per cell - placed, per-arm, cnp, never-held (episode class),
  ticks/attempt, arm mix;
* **§3 the pooled primary** - left placed with Fisher against C, the per-seed
  table (P1a/P1b/P1c), and the P77/P78/P78 records beside it;
* **§4 the lift leg's own state** (E4, H-pick-b) - `min_contacts <= 1` legs,
  `sep_end - gap_start`, `force_min`/`fmax` medians;
* **§5 the place guard** (E5) - left `place*` escapes/pries and peak force: the
  cap must not be reachable there;
* **§6 the strawberry** (E8) - every 3.4-3.9 cm leg with the crush guards;
* **§7 the ledger** by note class, the right arm (E6) and the cycle (E7);
* **§8 the decision rule** (PREREG §6) P1-P6 -> the exclusive verdict;
* **§9 the blast radius** (PREREG §8) if `logs/p79/b1_*` / `b2_*` exist.

`--check` asserts, per armed cell, the **structural** site proof (one
raise+restore per left `grasp_lift` leg and **zero** rows on any `place*` leg or
the right arm, the delivered lift peak in band, the manifest's `sites`), and
that every cell has its 15 episodes and its `[carry]` rows - so a printed table
cannot silently drop legs or cells (exit 1). The registered **band** clause on a
single cell's `place*` peak is **reported, not gated**: `fmax` is a peak contact
transient that exceeds the drive cap on a single leg even at 10 N (DEVIATION A1,
`PREREG.md` §9), so the gate is the pooled comparison plus the structural rows.
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
#: PREREG §6 P1a/P1c.
P1_GAIN = 3
P1_RATE = 0.75
#: PREREG §6 P4.
RIGHT_MARGIN = 1
#: PREREG §6 P6.
CYCLE_MARGIN = 1.05
#: PREREG §4 clause 3: the place's peak stays inside C's own band (P78 control).
PLACE_FMAX_BAND = 11.25
#: PREREG §1: the records this phase is read against (not re-run).
RECORDS = {
    "P77 C (global off)": dict(left=(11, 21), never=3, cnp=7, right=(21, 24),
                               pries="4/38"),
    "P77 T (global 60 N)": dict(left=(17, 20), never=0, cnp=3, right=(22, 25),
                                pries="1/40"),
    "P78 C (place off)": dict(left=(10, 18), never=2, cnp=8, right=(25, 27),
                              pries="3/36"),
    "P78 S60 (place 60 N)": dict(left=(11, 16), never=5, cnp=4, right=(25, 29),
                                 pries="1/31"),
}
#: PREREG §8: the shipped-cap archives the blast-radius run is read against.
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
    """Format a possibly-missing number; the width is honoured when missing."""
    if value is not None:
        return format(value, spec)
    m = re.match(r"([<>]?)(\d+)", spec)
    return f"{'n/a':>{int(m.group(2))}}" if m else "n/a"


def md5_of(lines) -> str:
    return hashlib.md5(("\n".join(lines) + "\n").encode()).hexdigest()


def median(values):
    values = list(values)
    return statistics.median(values) if values else None


# ---- exact statistics (no scipy on this machine) ---------------------------
def _log_comb(n: int, k: int) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher_exact(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact on [[a, b], [c, d]], exhaustive over the support."""
    n = a + b + c + d
    if n == 0:
        return 1.0
    row1, col1 = a + b, a + c
    lo, hi = max(0, col1 - (n - row1)), min(row1, col1)
    p_obs = math.exp(_log_comb(row1, a) + _log_comb(n - row1, col1 - a)
                     - _log_comb(n, col1))
    total = 0.0
    for k in range(lo, hi + 1):
        p = math.exp(_log_comb(row1, k) + _log_comb(n - row1, col1 - k)
                     - _log_comb(n, col1))
        if p <= p_obs * (1 + 1e-9):
            total += p
    return min(1.0, total)


# ---- parsing ---------------------------------------------------------------
class Leg:
    def __init__(self, line: str, episode: dict) -> None:
        head = RE_CARRY.search(line)
        self.side, self.name = head.group(1), head.group(2)
        self.ticks = int(head.group(3))
        self.episode = episode
        self.slip = num(line, "clean_slip_max") or 0.0
        self.sep_loss = num(line, "sep@loss")
        self.sep_end = num(line, "sep_end")
        self.gap_start = num(line, "gap_start")
        self.dia = num(line, "dia")
        self.fmax = num(line, "fmax")
        self.fmin = num(line, "force_min")
        self.min_contacts = num(line, "min_contacts")
        self.contacts_onset = num(line, "contacts@onset")
        m = re.match(r"([\d.]+)@t(\d+)", field_of(line, "sep_max") or "")
        self.sep_max = float(m.group(1)) if m else None

    @property
    def never_held(self) -> bool:
        return self.fmax is not None and self.fmax == 0.0

    @property
    def escape(self) -> bool:
        return self.slip > ESCAPE_MM and self.fmax is not None and self.fmax > 0.0

    @property
    def strict_escape(self) -> bool:
        return self.slip > STRICT_ESCAPE_MM and self.fmax is not None and self.fmax > 0.0

    @property
    def at_stop(self) -> bool:
        return self.sep_max is not None and self.sep_max >= AT_STOP_MM

    @property
    def lost_a_face(self) -> bool:
        return self.min_contacts is not None and self.min_contacts <= 1

    @property
    def end_minus_start(self) -> float | None:
        if self.sep_end is None or self.gap_start is None:
            return None
        return self.sep_end - self.gap_start

    @property
    def loss_interference(self) -> float | None:
        if self.sep_loss is None or self.dia is None:
            return None
        return self.sep_loss - self.dia

    @property
    def crush_c1(self) -> bool:
        i = self.loss_interference
        return (i is not None and i <= -CRUSH_INTERFERENCE_MM
                and self.slip < 10_000.0 and not self.never_held)

    def crush_c2(self, small: bool) -> bool:
        return bool(small and self.escape and self.fmin is not None
                    and self.fmin >= CRUSH_FORCE_N)

    def row(self) -> str:
        return (
            f"    {self.episode['species']:<12}{self.episode['dia']:>5.1f}cm "
            f"{self.side:<5}{self.name:<11}"
            f"slip={self.slip:8.1f} sep_max={_f(self.sep_max, '6.1f')}"
            f" dia={_f(self.dia, '6.1f')} fmax={_f(self.fmax, '>6.2f')}"
            f" fmin={_f(self.fmin, '>6.2f')}"
            f" sep_end-gap={_f(self.end_minus_start, '>7.1f')}"
            f" minc={_f(self.min_contacts, '>4.0f')}"
            f"{' STOP' if self.at_stop else ''}"
        )


class Run:
    def __init__(self, arm: str, seed: str, path: Path, rollouts: Path | None = None) -> None:
        self.arm, self.seed, self.path = arm, seed, path
        self.rollouts = rollouts or (ROOT / "logs/p79/rollouts")
        self.lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        self.scope_token = None
        self.scope_cap = None
        self.scope_rows: list[tuple] = []
        for line in self.lines:
            m = RE_SCOPE_ROW.search(line)
            if m and self.scope_token is None:
                self.scope_token, self.scope_cap = m.group(1), float(m.group(2))
            m = RE_SCOPE_LEG.search(line)
            if m:
                self.scope_rows.append((m.group(1), m.group(2), m.group(3),
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

    @property
    def placed(self) -> int:
        return sum(1 for e in self.episodes if e["outcome"]["placed"])

    def side(self, which: str) -> list[dict]:
        return [e for e in self.episodes if e["arm"] == which]

    def side_placed(self, which: str) -> int:
        return sum(1 for e in self.side(which) if e["outcome"]["placed"])

    def side_cnp(self, which: str) -> int:
        return sum(1 for e in self.side(which)
                   if e["outcome"]["grasped"] and not e["outcome"]["placed"])

    def side_never(self, which: str) -> int:
        return sum(1 for e in self.side(which) if not e["outcome"]["grasped"])

    def legs_of(self, side: str, cls: str) -> list[Leg]:
        if cls == "grasp":
            return [l for l in self.legs if l.side == side and l.name == "grasp_lift"]
        if cls == "place":
            return [l for l in self.legs if l.side == side and l.name.startswith("place")]
        return [l for l in self.legs if l.side == side or side == "*"]

    def cells(self) -> tuple[int, int]:
        ticks = [e["outcome"]["ticks"] for e in self.episodes if e["outcome"]["ticks"]]
        return (sum(ticks), len(ticks))


def note_key(note: str) -> str:
    text = re.search(r"'(.*)'", note)
    body = text.group(1) if text else note.strip("[]")
    return RE_ANY_NUM.sub("#", body)[:72]


def _p(x: float) -> str:
    return "<1e-4" if x < 1e-4 else f"{x:.4f}"


def _ratio(hit: int, n: int) -> str:
    return f"{hit}/{n}"


def _positive(legs, attr):
    return [getattr(l, attr) for l in legs
            if getattr(l, attr) is not None and getattr(l, attr) > 0]


# ---- report ----------------------------------------------------------------
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
        print(f"missing logs: {', '.join(missing)}", file=sys.stderr)
    if not runs:
        print("no logs found", file=sys.stderr)
        return 1

    fails: list[str] = []
    site_fails: list[str] = []
    band_hits: list[tuple[str, str, float]] = []
    print("=" * 78)
    print("P79 REPORT - the pick half (`grasp-left`) at 30 and 60 N against the")
    print("shipped 10 N. Counts, not rates (PREREG §7).")
    print("=" * 78)

    # ------------------------------------------------------------------ 0
    print("\n## 0. The manipulation check / site proof (PREREG §4)")
    hdr = (f"  {'arm':<5}{'seed':<6}{'scope row':<13}{'rows':<6}"
           f"{'legs armed':<28}{'L lift fmax':<12}{'L place fmax':<13}")
    print(hdr)
    for run in runs:
        by_leg: dict[str, list[int]] = {}
        for side, name, stage, _b, _w, _rb in run.scope_rows:
            key = f"{side} {name}"
            by_leg.setdefault(key, [0, 0])
            by_leg[key][0 if stage == "raise" else 1] += 1
        legs_txt = ", ".join(f"{k} {v[0]}/{v[1]}" for k, v in sorted(by_leg.items())) or "-"
        n_rows = len(run.scope_rows)
        lift = median(_positive(run.legs_of("left", "grasp"), "fmax"))
        place = median(_positive(run.legs_of("left", "place"), "fmax"))
        print(f"  {run.arm:<5}{run.seed:<6}{(run.scope_token or 'off'):<13}"
              f"{n_rows:<6}{legs_txt:<28}"
              f"{_f(lift, '6.2f'):<12}{_f(place, '6.2f'):<13}")
        if run.armed:
            bad = [r for r in run.scope_rows if r[1] != "grasp_lift"]
            if bad:
                site_fails.append(
                    f"{run.arm}_{run.seed}: {len(bad)} scope row(s) off grasp_lift")
            n_lift = len(run.legs_of("left", "grasp"))
            n_raise = sum(1 for r in run.scope_rows if r[2] == "raise")
            n_rest = sum(1 for r in run.scope_rows if r[2] == "restore")
            if not (n_raise == n_rest == n_lift):
                site_fails.append(f"{run.arm}_{run.seed}: raise/restore {n_raise}/"
                                  f"{n_rest} != {n_lift} left grasp_lift legs")
            if lift is None or lift < 0.75 * run.scope_cap:
                site_fails.append(f"{run.arm}_{run.seed}: lift fmax {lift} below 75 % of cap")
            if place is not None and place > PLACE_FMAX_BAND:
                # DEVIATION A1: reported, not gated - see PREREG §9.
                band_hits.append((run.arm, run.seed, place))
            phys = run.manifest().get("physics", {})
            sites = (phys.get("finger_cap_scope") or {}).get("sites")
            if sites != {"left:grasp": run.scope_cap}:
                site_fails.append(f"{run.arm}_{run.seed}: manifest sites {sites} "
                                  f"!= left:grasp")
            if not (phys.get("finger_drive") or {}).get("readback_matches"):
                site_fails.append(f"{run.arm}_{run.seed}: manifest readback_matches false")
        elif run.scope_rows:
            site_fails.append(f"C_{run.seed}: the control printed scope rows")
        if len([e for e in run.episodes if e["outcome"]["ticks"]]) != 15:
            fails.append(f"{run.arm}_{run.seed}: not 15 episodes")
        if not run.legs:
            fails.append(f"{run.arm}_{run.seed}: no [carry] rows parsed")

    print(f"\n  the registered per-cell band clause (place* fmax <= {PLACE_FMAX_BAND:.2f} N,"
          f" DEVIATION A1: reported, not gated):")
    for arm, seed, value in band_hits:
        print(f"    {arm}_{seed}: place* fmax median {value:.2f} N - over the band; the"
              f" leg rows and the pooled column below are the read")
    if not band_hits:
        print("    no cell over the band")

    print("\n  delivered force by leg class, pooled over the cells of an arm (medians):")
    print(f"  {'arm':<6}{'L lift fmax':<13}{'L lift fmin':<13}"
          f"{'L place fmax':<14}{'L place fmin':<14}{'R lift fmax':<13}")
    for arm in arms:
        rs = [r for r in runs if r.arm == arm]
        if not rs:
            continue
        legs = lambda side, cls: [l for r in rs for l in r.legs_of(side, cls)]  # noqa: E731
        print(f"  {arm:<6}"
              f"{_f(median(_positive(legs('left', 'grasp'), 'fmax')), '8.2f'):<13}"
              f"{_f(median(_positive(legs('left', 'grasp'), 'fmin')), '8.2f'):<13}"
              f"{_f(median(_positive(legs('left', 'place'), 'fmax')), '8.2f'):<14}"
              f"{_f(median(_positive(legs('left', 'place'), 'fmin')), '8.2f'):<14}"
              f"{_f(median(_positive(legs('right', 'grasp'), 'fmax')), '8.2f'):<13}")

    # ------------------------------------------------------------------ 1
    print("\n## 1. The leg census (PREREG §5)")
    print(f"  escape = clean_slip_max > {ESCAPE_MM:.0f} mm with a pinch; "
          f"pried = sep_max >= {AT_STOP_MM:.0f} mm of the {OPEN_STOP_MM:.1f} mm stop;")
    print("  never-held = fmax == 0 on that carry leg")
    print(f"  {'arm':<5}{'seed':<6}{'side':<7}{'legs':<6}{'escape':<8}{'>800':<6}"
          f"{'pried':<7}{'never':<7}{'sep_max max':<13}")
    for run in runs:
        for side in ("left", "right"):
            legs = run.legs_of(side, "*")
            print(f"  {run.arm:<5}{run.seed:<6}{side:<7}{len(legs):<6}"
                  f"{sum(1 for l in legs if l.escape):<8}"
                  f"{sum(1 for l in legs if l.strict_escape):<6}"
                  f"{sum(1 for l in legs if l.at_stop):<7}"
                  f"{sum(1 for l in legs if l.never_held):<7}"
                  f"{_f(max((l.sep_max or 0) for l in legs) if legs else None, '6.1f'):<13}")

    print("\n  --- pooled per arm")
    pooled_legs: dict[tuple, dict] = {}
    for run in runs:
        for side in ("left", "right"):
            for cls in ("grasp", "place"):
                legs = run.legs_of(side, cls)
                a = pooled_legs.setdefault((run.arm, side, cls),
                                           {"legs": 0, "esc": 0, "pried": 0,
                                            "never": 0, "face": 0})
                a["legs"] += len(legs)
                a["esc"] += sum(1 for l in legs if l.escape)
                a["pried"] += sum(1 for l in legs if l.at_stop)
                a["never"] += sum(1 for l in legs if l.never_held)
                a["face"] += sum(1 for l in legs if l.lost_a_face)
    print(f"  {'arm':<6}{'side':<7}{'class':<8}{'legs':<6}{'esc':<5}{'pried':<7}"
          f"{'never':<7}{'lost-a-face':<13}")
    for arm in arms:
        for side in ("left", "right"):
            for cls in ("grasp", "place"):
                a = pooled_legs.get((arm, side, cls))
                if not a:
                    continue
                print(f"  {arm:<6}{side:<7}{cls:<8}{a['legs']:<6}{a['esc']:<5}"
                      f"{a['pried']:<7}{a['never']:<7}{a['face']:<13}")

    # ------------------------------------------------------------------ 2
    print("\n## 2. The counts, per cell - a REPORT, not a rate (PREREG §7)")
    print(f"  {'arm':<5}{'seed':<6}{'n':<4}{'placed':<8}{'left':<8}{'right':<8}"
          f"{'cnp':<6}{'never':<7}{'ticks/att':<11}{'arm mix L/R':<12}")
    for run in runs:
        ticks, n = run.cells()
        n_l, n_r = len(run.side("left")), len(run.side("right"))
        print(f"  {run.arm:<5}{run.seed:<6}{len(run.episodes):<4}{run.placed:<8}"
              f"{_ratio(run.side_placed('left'), n_l):<8}"
              f"{_ratio(run.side_placed('right'), n_r):<8}"
              f"{run.side_cnp('left'):<6}{run.side_never('left'):<7}"
              f"{(ticks / n if n else 0):<11.0f}{f'{n_l}/{n_r}':<12}")

    # ------------------------------------------------------------------ 3
    print("\n## 3. The pooled primary - left placed (PREREG §6 P1)")
    pool: dict[str, dict] = {}
    for arm in arms:
        rs = [r for r in runs if r.arm == arm]
        if not rs:
            continue
        pool[arm] = {
            "placed": sum(r.side_placed("left") for r in rs),
            "n": sum(len(r.side("left")) for r in rs),
            "cnp": sum(r.side_cnp("left") for r in rs),
            "never": sum(r.side_never("left") for r in rs),
            "rplaced": sum(r.side_placed("right") for r in rs),
            "rn": sum(len(r.side("right")) for r in rs),
        }
    c = pool.get("C")
    print(f"  {'arm':<6}{'left placed':<15}{'rate':<8}{'cnp':<6}{'never':<7}"
          f"{'right placed':<15}{'p vs C':<10}")
    for arm in arms:
        p = pool[arm]
        pv = "-"
        if c and arm != "C":
            pv = _p(fisher_exact(p["placed"], p["n"] - p["placed"],
                                 c["placed"], c["n"] - c["placed"]))
        rate = p["placed"] / p["n"] if p["n"] else 0.0
        print(f"  {arm:<6}{_ratio(p['placed'], p['n']):<15}{rate:<8.3f}"
              f"{p['cnp']:<6}{p['never']:<7}"
              f"{_ratio(p['rplaced'], p['rn']):<15}{pv:<10}")
    print("\n  the records this phase is read against (not re-run, PREREG §3):")
    for name, rec in RECORDS.items():
        left, n = rec["left"]
        print(f"    {name:<22} left {left}/{n} = {left / n:.3f}  "
              f"never-held {rec['never']}  cnp {rec['cnp']}  "
              f"right {_ratio(*rec['right'])}  pries {rec['pries']}")
    print("\n  per seed (P1b: G >= C on >= 2 of 3, at least one strict):")
    print(f"  {'seed':<8}" + "".join(f"{a:<10}" for a in arms))
    for seed in seeds:
        row = f"  {seed:<8}"
        for arm in arms:
            rs = [r for r in runs if r.arm == arm and r.seed == seed]
            row += (f"{_ratio(rs[0].side_placed('left'), len(rs[0].side('left'))):<10}"
                    if rs else f"{'-':<10}")
        print(row)

    # ------------------------------------------------------------------ 4
    print("\n## 4. The lift leg's own state (E4, H-pick-b)")
    print(f"  {'arm':<6}{'L legs':<8}{'lost-a-face':<13}{'sep_end-gap p50':<18}"
          f"{'fmin p50':<10}{'fmax p50':<10}")
    for arm in arms:
        rs = [r for r in runs if r.arm == arm]
        if not rs:
            continue
        legs = [l for r in rs for l in r.legs_of("left", "grasp")]
        dm = [l.end_minus_start for l in legs if l.end_minus_start is not None]
        print(f"  {arm:<6}{len(legs):<8}{sum(1 for l in legs if l.lost_a_face):<13}"
              f"{_f(median(dm), '8.1f'):<18}"
              f"{_f(median(_positive(legs, 'fmin')), '8.2f'):<10}"
              f"{_f(median(_positive(legs, 'fmax')), '8.2f'):<10}")

    # ------------------------------------------------------------------ 5
    print("\n## 5. The place guard (E5) - the cap must not be reachable there")
    print(f"  {'arm':<6}{'L place legs':<14}{'escapes':<9}{'pried':<7}"
          f"{'place fmax p50':<16}{'place fmin p50':<16}")
    for arm in arms:
        rs = [r for r in runs if r.arm == arm]
        if not rs:
            continue
        legs = [l for r in rs for l in r.legs_of("left", "place")]
        print(f"  {arm:<6}{len(legs):<14}{sum(1 for l in legs if l.escape):<9}"
              f"{sum(1 for l in legs if l.at_stop):<7}"
              f"{_f(median(_positive(legs, 'fmax')), '8.2f'):<16}"
              f"{_f(median(_positive(legs, 'fmin')), '8.2f'):<16}")

    # ------------------------------------------------------------------ 6
    print("\n## 6. The strawberry (E8) - the bruise-critical class")
    small_legs = [l for r in runs for l in r.legs
                  if l.episode["species"] == "strawberry"]
    if small_legs:
        print(f"  {'arm':<5}{'seed':<6}{'side':<6}{'leg':<11}{'dia':<7}{'fmax':<8}"
              f"{'fmin':<8}{'sep_max-dia':<13}{'slip':<9}{'placed':<8}")
        for run in runs:
            for leg in run.legs_of("*", "*"):
                if leg.episode["species"] != "strawberry":
                    continue
                beyond = ((leg.sep_max - leg.dia)
                          if (leg.sep_max is not None and leg.dia is not None) else None)
                print(f"  {run.arm:<5}{run.seed:<6}{leg.side:<6}{leg.name:<11}"
                      f"{_f(leg.dia, '5.1f'):<7}{_f(leg.fmax, '6.2f'):<8}"
                      f"{_f(leg.fmin, '6.2f'):<8}{_f(beyond, '>7.1f'):<13}"
                      f"{leg.slip:<9.1f}"
                      f"{'yes' if leg.episode['outcome']['placed'] else 'no':<8}")
    crush = [l for r in runs for l in r.legs if l.crush_c1]
    crush2 = [l for r in runs for l in r.legs
              if l.crush_c2(l.episode["dia"] is not None and l.episode["dia"] <= 3.9)]
    print(f"\n  crush guards: C1 (sep@loss - dia <= -{CRUSH_INTERFERENCE_MM:.0f} mm): "
          f"{len(crush)} leg(s); C2 (escape + fmin >= {CRUSH_FORCE_N:.0f} N on a "
          f"<= 3.9 cm fruit): {len(crush2)} leg(s)")
    for leg in crush + crush2:
        print(leg.row())

    # ------------------------------------------------------------------ 7
    print("\n## 7. The ledger (E9), the right arm (E6) and the cycle (E7)")
    for arm in arms:
        rs = [r for r in runs if r.arm == arm]
        if not rs:
            continue
        print(f"\n  --- {arm}")
        for run in rs:
            bad = [e for e in run.episodes if not e["outcome"]["placed"]]
            if not bad:
                print(f"    seed {run.seed}: every episode placed")
                continue
            keys: dict[str, int] = {}
            for e in bad:
                for note in re.findall(r"'([^']*)'", e["outcome"]["notes"]):
                    k = note_key(note)
                    keys[k] = keys.get(k, 0) + 1
            print(f"    seed {run.seed}: " + "; ".join(
                f"{k} x{v}" for k, v in sorted(keys.items(), key=lambda kv: -kv[1])))
    print(f"\n  {'arm':<6}{'right placed':<15}{'right cnp':<12}{'right esc':<11}"
          f"{'s/att':<8}{'ticks/att':<11}")
    for arm in arms:
        rs = [r for r in runs if r.arm == arm]
        if not rs:
            continue
        p = pool[arm]
        ticks = sum(r.cells()[0] for r in rs)
        n = sum(r.cells()[1] for r in rs)
        esc = sum(1 for r in rs for l in r.legs_of("right", "*") if l.escape)
        print(f"  {arm:<6}{_ratio(p['rplaced'], p['rn']):<15}"
              f"{sum(r.side_cnp('right') for r in rs):<12}{esc:<11}"
              f"{(ticks / 120.0 / n if n else 0):<8.1f}{ticks / n if n else 0:<11.0f}")

    # ------------------------------------------------------------------ 8
    print("\n## 8. The decision rule (PREREG §6) - pre-registered, evaluated")
    g60, g30 = pool.get("G60"), pool.get("G30")
    if not (c and g60):
        print("  (needs C and G60)")
    else:
        p1a = g60["placed"] >= c["placed"] + P1_GAIN
        per_seed = []
        for seed in seeds:
            rc = [r for r in runs if r.arm == "C" and r.seed == seed]
            rg = [r for r in runs if r.arm == "G60" and r.seed == seed]
            if rc and rg:
                per_seed.append(rg[0].side_placed("left") - rc[0].side_placed("left"))
        p1b = (sum(1 for d in per_seed if d >= 0) >= 2
               and sum(1 for d in per_seed if d > 0) >= 1)
        rate60 = g60["placed"] / g60["n"] if g60["n"] else 0.0
        p1c = rate60 >= P1_RATE
        print(f"  P1a  left placed(G60) {g60['placed']} >= C {c['placed']} + {P1_GAIN}"
              f"  -> {'PASS' if p1a else 'FAIL'}")
        print(f"  P1b  per-seed deltas {per_seed} (>= 0 on 2/3, >= 1 strict)"
              f"  -> {'PASS' if p1b else 'FAIL'}")
        print(f"  P1c  rate(G60) {rate60:.3f} >= {P1_RATE}"
              f"  -> {'PASS' if p1c else 'FAIL'}")
        p1 = p1a and p1b and p1c
        lift_c = [l for r in runs if r.arm == "C" for l in r.legs_of("left", "grasp")]
        lift_g = [l for r in runs if r.arm == "G60" for l in r.legs_of("left", "grasp")]
        legs_c = [l for r in runs if r.arm == "C" for l in r.legs_of("left", "place")]
        legs_g30 = [l for r in runs if r.arm == "G30" for l in r.legs_of("left", "place")]
        face_c = sum(1 for l in lift_c if l.lost_a_face)
        face_g = sum(1 for l in lift_g if l.lost_a_face)
        dm_c = median([l.end_minus_start for l in lift_c
                       if l.end_minus_start is not None]) or 0.0
        dm_g = median([l.end_minus_start for l in lift_g
                       if l.end_minus_start is not None]) or 0.0
        e4 = face_g < face_c or dm_g < dm_c
        p2a = g60["never"] < c["never"]
        p2b = (g60["cnp"] < c["cnp"]) and e4
        p2a_txt = ("NOT EVALUABLE (control reads 0)" if c["never"] == 0
                   else ("PASS" if p2a else "FAIL"))
        print(f"  P2a  never-held(G60) {g60['never']} < C {c['never']}"
              f"  -> {p2a_txt}")
        print(f"  P2b  cnp(G60) {g60['cnp']} < C {c['cnp']} AND E4 improves "
              f"(lost-a-face {face_g} vs {face_c}, sep_end-gap p50 {dm_g:.1f} vs "
              f"{dm_c:.1f})  -> {'PASS' if p2b else 'FAIL'}")
        place_c = median(_positive([l for r in runs if r.arm == "C"
                                    for l in r.legs_of("left", "place")], "fmax"))
        place_g = median(_positive([l for r in runs if r.arm == "G60"
                                    for l in r.legs_of("left", "place")], "fmax"))
        pool_ok = (place_c is not None and place_g is not None
                   and place_g <= place_c * 1.05)
        p3 = (not site_fails) and pool_ok
        print(f"  P3   the site proof: 0 place-leg / right-arm raise rows in "
              f"{sum(1 for r in runs if r.armed)} armed cells"
              f"{'' if not site_fails else ' - VIOLATED'}, pooled place* fmax "
              f"{_f(place_g, '6.2f')} vs C {_f(place_c, '6.2f')}  -> "
              f"{'PASS' if p3 else 'FAIL'}")
        if band_hits:
            print(f"       (DEVIATION A1: {len(band_hits)} cell(s) over the registered "
                  f"{PLACE_FMAX_BAND:.2f} N per-cell band - a peak transient, not a "
                  f"re-clamp: the escaping leg reads fmax 12.13 N at the shipped cap)")
        p4 = g60["rplaced"] >= c["rplaced"] - RIGHT_MARGIN
        print(f"  P4   right placed(G60) {g60['rplaced']} >= C {c['rplaced']} - "
              f"{RIGHT_MARGIN}  -> {'PASS' if p4 else 'FAIL'}")
        p5 = not crush and not crush2
        print(f"  P5   crush guards clean  -> {'PASS' if p5 else 'FAIL'}")
        tc = sum(r.cells()[0] for r in runs if r.arm == "C")
        nc = sum(r.cells()[1] for r in runs if r.arm == "C")
        tg = sum(r.cells()[0] for r in runs if r.arm == "G60")
        ng = sum(r.cells()[1] for r in runs if r.arm == "G60")
        p6 = (tg / ng if ng else 0) <= CYCLE_MARGIN * (tc / nc if nc else 0)
        print(f"  P6   ticks/attempt(G60) {tg / ng if ng else 0:.0f} <= "
              f"{CYCLE_MARGIN:.2f} x C {tc / nc if nc else 0:.0f}  -> "
              f"{'PASS' if p6 else 'FAIL'}")
        if not p5:
            verdict = "DOSE-INADMISSIBLE"
        elif p1 and (p2a or p2b) and p3 and p4:
            verdict = "PICK-ACQUISITION" if p2a else "PICK-LIFT-STATE"
        elif p1:
            verdict = "COUNT-UNATTRIBUTED"
        else:
            verdict = "NO-PICK (F1 fires)" if not (p2a or p2b) else "NO-PICK"
        print(f"\n  VERDICT: {verdict}")
        if g30:
            g30_lift = [l for r in runs if r.arm == "G30"
                        for l in r.legs_of("left", "grasp")]
            print(f"  (G30, a dose not a second primary: left "
                  f"{_ratio(g30['placed'], g30['n'])}, cnp {g30['cnp']} "
                  f"(C {c['cnp']}), never {g30['never']} (C {c['never']}), "
                  f"lost-a-face {sum(1 for l in g30_lift if l.lost_a_face)} "
                  f"(C {face_c}), place escapes "
                  f"{sum(1 for l in legs_g30 if l.escape)} "
                  f"(C {sum(1 for l in legs_c if l.escape)}))")

    # ------------------------------------------------------------------ 9
    print("\n## 9. The blast radius (PREREG §8)")
    b1 = ROOT / "logs/p79/b1_accept_armed.log"
    b2 = ROOT / "logs/p79/b2_twoline_armed.gate"
    if b1.exists():
        lines = [l for l in b1.read_text(encoding="utf-8", errors="replace").splitlines()
                 if "[fruit]" in l]
        ark = [l for l in ARCHIVE_ACCEPT.read_text(encoding="utf-8",
                                                   errors="replace").splitlines()
               if "[fruit]" in l]
        same = lines == ark
        first = next((i for i, (x, y) in enumerate(zip(lines, ark)) if x != y), -1)
        print(f"  B1 scripted acceptance with the scope ARMED: {len(lines)} [fruit] "
              f"lines, md5 {md5_of(lines)}")
        print(f"     archive {ARCHIVE_ACCEPT_LINES} lines, md5 {ARCHIVE_ACCEPT_MD5}")
        print(f"     byte-identical: {'YES' if same else 'NO'}"
              + ("" if same else f" (first diff line {first})"))
        print(f"     -> {'PASS' if same else 'FAIL'}")
        print(f"     scope rows printed on the scripted path: "
              f"{sum(1 for l in lines if 'finger cap scope' in l)} (must be 0)")
    else:
        print("  B1 not run")
    if b2.exists():
        text = b2.read_text(encoding="utf-8", errors="replace")
        print(f"  B2 two-line gate: {'PASS' if 'PASS' in text else 'FAIL'} "
              f"(reference {TWOLINE_REF_MD5})")
    else:
        print("  B2 not run")

    print("\n" + "=" * 78)
    if fails or site_fails:
        print(f"CHECK FAILURES ({len(fails) + len(site_fails)}):")
        for f in fails + site_fails:
            print(f"  - {f}")
    else:
        print("all structural checks PASS")
    print("=" * 78)
    return 1 if (check and (fails or site_fails)) else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arms", default="C,G30,G60")
    ap.add_argument("--seeds", default="77,101,202")
    ap.add_argument("--logdir", default=str(ROOT / "logs/p79/direct"))
    ap.add_argument("--rollouts", default=str(ROOT / "logs/p79/rollouts"))
    ap.add_argument("--check", action="store_true",
                    help="exit 1 on a structural failure (site proof, cells)")
    args = ap.parse_args()
    return report([a for a in args.arms.split(",") if a],
                  [s for s in args.seeds.split(",") if s],
                  args.check, Path(args.logdir), Path(args.rollouts))


if __name__ == "__main__":
    raise SystemExit(main())
