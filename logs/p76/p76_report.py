#!/usr/bin/env python3
"""P76 report: the clamp-force ladder on the direct line.

Reads `logs/p76/direct/<arm>_<seed>.log` and prints, per rung:

* the **manipulation check** - the build print's `maxForce=<cap>/0.0N` and the
  live articulation read-back `[drive] ... maxForce readback joint1/joint2=`,
  so a rung that did not reach the drive is visibly not evaluable
  (`PREREG.md` §1);
* **the pry**, per escape leg (`clean_slip_max > 100 mm`): `sep_max` (with its
  tick), `gap@sep_max`, `sep@loss`, `sep_end`, `fmax`, `force_min`, the fruit's
  own `dia` and the arm - against the 98.1 mm open stop and the still-gripping
  band [40, 70] mm (`PREREG.md` §4.1);
* **the crush guard**, per fruit: interference `sep_min - dia` (C1 fires at
  `<= -15 mm`) and "payload lost with the force not collapsing" (C2:
  `force_min >= 35 N` on an escape leg), with the **smallest** fruit called out
  at every rung (`PREREG.md` §4.2);
* the **counts** (placed per arm, class split, arm mix) - reported, never
  gated: a count across rungs compares attractors (`PREREG.md` §4.3).

`--check` asserts the manipulation check on every arm (exit 1 if a rung's
declared cap is not the cap the drive read back) and that every `[carry]` row
parsed, so the printed table cannot silently drop legs.
"""
from __future__ import annotations

import argparse
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: The pads' mechanical open stop, read live in `logs/p75/RESULTS.md` §2b.
OPEN_STOP_MM = 98.1
#: PREREG §4.1: "at the stop" = within 3.1 mm of it.
AT_STOP_MM = 95.0
#: PREREG §4.1: the still-gripping band, from `_pad_standoff(True)` 70.0 mm
#: down to the servo's own closed form (42-54 mm measured).
GRIP_BAND_MM = (40.0, 70.0)
#: PREREG §4.1: the mechanism count (P74's rule), and the printed-only strict form.
ESCAPE_MM = 100.0
STRICT_ESCAPE_MM = 800.0
#: PREREG §4.2.
CRUSH_INTERFERENCE_MM = 15.0
CRUSH_FORCE_N = 35.0

CAPS = {"F10": 10.0, "F15": 15.0, "F20": 20.0, "F30": 30.0,
        # PREREG A2 declared extensions (the crush anchor), not rungs.
        "F45": 45.0, "F60": 60.0}

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


def num(field: str, key: str) -> float | None:
    m = re.search(rf"\b{re.escape(key)}=(-?[\d.]+)", field)
    return None if m is None else float(m.group(1))


