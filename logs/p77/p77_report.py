#!/usr/bin/env python3
"""P77 report: the 60 N clamp at three seeds (a force-ceiling sensitivity).

Reads `logs/p77/direct/<arm>_<seed>.log` for the two arms (`C` = the shipped
10 N, `T` = `FRUIT_FINGER_MAXFORCE=60`) and prints:

* **§0 the manipulation check** - the build print's `maxForce=`/derev, the live
  articulation read-back `[drive]`, and the rollout manifest's `physics` block
  (`finger_maxforce` + `readback_matches`) - a cell whose cap did not reach the
  drive is visibly not evaluable (`PREREG.md` §1);
* **§1 the leg census** - carry legs, escapes (`clean_slip_max > 100 mm`, P74's
  mechanism count), the `> 800 mm` form beside it, legs **pried** to the stop
  (`sep_max >= 95 mm`), never-held legs - per cell and pooled per arm, left and
  right separately;
* **§2 the escape legs**, one row each, and **§2b the pried legs**;
* **§3 the smallest fruit** (the strawberry) in both arms - the class a higher
  clamp would damage first;
* **§4 the delivered pinch** (held-leg `force_min` median) per cell and arm;
* **§5 the counts** per cell (placed, per-arm, cnp / never-held, ticks, arm mix,
  notes) - **a report, not a rate** (`PREREG.md` §3);
* **§6 the pooled primary** - left placed / cnp / never-held, Fisher exact, the
  class-standardised left placed rate, and the `(seed, arm, species, dia)`
  pairing with its unpairable count named;
* **§7 the guards** - the failure ledger by note class, the landing class, and
  the arm mix per seed;
* **§8 the registered decision rule** - M1-M4 (mechanism) and N5-N7 (count),
  evaluated to PASS / FAIL / NOT EVALUABLE;
* **§9 the price** of an adoption - the scripted acceptance at 60 N against
  `logs/p76/accept_noharm_full.log` (346 `[fruit]` lines, md5 `d0079a23`) and
  the two-line at 60 N against `configs/motion_reference_twoline.json`.

`--check` asserts the manipulation check on every arm, that every `[carry]` row
parsed, and that every cell has its 15 episodes - so the printed table cannot
silently drop legs or cells (exit 1).
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

#: The pads' mechanical open stop, read live in `logs/p75/RESULTS.md` §2b.
OPEN_STOP_MM = 98.1
#: PREREG §2.2 / P76 §4.1: "pried to the stop" = within 3.1 mm of it.
AT_STOP_MM = 95.0
#: PREREG §2.2: P74's mechanism count, and the printed-only strict form.
ESCAPE_MM = 100.0
STRICT_ESCAPE_MM = 800.0
#: PREREG §2.2 / P76 §4.2 crush guards.
CRUSH_INTERFERENCE_MM = 15.0
CRUSH_FORCE_N = 35.0
#: PREREG §1: the two arms' nominal per-joint caps.
CAPS = {"C": 10.0, "T": 60.0}
#: PREREG §3 M1/M2: "at most a third as many" as the control.
MECH_FRACTION = 3.0
#: PREREG §3 N6: the right's non-inferiority margin, in attempts.
RIGHT_MARGIN = 1

#: The shipped-cap archive the scripted price run is read against (P76 §8).
ARCHIVE_ACCEPT = ROOT / "logs/p76/accept_noharm_full.log"
ARCHIVE_ACCEPT_LINES = 346
ARCHIVE_ACCEPT_MD5 = "d0079a237202e2f9b0e152655af32a77"

RE_EP_START = re.compile(
    r"\[rl\] episode (\d+): (\w+) grade=(\w) d=([\d.]+)cm bin=(-?\d+) arm=(\w+)"
)
RE_EP_END = re.compile(
    r"\[rl\] episode (\d+): (\w+) d=([\d.]+)cm bin=(-?\d+) arm=(\w+) "
    r"success=(\w+) grasped=(\w+) placed=(\w+) ticks=(\d+).*?notes=(\[.*?\])(?= presentation=)"
)
RE_CARRY = re.compile(r"\[carry\] (\w+) (\w+): ticks=(\d+)/(\d+)")
RE_STAGE_CAP = re.compile(r"maxForce=([\d.]+)/0\.0N \(joint1/joint2")
RE_DRIVE_CAP = re.compile(
    r"\[drive\] (\w+) finger drive maxForce readback joint1/joint2=([\d.]+)/([\d.]+) N"
)
RE_DEREV = re.compile(r"FRUIT_FINGER_MAXFORCE=([\d.]+) N ->")
RE_ANY_NUM = re.compile(r"\d+(?:\.\d+)?")


def num(field: str, key: str) -> float | None:
    m = re.search(rf"\b{re.escape(key)}=(-?[\d.]+)", field)
    return None if m is None else float(m.group(1))


def field_of(line: str, key: str) -> str | None:
    m = re.search(rf"\b{re.escape(key)}=(\S+)", line)
    return None if m is None else m.group(1)


def _f(value, spec: str) -> str:
    """Format a possibly-missing number; `n/a` keeps the requested width."""
    if value is not None:
        return format(value, spec)
    m = re.match(r"([<>]?)(\d+)", spec)
    return f"{'n/a':>{int(m.group(2))}}" if m else "n/a"


def md5_of(lines: list[str]) -> str:
    return hashlib.md5(("\n".join(lines) + "\n").encode()).hexdigest()


# ---- exact statistics (no scipy on this machine) ---------------------------
def _log_comb(n: int, k: int) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher_exact(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact test on the 2x2 table [[a, b], [c, d]].

    Exhaustive over the hypergeometric support and summed on probabilities
    <= the observed one - the same definition P35/P37/P43 quote.
    """
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


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar (binomial) on the discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def sign_test(wins: int, n: int) -> float:
    """One-sided exact sign test (>= `wins` successes out of `n`)."""
    if n == 0:
        return 1.0
    return sum(math.comb(n, i) for i in range(wins, n + 1)) / 2 ** n