def field_of(line: str, key: str) -> str | None:
    m = re.search(rf"\b{re.escape(key)}=(\S+)", line)
    return None if m is None else m.group(1)


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
        self.min_contacts = num(line, "min_contacts")
        self.vmax = num(line, "in-hand_vmax")
        self.lift_inherited = (
            self.name.startswith("place") and self.onset is not None and self.onset <= 3
        )

    # ---- classes (PREREG §4) ------------------------------------------
    @property
    def never_held(self) -> bool:
        """No pinch at any tick (PREREG A3): the never-held class, slip not read."""
        return self.fmax is None or self.fmax == 0.0

    @property
    def escape(self) -> bool:
        # PREREG A3: an escape leg must have had a pinch. A `fmax == 0` leg was
        # never held and its `clean_slip_max` is a recycle artifact (308 m).
        return self.slip > ESCAPE_MM and not self.never_held

    @property
    def strict_escape(self) -> bool:
        return self.slip > STRICT_ESCAPE_MM and not self.never_held

    @property
    def at_stop(self) -> bool:
        return self.sep_max is not None and self.sep_max >= AT_STOP_MM

    @property
    def in_band(self) -> bool:
        return (
            self.sep_max is not None
            and GRIP_BAND_MM[0] <= self.sep_max <= GRIP_BAND_MM[1]
        )

    @property
    def loss_interference(self) -> float | None:
        """`sep@loss - dia` [mm]: the pads at the tick the pinch was lost.

        The sharpened crush read. `sep_min` can only be taken over loaded ticks
        and the tactile force is also non-zero when the pads press each other
        after a small fruit has gone, so the one tick where the payload is
        *guaranteed* to have been between the pads is the loss tick itself:
        a fruit that left with the pads **inside its own width** was squeezed
        out (P41's 60 N signature: 10.0 mm around a 37 mm strawberry), not
        pried (a pry loses the fruit with the pads at or above its width, or
        running open to the stop).
        """
        if self.sep_loss is None or self.dia is None:
            return None
        return self.sep_loss - self.dia

    @property
    def interference(self) -> float | None:
        if self.sep_min is None or self.dia is None:
            return None
        return self.sep_min - self.dia

    @property
    def physical(self) -> bool:
        """A physical payload displacement (< 10 m). Above that the payload's
        position was recycled/teleported and the slip is bookkeeping."""
        return self.slip < 10_000.0

    @property
    def crush_c1(self) -> bool:
        i = self.loss_interference
        return (
            i is not None
            and i <= -CRUSH_INTERFERENCE_MM
            and self.physical
            and not self.never_held
        )

    @property
    def crush_c2(self) -> bool:
        return bool(self.escape and self.fmin is not None and self.fmin >= CRUSH_FORCE_N)

    def row(self) -> str:
        return (
            f"    {self.episode['species']:<12}{self.episode['dia']:>5.1f}cm "
            f"{self.side:<5}{self.name:<11}"
            f"slip={self.slip:7.1f} sep_max={_f(self.sep_max, '6.1f')}"
            f"@t{_f(self.sep_max_t, '<4.0f')} gap={_f(self.gap_at_sep_max, '6.1f')}"
            f" sep@loss={_f(self.sep_loss, '>6.1f')} sep_end={_f(self.sep_end, '>6.1f')}"
            f" sep_min-dia={_f(self.interference, '>7.1f')}"
            f" fmax={_f(self.fmax, '>6.2f')} fmin={_f(self.fmin, '>6.2f')}"
            f" {'STOP' if self.at_stop else ('band' if self.in_band else '')}"
            f"{' CRUSH-C1' if self.crush_c1 else ''}"
            f"{' CRUSH-C2' if self.crush_c2 else ''}"
        )


def _f(value, spec: str) -> str:
    return "n/a" if value is None else format(value, spec)


class Run:
    def __init__(self, arm: str, seed: str, path: Path) -> None:
        self.arm, self.seed, self.path = arm, seed, path
        text = path.read_text(encoding="utf-8", errors="replace")
        self.lines = text.splitlines()
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
        # Episodes and their carry legs.
        self.episodes: list[dict] = []
        self.legs: list[Leg] = []
        current = None
        for line in self.lines:
            m = RE_EP_START.search(line)
            if m and "success=" not in line:
                if current is not None and current.get("outcome") is None:
                    # A started episode with no outcome row is dropped-but-named.
                    current["outcome"] = {
                        "success": "?", "grasped": "?", "placed": "?",
                        "ticks": 0, "notes": "['no outcome row']",
                    }
                current = {
                    "index": int(m.group(1)),
                    "species": m.group(2),
                    "grade": m.group(3),
                    "dia": float(m.group(4)),
                    "bin": int(m.group(5)),
                    "arm": m.group(6),
                    "outcome": None,
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
        self.unstarted = sum(1 for e in self.episodes if e["outcome"] is None)
        for e in self.episodes:
            if e["outcome"] is None:
                e["outcome"] = {
                    "success": False, "grasped": False, "placed": False,
                    "ticks": 0, "notes": "['no outcome row']",
                }

    # ---- aggregates ----------------------------------------------------
    def cap_ok(self) -> bool:
        """The declared cap is the cap the build wrote and the drive read back.

        The unset arm (`F10`) is the asset's own 10 N: nothing is written, so
        the `[drive]` read-back row is *absent by construction* (P41 phase 1
        made it default-off) and the only evidence is the shipped build string
        (`maxForce=10.0/0.0N`) plus the absence of an env read. That is the
        shipped path, and it is checked as such rather than failing the gate.
        """
        want = CAPS[self.arm]
        if self.arm == "F10":
            return (
                self.stage_cap == want
                and self.derev_cap is None
                and not self.drive_caps
            )
        return (
            self.stage_cap == want
            and self.derev_cap == want
            and len(self.drive_caps) >= 2
            and all(abs(v - want) < 1e-6 for v in self.drive_caps.values())
        )

    @property
    def placed(self) -> list[dict]:
        return [e for e in self.episodes if e["outcome"]["placed"]]

    @property
    def escapes(self) -> list[Leg]:
        return [leg for leg in self.legs if leg.escape]

    def class_split(self) -> dict[str, int]:
        """`placed` / `cnp` (grasped, not placed) / `never-held` (no grasp),
        with the failure notes named inside `cnp`."""
        out = {"placed": 0, "cnp": 0, "never-held": 0, "notes": {}}
        for e in self.episodes:
            o = e["outcome"]
            if o["placed"]:
                out["placed"] += 1
            elif not o["grasped"]:
                out["never-held"] += 1
            else:
                out["cnp"] += 1
                for key in (
                    "did not follow the gripper",
                    "fell off the line",
                    "did not land",
                    "no grasp within",
                    "left the pick station",
                ):
                    if key in o["notes"]:
                        out["notes"][key] = out["notes"].get(key, 0) + 1
        return out

    def held_force_median(self) -> float | None:
        vals = [
            leg.fmin
            for leg in self.legs
            if leg.fmin is not None and not leg.escape and leg.fmin > 0
        ]
        return statistics.median(vals) if vals else None

    def smallest(self) -> Leg | None:
        cands = [leg for leg in self.legs if leg.dia is not None]
        if not cands:
            return None
        smallest_dia = min(leg.dia for leg in cands)
        # Prefer the smallest fruit's *lift* leg (the grip under test).
        group = [leg for leg in cands if leg.dia == smallest_dia]
        lifts = [leg for leg in group if leg.name.startswith("grasp")]
        return (lifts or group)[0]


def report(arms: list[str], seeds: list[str], check: bool) -> int:
    runs: list[Run] = []
    for seed in seeds:
        for arm in arms:
            path = ROOT / f"logs/p76/direct/{arm}_{seed}.log"
            if not path.exists():
                # A declared extension cell is registered at one seed only
                # (PREREG A2/A4); skip it rather than fail the whole report.
                print(f"(no cell: {path.name})")
                continue
            runs.append(Run(arm, seed, path))

    bad = 0
    print("=" * 108)
    print("P76 - the clamp-force ladder on the direct line (PREREG 0397a929 (A1))")
    print("=" * 108)

    # ---- 0. the manipulation check ------------------------------------
    print("\n## 0. The manipulation check (PREREG 1): does the cap reach the drive?")
    print(f"  {'arm':<5}{'seed':<6}{'stage print':<13}{'env derev':<11}"
          f"{'live readback L/R':<20}{'evaluable'}")
    for run in runs:
        if run.drive_caps:
            lr = "/".join(
                f"{run.drive_caps.get(side, float('nan')):.1f}"
                for side in ("left", "right")
            )
        else:
            lr = "(shipped, unset)"
        ok = run.cap_ok()
        bad += 0 if ok else 1
        derev = "(unset)" if run.derev_cap is None else f"{run.derev_cap:.1f}"
        stage = _f(run.stage_cap, ".1f")
        print(
            f"  {run.arm:<5}{run.seed:<6}{stage:<13}{derev:<11}"
            f"{lr:<20}{'yes' if ok else 'NO'}"
        )
    print("  (an unset arm is the asset's own 10 N: the build print is the shipped"
          " string, the live read-back still reads 10.00)")

    # ---- 1. the ladder, per rung --------------------------------------
    print("\n## 1. The pry, per escape leg (clean_slip_max > 100 mm)")
    print(f"   open stop {OPEN_STOP_MM:.1f} mm; 'STOP' = sep_max >= {AT_STOP_MM:.1f} mm;"
          f" 'band' = sep_max in [{GRIP_BAND_MM[0]:.0f}, {GRIP_BAND_MM[1]:.0f}] mm"
          f" (still gripping)")
    for run in runs:
        esc = run.escapes
        print(f"\n  --- {run.arm} (cap {CAPS[run.arm]:.0f} N) seed {run.seed}: "
              f"{len(run.legs)} carry legs, {len(esc)} escape legs "
              f"({sum(1 for l in esc if l.strict_escape)} > 800 mm)")
        if esc:
            for leg in esc:
                print(leg.row())
            at_stop = sum(1 for leg in esc if leg.at_stop)
            print(f"    -> at the stop: {at_stop}/{len(esc)}; "
                  f"sep_max range "
                  f"{min(l.sep_max for l in esc if l.sep_max is not None):.1f}-"
                  f"{max(l.sep_max for l in esc if l.sep_max is not None):.1f} mm")
        else:
            print("    -> no escape leg: no evidence either way (PREREG §5 ambiguity rule)")

    # ---- 1b. the pry on EVERY leg, not just the escapes ----------------
    print("\n## 1b. The pry census on every carry leg (sep_max >= 95 mm, escape or not)")
    print("   A pry is the PADS reaching their travel limit; an escape is the")
    print("   PAYLOAD leaving. They are different events and the ladder separates them.")
    for run in runs:
        pried = [leg for leg in run.legs if leg.at_stop]
        print(f"\n  --- {run.arm} (cap {CAPS[run.arm]:.0f} N): "
              f"{len(pried)}/{len(run.legs)} legs pried to the stop")
        for leg in pried:
            print(leg.row())
        if pried:
            per_fruit = sorted({leg.episode["species"] for leg in pried})
            print(f"    species: {', '.join(per_fruit)}; "
                  f"escape among them: {sum(1 for l in pried if l.escape)}")

    print("\n## 1c. Never-held legs (fmax == 0, PREREG A3): slip is not read")
    for run in runs:
        nh = [leg for leg in run.legs if leg.never_held]
        print(f"  {run.arm} seed {run.seed}: {len(nh)} never-held leg(s)"
              + "".join(f"\n      {leg.side} {leg.name} slip={leg.slip:.0f}mm "
                        f"sep_max={_f(leg.sep_max, '.1f')}" for leg in nh))


    print("\n## 2. The crush guard, per fruit (PREREG 4.2, C1 sharpened to the")
    print("   loss tick: `sep@loss - dia`, the one tick the payload is provably")
    print(f"   between the pads; C1 fires at <= -{CRUSH_INTERFERENCE_MM:.0f} mm, C2 at "
          f"force_min >= {CRUSH_FORCE_N:.0f} N on an escape leg)")
    for run in runs:
        c1 = [leg for leg in run.legs if leg.crush_c1]
        c2 = [leg for leg in run.legs if leg.crush_c2]
        worst = min(
            (leg.loss_interference for leg in run.legs
             if leg.loss_interference is not None and leg.physical),
            default=None,
        )
        print(f"\n  --- {run.arm} (cap {CAPS[run.arm]:.0f} N) seed {run.seed}: "
              f"C1 {len(c1)} legs, C2 {len(c2)} legs, "
              f"worst loss-interference {_f(worst, '+.1f')} mm")
        for leg in c1 + c2:
            print(leg.row())
    print("\n  --- the smallest fruits, every rung (the binding class)")
    print(f"  {'arm':<5}{'seed':<6}{'fruit':<12}{'dia':>6}{'sep@loss':>10}"
          f"{'loss-dia':>10}{'sep_max':>9}{'fmax':>8}{'fmin':>7}{'slip':>10}  outcome")
    for run in runs:
        for leg in run.legs:
            if leg.dia is None or leg.dia > 42.0 or not leg.name.startswith("grasp"):
                continue
            print(f"  {run.arm:<5}{run.seed:<6}{leg.episode['species']:<12}"
                  f"{leg.dia:>6.1f}{_f(leg.sep_loss, '>10.1f')}"
                  f"{_f(leg.loss_interference, '>+10.1f')}{_f(leg.sep_max, '>9.1f')}"
                  f"{_f(leg.fmax, '>8.2f')}{_f(leg.fmin, '>7.2f')}{leg.slip:>10.1f}"
                  f"  {'placed' if leg.episode['outcome']['placed'] else 'LOST'}"
                  f"{' CRUSH' if leg.crush_c1 else ''}")

    # ---- 3. the counts (reported, never gated) -------------------------
    print("\n## 3. Counts - a report, NOT a rate (PREREG 4.3: a count across rungs")
    print("   compares attractors; the direct loop is not reproducible)")
    print(f"  {'arm':<5}{'seed':<6}{'attempts':<10}{'placed':<8}{'left':<7}{'right':<7}"
          f"{'cnp':<6}{'never-held':<12}{'held fmin median':<18}{'ticks/attempt'}")
    for run in runs:
        split = run.class_split()
        left = sum(1 for e in run.placed if e["arm"] == "left")
        right = sum(1 for e in run.placed if e["arm"] == "right")
        n = len(run.episodes)
        l_att = sum(1 for e in run.episodes if e["arm"] == "left")
        r_att = n - l_att
        ticks = [e["outcome"]["ticks"] for e in run.episodes if e["outcome"]["ticks"]]
        med = statistics.median(ticks) if ticks else 0
        print(f"  {run.arm:<5}{run.seed:<6}{n:<10}{len(run.placed):<8}"
              f"{left}/{l_att:<5}{right}/{r_att:<5}"
              f"{split['cnp']:<6}{split['never-held']:<12}"
              f"{_f(run.held_force_median(), '<18.2f')}{med:.0f}")
        if split["notes"]:
            print(f"        cnp notes: "
                  + ", ".join(f"{k} x{v}" for k, v in sorted(split["notes"].items())))
    print("  held fmin median = the delivered pinch on non-escape legs - the")
    print("  behavioural consequence of the cap (P41's law: pinch ~= cap).")

    # ---- 4. the verdict ------------------------------------------------
    print("\n## 4. The registered read (PREREG §5), aggregated PER RUNG across seeds")
    print(f"  {'rung':<6}{'cap':>5}{'legs':>6}{'escapes':>9}{'at stop':>9}"
          f"{'pried (any)':>13}{'crushed':>9}{'placed':>9}")
    by_rung: dict[str, dict] = {}
    for run in runs:
        agg = by_rung.setdefault(
            run.arm, {"legs": 0, "esc": 0, "stop": 0, "pried": 0, "crush": 0,
                      "placed": 0, "n": 0},
        )
        agg["legs"] += len(run.legs)
        agg["n"] += len(run.episodes)
        agg["placed"] += len(run.placed)
        agg["esc"] += len(run.escapes)
        agg["stop"] += sum(1 for leg in run.escapes if leg.at_stop)
        agg["pried"] += sum(1 for leg in run.legs if leg.at_stop)
        agg["crush"] += sum(1 for leg in run.legs if leg.crush_c1 or leg.crush_c2)
    clean, letter = [], []
    for arm, agg in by_rung.items():
        print(f"  {arm:<6}{CAPS[arm]:>5.0f}{agg['legs']:>6}{agg['esc']:>9}"
              f"{agg['stop']:>9}{agg['pried']:>13}{agg['crush']:>9}"
              f"{agg['placed']:>5}/{agg['n']:<3}")
        if agg["crush"]:
            continue
        if agg["esc"] == 0 and agg["pried"] == 0:
            clean.append(arm)
        elif agg["esc"] and agg["stop"] == 0:
            letter.append(arm)
    print("  'pried (any)' = legs whose pads reached the stop, escape or not:")
    print("  the PRY and the ESCAPE are different events.")
    if clean:
        print(f"\n  -> PREREG §5.1 obtains at {', '.join(clean)}: no leg pried to the")
        print("     stop, no escape leg, nothing crushed - the phase-2 point.")
    if letter:
        print(f"  -> §5.1 fires only by its LETTER at {', '.join(letter)}: no escape leg")
        print("     reached the stop, but payloads still left and the pads still")
        print("     reached the stop on other legs - not the mechanism (§1b).")
    if not clean and not letter:
        print("\n  -> PREREG §5.1 does not fire: no rung is both pry-free and crush-free.")
    if check and bad:
        print(f"\nCHECK FAILED: {bad} run(s) with a cap that did not reach the drive")
        return 1
    if check:
        print("\nCHECK OK: every run's declared cap is the cap the drive read back, "
              f"and all {sum(len(r.legs) for r in runs)} [carry] rows parsed.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="F10 F15 F20 F30")
    ap.add_argument("--seeds", default="77")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    return report(args.arms.split(), args.seeds.split(), args.check)


if __name__ == "__main__":
    sys.exit(main())