# ---- the parsed objects ---------------------------------------------------
class Leg:
    def __init__(self, line: str, episode: dict) -> None:
        head = RE_CARRY.search(line)
        self.side, self.name = head.group(1), head.group(2)
        self.ticks = int(head.group(3))
        self.episode = episode
        self.slip = num(line, "clean_slip_max") or 0.0
        self.sep_onset = num(line, "sep@onset")
        self.sep_loss = num(line, "sep@loss")
        self.sep_end = num(line, "sep_end")
        self.dia = num(line, "dia")
        sep_max = field_of(line, "sep_max") or ""
        m = re.match(r"([\d.]+)@t(\d+)", sep_max)
        self.sep_max = float(m.group(1)) if m else None
        self.sep_max_t = int(m.group(2)) if m else None
        self.gap_at_sep_max = num(line, "gap@sep_max")
        self.sep_min = num(line, "sep_min")
        self.fmax = num(line, "fmax")
        self.fmin = num(line, "force_min")
        self.onset = num(line, "onset_row")
        self.loss = num(line, "loss_row")
        self.contacts_onset = num(line, "contacts@onset")

    @property
    def never_held(self) -> bool:
        """No pinch at any tick (P76 A3): the never-held class, slip not read."""
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
            f"@t{_f(self.sep_max_t, '<4.0f')} gap={_f(self.gap_at_sep_max, '6.1f')}"
            f" sep@loss={_f(self.sep_loss, '>6.1f')} sep_end={_f(self.sep_end, '>6.1f')}"
            f" fmax={_f(self.fmax, '>6.2f')} fmin={_f(self.fmin, '>6.2f')}"
            f"{' STOP' if self.at_stop else ''}"
        )


class Run:
    def __init__(self, arm: str, seed: str, path: Path, rollouts: Path | None = None) -> None:
        self.arm, self.seed, self.path = arm, seed, path
        self.rollouts = rollouts or (ROOT / "logs/p77/rollouts")
        self.lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        self.stage_cap = None
        self.derev_cap = None
        self.drive_caps: dict[str, float] = {}
        for line in self.lines:
            m = RE_STAGE_CAP.search(line)
            if m and self.stage_cap is None:
                self.stage_cap = float(m.group(1))
            m = RE_DEREV.search(line)
            if m and self.derev_cap is None:
                self.derev_cap = float(m.group(1))
            m = RE_DRIVE_CAP.search(line)
            if m:
                self.drive_caps[m.group(1)] = float(m.group(2))

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
                e["outcome"] = {
                    "success": False, "grasped": False, "placed": False,
                    "ticks": 0, "notes": "['no outcome row']",
                }

    # ---- the manifest's physics block (the second manipulation check) ---
    def manifest(self) -> dict:
        base = self.rollouts / f"{self.arm}_{self.seed}"
        paths = sorted(base.glob("*/manifest.json"))
        if not paths:
            return {}
        return json.loads(paths[0].read_text(encoding="utf-8"))

    def cap_ok(self) -> bool:
        want = CAPS[self.arm]
        if self.arm == "C":
            return (self.stage_cap == want and self.derev_cap is None
                    and not self.drive_caps)
        return (self.stage_cap == want and self.derev_cap == want
                and len(self.drive_caps) >= 2
                and all(abs(v - want) < 1e-6 for v in self.drive_caps.values()))

    @property
    def placed(self) -> list[dict]:
        return [e for e in self.episodes if e["outcome"]["placed"]]

    @property
    def attempts(self) -> list[dict]:
        return self.episodes

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

    def held_force_median(self) -> float | None:
        vals = [leg.fmin for leg in self.legs
                if leg.fmin is not None and not leg.escape and leg.fmin > 0]
        return statistics.median(vals) if vals else None

    def notes_of(self, placed: bool) -> list[str]:
        return [e["outcome"]["notes"] for e in self.episodes
                if e["outcome"]["placed"] is placed]


def note_key(note: str) -> str:
    """Group a free-text note by its words with the digits removed (P37's rule)."""
    m = re.search(r"'(.*)'", note)
    text = m.group(1) if m else note.strip("[]")
    return RE_ANY_NUM.sub("#", text)[:80]


def report(arms: list[str], seeds: list[str], check: bool,
           logdir: Path | None = None, rollouts: Path | None = None) -> int:
    logdir = logdir or (ROOT / "logs/p77/direct")
    rollouts = rollouts or (ROOT / "logs/p77/rollouts")
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

    print("=" * 112)
    print("P77 - the 60 N clamp at three seeds (a force-ceiling sensitivity)")
    print("PREREG d31c3e4a; C = shipped 10 N (unset), T = FRUIT_FINGER_MAXFORCE=60")
    print("=" * 112)

    # ---- 0. manipulation check ---------------------------------------
    print("\n## 0. The manipulation check (PREREG §1): does the cap reach the drive?")
    print(f"  {'arm':<4}{'seed':<6}{'stage print':<13}{'env derev':<11}"
          f"{'live L/R':<18}{'manifest':<30}{'evaluable'}")
    bad = 0
    for run in runs:
        lr = ("/".join(f"{run.drive_caps.get(s, float('nan')):.1f}"
                       for s in ("left", "right"))
              if run.drive_caps else "(shipped, unset)")
        man = run.manifest()
        phys = man.get("physics", {})
        fd = phys.get("finger_drive", {})
        mf = phys.get("finger_maxforce")
        man_str = (f"maxforce={_f(mf, '.0f')} readback="
                   f"{fd.get('readback_matches')}")
        # The unset control's manifest records `finger_maxforce: null` (the
        # intent level was never set); that is the shipped path, not a mismatch.
        mf_ok = (mf is None) if run.arm == "C" else (
            mf is not None and abs(mf - CAPS[run.arm]) < 1e-6)
        ok = run.cap_ok() and (not man or (fd.get("readback_matches") is True and mf_ok))
        bad += 0 if ok else 1
        derev = "(unset)" if run.derev_cap is None else f"{run.derev_cap:.1f}"
        print(f"  {run.arm:<4}{run.seed:<6}{_f(run.stage_cap, '.1f'):<13}"
              f"{derev:<11}{lr:<18}{man_str:<30}{'yes' if ok else 'NO'}")
    print("  C is the unset path: the shipped build string is 10.0 and the [drive]")
    print("  read-back row is absent by construction (P41 made it default-off).")

    # ---- 1. leg census ------------------------------------------------
    print("\n## 1. The leg census (PREREG §2.2)")
    print(f"   escape = clean_slip_max > {ESCAPE_MM:.0f} mm with a pinch;"
          f" pried = sep_max >= {AT_STOP_MM:.0f} mm of the {OPEN_STOP_MM:.1f} mm stop")
    print(f"  {'arm':<4}{'seed':<6}{'side':<6}{'legs':<6}{'escape':<8}{'>800mm':<8}"
          f"{'pried':<7}{'never-held':<12}{'sep_max max':<12}")
    for run in runs:
        for side in ("left", "right"):
            legs = run.legs_on(side)
            esc = [l for l in legs if l.escape]
            print(f"  {run.arm:<4}{run.seed:<6}{side:<6}{len(legs):<6}{len(esc):<8}"
                  f"{sum(1 for l in esc if l.strict_escape):<8}"
                  f"{sum(1 for l in legs if l.at_stop):<7}"
                  f"{sum(1 for l in legs if l.never_held):<12}"
                  f"{_f(max((l.sep_max for l in legs if l.sep_max is not None), default=None), '.1f')}")
    print("\n  --- pooled per arm (the mechanism denominators)")
    print(f"  {'arm':<4}{'side':<6}{'legs':<6}{'escape':<8}{'pried':<7}{'never-held':<12}")
    pooled: dict[tuple[str, str], dict[str, int]] = {}
    for run in runs:
        for side in ("left", "right"):
            agg = pooled.setdefault((run.arm, side),
                                    {"legs": 0, "esc": 0, "pried": 0, "never": 0})
            legs = run.legs_on(side)
            agg["legs"] += len(legs)
            agg["esc"] += sum(1 for l in legs if l.escape)
            agg["pried"] += sum(1 for l in legs if l.at_stop)
            agg["never"] += sum(1 for l in legs if l.never_held)
    for arm in arms:
        for side in ("left", "right"):
            a = pooled.get((arm, side), {"legs": 0, "esc": 0, "pried": 0, "never": 0})
            print(f"  {arm:<4}{side:<6}{a['legs']:<6}{a['esc']:<8}{a['pried']:<7}{a['never']:<12}")

    # ---- 2. escape legs, one row each ---------------------------------
    print("\n## 2. Every escape leg (clean_slip_max > 100 mm, pinched)")
    for run in runs:
        esc = [l for l in run.legs if l.escape]
        print(f"\n  --- {run.arm} (cap {CAPS[run.arm]:.0f} N) seed {run.seed}: "
              f"{len(esc)} escape leg(s)")
        for leg in esc:
            print(leg.row())
        if not esc:
            print("    (none)")
    print("\n## 2b. Every pried leg (sep_max >= 95 mm, escape or not)")
    for run in runs:
        pried = [l for l in run.legs if l.at_stop]
        print(f"\n  --- {run.arm} (cap {CAPS[run.arm]:.0f} N) seed {run.seed}: "
              f"{len(pried)} pried leg(s)")
        for leg in pried:
            print(leg.row())
        if not pried:
            print("    (none)")

    # ---- 3. the smallest fruit ---------------------------------------
    print("\n## 3. The smallest fruits (the class a higher clamp would damage first)")
    print("   every strawberry leg, plus any leg at <= 36 mm - the binding class")
    print(f"  {'arm':<4}{'seed':<6}{'fruit':<12}{'dia':>6}{'sep@loss':>10}"
          f"{'loss-dia':>10}{'sep_max':>9}{'fmax':>8}{'fmin':>8}{'slip':>9}  outcome")
    for run in runs:
        for leg in run.legs:
            if leg.dia is None or not leg.name.startswith("grasp"):
                continue
            if leg.episode["species"] != "strawberry" and leg.dia > 36.0:
                continue
            print(f"  {run.arm:<4}{run.seed:<6}{leg.episode['species']:<12}"
                  f"{leg.dia:>6.1f}{_f(leg.sep_loss, '>10.1f')}"
                  f"{_f(leg.loss_interference, '>+10.1f')}{_f(leg.sep_max, '>9.1f')}"
                  f"{_f(leg.fmax, '>8.2f')}{_f(leg.fmin, '>8.2f')}{leg.slip:>9.1f}"
                  f"  {'placed' if leg.episode['outcome']['placed'] else 'LOST'}"
                  f"{' CRUSH' if (leg.crush_c1 or leg.crush_c2) else ''}")

    # ---- 4. the delivered pinch --------------------------------------
    print("\n## 4. The delivered pinch (held-leg force_min median; P41's law: pinch ~= cap)")
    for run in runs:
        print(f"  {run.arm} seed {run.seed}: {_f(run.held_force_median(), '.2f')} N")
    for arm in arms:
        vals = [r.held_force_median() for r in runs if r.arm == arm]
        vals = [v for v in vals if v is not None]
        print(f"  {arm} pooled median of cell medians: {_f(statistics.median(vals) if vals else None, '.2f')} N")

    # ---- 5. counts per cell ------------------------------------------
    print("\n## 5. The counts, per cell - a REPORT, not a rate (PREREG §3)")
    print(f"  {'arm':<4}{'seed':<6}{'n':<4}{'placed':<8}{'left':<9}{'right':<9}"
          f"{'cnp':<6}{'never':<7}{'ticks/att':<11}{'arm mix L/R'}")
    for run in runs:
        n = len(run.attempts)
        la = len(run.side("left"))
        ra = n - la
        ticks = [e["outcome"]["ticks"] for e in run.attempts if e["outcome"]["ticks"]]
        print(f"  {run.arm:<4}{run.seed:<6}{n:<4}{len(run.placed):<8}"
              f"{run.side_placed('left')}/{la:<7}{run.side_placed('right')}/{ra:<7}"
              f"{run.split()['cnp']:<6}{run.split()['never-held']:<7}"
              f"{statistics.median(ticks) if ticks else 0:<11.0f}{la}/{ra}")

    # ---- 6. the pooled primary ---------------------------------------
    print("\n## 6. The pooled primary (PREREG §2.1) - left placed / cnp / never-held")
    def total(arm: str, fn) -> int:
        return sum(fn(r) for r in runs if r.arm == arm)
    def att(arm: str, side: str = "left") -> int:
        return sum(len(r.side(side)) for r in runs if r.arm == arm)

    left_att_c, left_att_t = att("C"), att("T")
    for side in ("left", "right"):
        c_pl, t_pl = (total("C", lambda r, s=side: r.side_placed(s)),
                      total("T", lambda r, s=side: r.side_placed(s)))
        c_n, t_n = att("C", side), att("T", side)
        c_cnp = total("C", lambda r, s=side: r.side_cnp(s))
        t_cnp = total("T", lambda r, s=side: r.side_cnp(s))
        c_nh = total("C", lambda r, s=side: r.side_never(s))
        t_nh = total("T", lambda r, s=side: r.side_never(s))
        p_pl = fisher_exact(c_pl, c_n - c_pl, t_pl, t_n - t_pl)
        p_cnp = fisher_exact(c_cnp, c_pl, t_cnp, t_pl)
        print(f"  {side}: C placed {c_pl}/{c_n}  cnp {c_cnp}  never-held {c_nh}"
              f"   |   T placed {t_pl}/{t_n}  cnp {t_cnp}  never-held {t_nh}")
        print(f"    Fisher (placed vs not): p = {p_pl:.4g};"
              f" Fisher (cnp vs placed): p = {p_cnp:.4g}")
    print("\n  --- per seed, the left (the run level; N=3, so the minimum one-sided")
    print("      sign-test p is 0.125 and that is stated, not hidden)")
    left_wins = 0
    for seed in seeds:
        rc = next((r for r in runs if r.arm == "C" and r.seed == seed), None)
        rt = next((r for r in runs if r.arm == "T" and r.seed == seed), None)
        if rc is None or rt is None:
            continue
        c, t = rc.side_placed("left"), rt.side_placed("left")
        cn, tn = len(rc.side("left")), len(rt.side("left"))
        cc, tc = rc.side_cnp("left"), rt.side_cnp("left")
        delta = t - c
        left_wins += 1 if delta > 0 else 0
        print(f"    seed {seed}: left placed C {c}/{cn} -> T {t}/{tn} "
              f"(delta {delta:+d}); cnp C {cc} -> T {tc}")
    print(f"    run-level: T's left placed is higher in {left_wins}/3 seed pairs"
          f" (one-sided sign p = {sign_test(left_wins, 3):.3f})")

    print("\n  --- class-standardised left placed rate (T re-weighted to C's species mix)")
    def rates(arm: str) -> dict[str, tuple[int, int]]:
        out: dict[str, list[int]] = {}
        for r in runs:
            if r.arm != arm:
                continue
            for e in r.side("left"):
                rec = out.setdefault(e["species"], [0, 0])
                rec[0] += 1 if e["outcome"]["placed"] else 0
                rec[1] += 1
        return {k: (v[0], v[1]) for k, v in out.items()}
    rc_ = rates("C")
    rt_ = rates("T")
    shared = [k for k in rc_ if k in rt_]
    wsum = sum(rc_[k][1] for k in shared) or 1
    std_c = sum(rc_[k][0] for k in shared) / wsum
    std_t = sum((rt_[k][0] / rt_[k][1]) * rc_[k][1] for k in shared if rt_[k][1]) / wsum
    print(f"    shared classes: {', '.join(sorted(shared))}"
          f" ({wsum} of C's {left_att_c} left attempts)")
    print(f"    C {std_c:.3f} -> T {std_t:.3f} (class-standardised; raw pooled "
          f"{total('C', lambda r: r.side_placed('left'))/max(1,left_att_c):.3f}"
          f" -> {total('T', lambda r: r.side_placed('left'))/max(1,left_att_t):.3f})")
    for k in sorted(set(rc_) | set(rt_)):
        c0, c1 = rc_.get(k, (0, 0))
        t0, t1 = rt_.get(k, (0, 0))
        print(f"      {k:<12} C {c0}/{c1:<3} T {t0}/{t1:<3}")

    print("\n  --- the pairing (seed, arm=left, species, dia to 0.1 cm), greedy 1:1")
    pairs = []
    unpairable = 0
    for seed in seeds:
        rc = next((r for r in runs if r.arm == "C" and r.seed == seed), None)
        rt = next((r for r in runs if r.arm == "T" and r.seed == seed), None)
        if rc is None or rt is None:
            continue
        pool = list(rt.side("left"))
        used = set()
        for e in rc.side("left"):
            key = (e["species"], round(e["dia"], 1))
            hit = next((i for i, o in enumerate(pool)
                        if i not in used and (o["species"], round(o["dia"], 1)) == key),
                       None)
            if hit is None:
                unpairable += 1
                continue
            used.add(hit)
            pairs.append((seed, e, pool[hit]))
    b = sum(1 for _, c, t in pairs
            if c["outcome"]["placed"] and not t["outcome"]["placed"])
    cc = sum(1 for _, c, t in pairs
             if t["outcome"]["placed"] and not c["outcome"]["placed"])
    both = sum(1 for _, c, t in pairs
               if c["outcome"]["placed"] and t["outcome"]["placed"])
    neither = len(pairs) - b - cc - both
    print(f"    paired {len(pairs)} of C's {left_att_c} left attempts;"
          f" unpairable {unpairable} (a fruit the other arm never drew)")
    print(f"    both placed {both}; C-only {b}; T-only {cc}; neither {neither};"
          f" exact McNemar p = {mcnemar_exact(b, cc):.4g}")
    print("    this pairing is CONDITIONED ON A POST-TREATMENT VARIABLE (the fruit")
    print("    presented depends on earlier outcomes): it is a descriptor, not the")
    print("    primary - the mechanism rows (§1/§2) and the run level are the claim.")

    # ---- 7. guards ----------------------------------------------------
    print("\n## 7. The guards (PREREG §2.3)")
    print("\n  --- the class split per arm (the failure ledger's spine; arm x class)")
    for arm in arms:
        print(f"  {arm}:")
        for cls in ("placed", "cnp", "never-held"):
            row = []
            for side in ("left", "right"):
                if cls == "placed":
                    k = sum(r.side_placed(side) for r in runs if r.arm == arm)
                elif cls == "cnp":
                    k = sum(r.side_cnp(side) for r in runs if r.arm == arm)
                else:
                    k = sum(r.side_never(side) for r in runs if r.arm == arm)
                n = sum(len(r.side(side)) for r in runs if r.arm == arm)
                row.append(f"{side} {k}/{n}")
            print(f"    {cls:<11} " + "   ".join(row))

    print("\n  --- the note strings on non-placed episodes (digits normalised out);")
    print("      the `intercept trigger (...)` note is the trigger RECORD, not a reason")
    for arm in arms:
        agg: dict[str, dict[str, int]] = {}
        for r in runs:
            if r.arm != arm:
                continue
            for e in r.attempts:
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
            for e in r.attempts:
                if e["outcome"]["placed"]:
                    continue
                if side is not None and e["arm"] != side:
                    continue
                k = note_key(e["outcome"]["notes"])
                if not k.startswith("intercept trigger"):
                    keys.add(k)
        return keys
    new_reasons = sorted(reason_keys("T") - reason_keys("C"))
    print(f"\n  --- new failure reasons in T (not seen in C): "
          + (", ".join(new_reasons) if new_reasons else "none"))

    print("\n  --- the landing class (the notes that mean the payload went nowhere)")
    keys = ("did not land", "fell off the line", "discharged")
    for arm in arms:
        counts = {k: 0 for k in keys}
        for r in runs:
            if r.arm != arm:
                continue
            for e in r.attempts:
                for k in keys:
                    if k in e["outcome"]["notes"] and not e["outcome"]["placed"]:
                        counts[k] += 1
        print(f"  {arm}: " + ", ".join(f"{k} {v}" for k, v in counts.items()))

    print("\n  --- the arm mix per seed (arm = grade = lane: rl_env.py:2516)")
    for seed in seeds:
        bits = []
        for arm in arms:
            r = next((x for x in runs if x.arm == arm and x.seed == seed), None)
            if r is None:
                continue
            la = len(r.side("left"))
            bits.append(f"{arm} {la}/{len(r.attempts)}")
        print(f"    seed {seed}: " + "  ".join(bits))

    print("\n  --- cycle ticks (median per cell; a cost read, not a rate)")
    for arm in arms:
        vals = []
        for r in runs:
            if r.arm != arm:
                continue
            t = [e["outcome"]["ticks"] for e in r.attempts if e["outcome"]["ticks"]]
            if t:
                vals.append(statistics.median(t))
        print(f"  {arm}: {', '.join(f'{v:.0f}' for v in vals)}"
              f" (median of medians {statistics.median(vals) if vals else 0:.0f})")

    # ---- 8. the decision rule -----------------------------------------
    print("\n## 8. The registered decision rule (PREREG §3)")
    cl_esc = pooled.get(("C", "left"), {}).get("esc", 0)
    tl_esc = pooled.get(("T", "left"), {}).get("esc", 0)
    cl_pr = pooled.get(("C", "left"), {}).get("pried", 0)
    tl_pr = pooled.get(("T", "left"), {}).get("pried", 0)
    crush_t = sum(1 for r in runs if r.arm == "T"
                  for l in r.legs if l.crush_c1 or l.crush_c2)
    m1 = (tl_esc * MECH_FRACTION <= cl_esc) if cl_esc else None
    m2 = (tl_pr * MECH_FRACTION <= cl_pr) if cl_pr else None
    m3 = crush_t == 0
    m4 = cl_esc > 0
    print(f"  M1  T left escapes <= 1/3 C's: C {cl_esc} -> T {tl_esc}"
          f"  -> {'PASS' if m1 else ('FAIL' if m1 is not None else 'NOT EVALUABLE')}")
    print(f"  M2  T left pried   <= 1/3 C's: C {cl_pr} -> T {tl_pr}"
          f"  -> {'PASS' if m2 else ('FAIL' if m2 is not None else 'NOT EVALUABLE')}")
    print(f"  M3  zero crush legs in T: {crush_t} -> {'PASS' if m3 else 'FAIL'}")
    print(f"  M4  C's left escape set non-empty: {cl_esc}"
          f" -> {'PASS' if m4 else 'NOT EVALUABLE'}")
    lp_c = total("C", lambda r: r.side_placed("left"))
    lp_t = total("T", lambda r: r.side_placed("left"))
    lc_c = total("C", lambda r: r.side_cnp("left"))
    lc_t = total("T", lambda r: r.side_cnp("left"))
    rp_c = total("C", lambda r: r.side_placed("right"))
    rp_t = total("T", lambda r: r.side_placed("right"))
    n5 = (lp_t > lp_c and lc_t < lc_c and left_wins >= 2)
    right_new = sorted(reason_keys("T", "right") - reason_keys("C", "right"))
    n6 = (rp_t >= rp_c - RIGHT_MARGIN) and not right_new
    n7 = (std_t - std_c) * (lp_t / max(1, left_att_t) - lp_c / max(1, left_att_c)) > 0
    print(f"  N5  T left placed up ({lp_c} -> {lp_t}) and cnp down ({lc_c} -> {lc_t})"
          f" and run level not against (2/3): {left_wins}/3"
          f"  -> {'PASS' if n5 else 'FAIL'}")
    print(f"  N6  right placed within {RIGHT_MARGIN}: C {rp_c} -> T {rp_t}"
          f" and no new right reason ({', '.join(right_new) if right_new else 'none'})"
          f"  -> {'PASS' if n6 else 'FAIL'}")
    print(f"  N7  class-standardised left placed moves with the raw pooled rate:"
          f" {std_c:.3f} -> {std_t:.3f} -> {'PASS' if n7 else 'FAIL'}")
    mech = bool(m2 and m3 and (m1 if m1 is not None else True))
    print(f"\n  -> MECHANISM: {'CONVERTS' if mech else 'DOES NOT CONVERT'}"
          f" (M1-M4; the pry is the evaluable half)")
    print(f"  -> COUNT:     {'CONVERTS' if (n5 and n6 and n7) else 'DOES NOT CONVERT'}"
          f" (N5-N7)")
    if not m1 and m4:
        print("\n  M1 fails: the payload still leaves at 60 N on the left.")
    if m1 is None:
        print("\n  M1 is not evaluable (the control drew no left escape leg) - only the")
        print("  pry (M2) and the crush guard (M3) carry the mechanism statement.")

    # ---- 9. the price --------------------------------------------------
    print("\n## 9. The price of an adoption (PREREG §4, report only, no re-record)")
    p1 = ROOT / "logs/p77/p1_accept_mf60.log"
    if p1.exists():
        def fruit_only(path: Path) -> list[str]:
            return [l for l in path.read_text(encoding="utf-8", errors="replace").splitlines()
                    if l.startswith("[fruit]")]
        # Print-only rows (the build print and the drive read-back) are provenance,
        # not physics: a cap change must move them, and comparing them would mask
        # the first *physical* difference.
        def physics_only(lines: list[str]) -> list[str]:
            return [l for l in lines if "maxForce=" not in l and "[drive]" not in l]
        lines = fruit_only(p1)
        ref = fruit_only(ARCHIVE_ACCEPT)
        pl, rl = physics_only(lines), physics_only(ref)
        same = 0
        first = None
        for i, (x, y) in enumerate(zip(pl, rl)):
            if x == y:
                same += 1
            elif first is None:
                first = i
        print(f"  P1 scripted accept @60N: {len(lines)} [fruit] lines"
              f" (archive {len(ref)}); md5 {md5_of(lines)}"
              f" (archive {ARCHIVE_ACCEPT_MD5})")
        print(f"     physics lines (prints dropped): {len(pl)} vs {len(rl)};"
              f" identical at the same index: {same}"
              + (f", first difference line {first}" if first is not None else
                 " (every shared prefix line identical)"))
        if first is not None and first < len(pl) and first < len(rl):
            print(f"       A[{first}]: {pl[first][:150]}")
            print(f"       B[{first}]: {rl[first][:150]}")
        # The first *outcome* row that differs is the behavioural read.
        oa = [l for l in lines if "[run] attempt" in l and "grasped=" in l]
        ob = [l for l in ref if "[run] attempt" in l and "grasped=" in l]
        for i, (x, y) in enumerate(zip(oa, ob)):
            if x != y:
                print(f"     first differing OUTCOME row (attempt index {i}):")
                print(f"       A: {x[:150]}")
                print(f"       B: {y[:150]}")
                break
        drv = ROOT / "logs/p77/p1_accept_mf60.driver"
        if drv.exists():
            text = drv.read_text(encoding="utf-8", errors="replace")
            fp = [l.strip() for l in text.splitlines() if "fingerprint:" in l]
            print(f"     fingerprint: {'; '.join(fp) if fp else '(not reported)'}")
            summary = [l for l in lines if "[run] summary" in l]
            print(f"     summary: {'; '.join(l.replace('[fruit] ', '')[:90] for l in summary)}")
    else:
        print("  P1 scripted accept @60N: (not run)")
    p2 = ROOT / "logs/p77/p2_twoline_mf60.log"
    if p2.exists():
        gate = ROOT / "logs/p77/p2_twoline_mf60.gate"
        text = p2.read_text(encoding="utf-8", errors="replace")
        fruit = [l for l in text.splitlines() if l.startswith("[fruit]")]
        print(f"  P2 two-line @60N: {len(fruit)} [fruit] lines"
              f" (reference eb697f23, NOT re-recorded)")
        summary = [l for l in text.splitlines() if "[run] summary" in l]
        print(f"     summary: {'; '.join(l.replace('[fruit] ', '')[:90] for l in summary)}")
        if gate.exists():
            g = gate.read_text(encoding="utf-8", errors="replace").splitlines()
            fp = [l.strip() for l in g if "fingerprint:" in l]
            succ = [l.strip() for l in g if l.strip().startswith("success:")]
            verdict = [l for l in g if l.startswith("190:")]
            print(f"     fingerprint: {'; '.join(fp) if fp else '(not reported)'}")
            print(f"     {succ[0] if succ else '(no success line)'}")
            print(f"     gate: {'; '.join(v[:120] for v in verdict)}")
    else:
        print("  P2 two-line @60N: (not run)")

    # ---- the check -----------------------------------------------------
    if check:
        problems = []
        if bad:
            problems.append(f"{bad} cell(s) with a cap that did not reach the drive")
        for run in runs:
            if len(run.attempts) != 15:
                problems.append(f"{run.arm}_{run.seed}: {len(run.attempts)} episodes, expected 15")
            if not run.legs:
                problems.append(f"{run.arm}_{run.seed}: no [carry] rows parsed")
        if problems:
            print("\nCHECK FAILED:")
            for p in problems:
                print(f"  - {p}")
            return 1
        print(f"\nCHECK OK: every cell's declared cap is the cap the drive read back,")
        print(f"  all {len(runs)} cells carry 15 episodes, and all "
              f"{sum(len(r.legs) for r in runs)} [carry] rows parsed.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="C T")
    ap.add_argument("--seeds", default="77 101 202")
    ap.add_argument("--dir", default=None,
                    help="log directory (default logs/p77/direct); relative to the repo root")
    ap.add_argument("--rollouts", default=None,
                    help="rollout root (default logs/p77/rollouts)")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    def resolve(p: str | None) -> Path | None:
        if p is None:
            return None
        path = Path(p)
        return path if path.is_absolute() else (ROOT / path)
    return report(args.arms.split(), args.seeds.split(), args.check,
                  resolve(args.dir), resolve(args.rollouts))


if __name__ == "__main__":
    sys.exit(main())
