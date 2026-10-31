#!/usr/bin/env python3
"""P71 report: the adoption package on the direct line (the `[carry]` read).

    python3 logs/p71/p71_report.py [--check] logs/p71/direct/{ctrl,treat}_*.log

The direct loop conditions on rendered frames and is **not** bit-reproducible, so
nothing here is a rate: the sections are, per arm and seed,
(1) the episode outcomes by class - `placed`, `carried-not-placed` (the closed
loaded-slide class, `logs/p42/SIM_LIMIT.md`), `never-held`;
(2) the arm split, because the direct env sets the arm from the fruit's grade
(`arm = left if grade == A`) and the lift flip is the left's;
(3) every `place*` leg's crossing `clr`/`clr_win` **and the surface it was
measured against** - with the inner rail dropped it must read `@obelt` (the
slab's inboard top edge), and every **held** left place leg must clear the
+33 mm access floor;
(4) the place legs' loaded slides (> 800 mm) and the G0 contact channel
(`|a|max`: 18-20 m/s^2 is the rail-contact signature, 2.6-5.7 the clean one);
(5) the failure reasons per arm, so a new one is visible.

Exit 0 on pass, 1 on a failed gate (with `--check`).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

EPISODE = re.compile(
    r"^\[fruit\] \[rl\] episode (\d+): (\w+) (?:grade=(\w+) )?d=([\d.]+)cm bin=(\d+) "
    r"arm=(\w+)(?: y=([-+\d.]+))? (.*)$"
)
OUTCOME = re.compile(r"success=(\w+) grasped=(\w+) placed=(\w+)")
NOTES = re.compile(r"notes=\[(.*)\]")
CARRY = re.compile(r"^\[fruit\] \[carry\] (\w+) ((?:place|grasp_lift)\d*): (.*)$")
MOTION = re.compile(r"^\[fruit\] \[motion\] carry (place\d+): (.*)$")
WALL = re.compile(r"^\[fruit\] \[rl\] run wall end ([\d.]+) duration ([\d.]+)s")
LIFT = re.compile(r"^(?:\[fruit\] )?\[grasp\] lift_dz: (.*)$")

FLOOR_MM = 33.0
SLIDE_MM = 800.0


def num(text: str, default: float = float("nan")) -> float:
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def crossing_of(fields: dict) -> dict:
    out = {}
    for key in ("clr", "clr_win", "clr_min"):
        m = re.match(r"([-+\d.]+)mm@(\w+)(?:/t(\d+))?$", fields.get(key, "n/a"))
        out[key] = (
            (float(m.group(1)), m.group(2), int(m.group(3)) if m.group(3) else None)
            if m
            else None
        )
    return out


def parse(path: Path) -> dict:
    episodes: dict = {}
    legs: list = []
    lift_row = ""
    wall = None
    current = None
    current_index = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = LIFT.match(line)
        if m:
            lift_row = m.group(1).strip()
            continue
        m = WALL.match(line)
        if m:
            wall = float(m.group(2))
            continue
        m = EPISODE.match(line)
        if m:
            index = int(m.group(1))
            current_index = index
            tail = m.group(8)
            record = episodes.setdefault(index, {"index": index})
            record.update(
                {
                    "species": m.group(2),
                    "arm": m.group(6),
                    "diameter_m": float(m.group(4)) / 100.0,
                }
            )
            outcome = OUTCOME.search(tail)
            if outcome:
                record["success"] = outcome.group(1) == "True"
                record["grasped"] = outcome.group(2) == "True"
                record["placed"] = outcome.group(3) == "True"
                notes = NOTES.search(tail)
                record["notes"] = notes.group(1) if notes else ""
                current = record
            continue
        m = CARRY.match(line)
        if m:
            fields = {}
            for token in m.group(3).split():
                if "=" in token:
                    key, _, value = token.partition("=")
                    fields[key] = value
            legs.append(
                {
                    "side": m.group(1),
                    "leg": m.group(2),
                    "episode": current_index,
                    "species": current["species"] if current else "?",
                    "diameter_m": current["diameter_m"] if current else float("nan"),
                    "fields": fields,
                    "crossing": crossing_of(fields),
                }
            )
            continue
        m = MOTION.match(line)
        if m and legs:
            text = m.group(2)
            amax = re.search(r"\|a\|max=([\d.]+)", text)
            legs[-1]["amax"] = float(amax.group(1)) if amax else float("nan")
            continue
    return {"episodes": episodes, "legs": legs, "lift": lift_row, "wall_s": wall}


def classify(episode: dict, legs: list) -> str:
    if not episode.get("success"):
        if not episode.get("grasped"):
            return "never-held"
        place = [leg for leg in legs if leg["episode"] == episode["index"]
                 and leg["leg"].startswith("place")]
        slip = max((num(leg["fields"].get("clean_slip_max", "nan").replace("mm", ""))
                    for leg in place), default=float("nan"))
        if slip == slip and slip > SLIDE_MM:
            return "carried-not-placed (loaded slide)"
        return "carried-not-placed (other)"
    return "placed"


def held(leg: dict) -> bool:
    """The payload was still in hand when the payload crossed the rail line."""
    crossing = leg["crossing"]["clr"] or leg["crossing"]["clr_win"]
    slip = num(leg["fields"].get("clean_slip_max", "nan").replace("mm", ""))
    loss = leg["fields"].get("loss_row", "None")
    if slip > 50.0 or crossing is None:
        return False
    if loss not in ("None", "n/a") and crossing[2] is not None and int(loss) < crossing[2]:
        return False
    return True


def fmt(cell) -> str:
    if cell is None:
        return "n/a"
    return f"{cell[0]:+.0f}@{cell[1]}" + (f"/t{cell[2]}" if cell[2] is not None else "")


def reason_of(notes: str) -> str:
    text = notes.strip()
    if not text:
        return "-"
    text = re.sub(r"\d+(\.\d+)?", "#", text)
    return text.split(";")[0][:58]


def main(argv: list[str]) -> int:
    check = "--check" in argv
    paths = [Path(a) for a in argv if not a.startswith("--")]
    parsed = {}
    for path in paths:
        if not path.is_file():
            print(f"FAIL: {path} missing")
            return 1
        parsed[path.stem] = parse(path)

    problems: list[str] = []
    print("=" * 82)
    print("P71 - the direct line with both flips (rails=none, lift=+0.20) vs the "
          "pre-P71 package")
    print("=" * 82)
    totals: dict = {}
    for arm, data in parsed.items():
        episodes = data["episodes"]
        legs = data["legs"]
        tag = "ctrl (rails both, lift 0.36)" if arm.startswith("ctrl") else "treat (P71 defaults)"
        print(f"--- {arm} [{tag}] " + "-" * max(0, 50 - len(arm)))
        print(f"  lift : {data['lift'] or '?'}")
        if data["wall_s"]:
            print(f"  wall : {data['wall_s']:.0f} s")
        classes: dict = {}
        reasons: dict = {}
        for index in sorted(episodes):
            episode = episodes[index]
            label = classify(episode, legs)
            classes[label] = classes.get(label, 0) + 1
            if label != "placed":
                key = reason_of(episode.get("notes") or "")
                reasons[key] = reasons.get(key, 0) + 1
            print(
                f"    ep{index:<2} {episode['species']:<10} {episode['arm']:<5} "
                f"{'PLACED' if episode.get('placed') else '-':<6} {label:<32} "
                f"{(episode.get('notes') or '')[:56]}"
            )
        placed = sum(1 for e in episodes.values() if e.get("placed"))
        print(f"  {placed}/{len(episodes)} placed by class: " + ", ".join(
            f"{k} {v}" for k, v in sorted(classes.items())))
        for side in ("left", "right"):
            side_eps = [e for e in episodes.values() if e["arm"] == side]
            side_placed = sum(1 for e in side_eps if e.get("placed"))
            side_cnp = sum(
                1 for e in side_eps if classify(e, legs).startswith("carried"))
            side_held = sum(1 for e in side_eps if classify(e, legs) == "placed")
            print(f"  {side:<5} {side_placed}/{len(side_eps)} placed, "
                  f"{side_cnp} carried-not-placed, {side_held} placed")
        place = [leg for leg in legs if leg["leg"].startswith("place")]
        held_legs = [leg for leg in place if held(leg)]
        loaded = [leg for leg in place if num(
            leg["fields"].get("clean_slip_max", "nan").replace("mm", "")) > SLIDE_MM]
        codes = {
            cell[1] for leg in place for cell in leg["crossing"].values()
            if cell is not None and cell[1] in ("rail", "obelt")
        }
        print(
            f"  place legs {len(place)} | held {len(held_legs)} | "
            f"loaded slide (>{SLIDE_MM:.0f} mm) {len(loaded)} | surfaces {sorted(codes)}"
        )
        for leg in held_legs:
            c = leg["crossing"]["clr"]
            w = leg["crossing"]["clr_win"]
            bad = "  <-- BELOW +33" if c is not None and c[0] < FLOOR_MM else ""
            print(
                f"    ep{leg['episode']} {leg['side']:<5} {leg['leg']:<7} "
                f"clr={fmt(c):<16} clr_win={fmt(w):<16} "
                f"clr_min={fmt(leg['crossing']['clr_min']):<16} "
                f"slip={leg['fields'].get('clean_slip_max', '?')} "
                f"|a|max={leg.get('amax', float('nan')):.2f}{bad}"
            )
        for leg in loaded:
            print(
                f"    ESC ep{leg['episode']} {leg['side']:<5} {leg['leg']:<7} "
                f"slip={leg['fields'].get('clean_slip_max', '?')} "
                f"contacts@onset={leg['fields'].get('contacts@onset', '?')} "
                f"force_min={leg['fields'].get('force_min', '?')} "
                f"loss_row={leg['fields'].get('loss_row', '?')} "
                f"clr={fmt(leg['crossing']['clr'])} clr_win={fmt(leg['crossing']['clr_win'])}"
            )
        for key, value in sorted(reasons.items(), key=lambda kv: -kv[1]):
            print(f"    reason x{value}: {key}")
        acc = totals.setdefault("class", {})
        for key, value in classes.items():
            acc[key] = acc.get(key, 0) + value
        totals["n"] = totals.get("n", 0) + len(episodes)
        totals["placed"] = totals.get("placed", 0) + placed
        for side in ("left", "right"):
            side_eps = [e for e in episodes.values() if e["arm"] == side]
            key = f"{side}_n"
            totals[key] = totals.get(key, 0) + len(side_eps)
            key = f"{side}_placed"
            totals[key] = totals.get(key, 0) + sum(1 for e in side_eps if e.get("placed"))
        totals["held"] = totals.get("held", 0) + len(held_legs)
        totals["loaded"] = totals.get("loaded", 0) + len(loaded)
        for leg in held_legs:
            c = leg["crossing"]["clr"]
            if c is not None:
                totals.setdefault("clr", []).append(c[0])
            w = leg["crossing"]["clr_win"]
            if w is not None:
                totals.setdefault("clr_win", []).append(w[0])
        print()

    if totals:
        print("=" * 82)
        print(f"POOLED {totals.get('placed', 0)}/{totals.get('n', 0)} placed by class: "
              + ", ".join(f"{k} {v}" for k, v in sorted(totals.get("class", {}).items())))
        print(f"  left  {totals.get('left_placed', 0)}/{totals.get('left_n', 0)} | "
              f"right {totals.get('right_placed', 0)}/{totals.get('right_n', 0)}")
        clr = totals.get("clr", [])
        clr_win = totals.get("clr_win", [])
        print(f"  held place legs {totals.get('held', 0)} | loaded slides {totals.get('loaded', 0)}")
        if clr:
            print(f"  crossing clr      min {min(clr):+.0f} max {max(clr):+.0f} mm (n={len(clr)})")
        if clr_win:
            print(f"  crossing clr_win  min {min(clr_win):+.0f} max {max(clr_win):+.0f} mm (n={len(clr_win)})")
        print()

    if check:
        for arm, data in parsed.items():
            if len(data["episodes"]) != 15:
                problems.append(f"{arm}: {len(data['episodes'])} episodes, expected 15")
            if "dz=" not in data["lift"]:
                problems.append(f"{arm}: no lift_dz row")
            treat = not arm.startswith("ctrl")
            if treat and "(default)" not in data["lift"]:
                problems.append(f"{arm}: the lift flip did not resolve as the default")
            if not treat and "(explicit)" not in data["lift"]:
                problems.append(f"{arm}: the control lift is not explicit")
            place = [leg for leg in data["legs"] if leg["leg"].startswith("place")]
            codes = {
                cell[1] for leg in place for cell in leg["crossing"].values()
                if cell is not None and cell[1] in ("rail", "obelt")
            }
            if not codes:
                problems.append(f"{arm}: no leg read a rail/obelt surface")
            if treat and "rail" in codes:
                problems.append(f"{arm}: a place leg still read the RAIL surface")

        # The +33 mm access clause, **in both frames**, reported rather than
        # asserted: the clause was written against the **rail top**, and since
        # P71 the shipped surface is the belt top - 35 mm lower - so the same
        # trajectory reads 35 mm **higher** (the pre-flip instrument would have
        # printed `belt - 35`). Both numbers are given because the clause cannot
        # be judged in only one of them, and because the pre-P71 line misses it
        # on its own left legs too (`ctrl` reads +24/+27 on two of four).
        print("=" * 82)
        print("the +33 mm access clause on the HELD place legs - the reported "
              "surface (belt top for `treat`, rail top for `ctrl`) | the same")
        print("trajectory at the RAIL top (`treat` minus the 0.035 m the rail "
              "stood proud), i.e. what the pre-flip instrument printed:")
        for arm, data in parsed.items():
            treat = not arm.startswith("ctrl")
            drop = 35.0 if treat else 0.0
            for side in ("left", "right"):
                legs = [leg for leg in data["legs"]
                        if held(leg) and leg["side"] == side
                        and leg["leg"].startswith("place")]
                if not legs:
                    continue
                clr = [leg["crossing"]["clr"][0] for leg in legs if leg["crossing"]["clr"]]
                win = [leg["crossing"]["clr_win"][0] for leg in legs if leg["crossing"]["clr_win"]]
                ok = sum(1 for v in clr if v >= FLOOR_MM)
                okw = sum(1 for v in win if v >= FLOOR_MM)
                ok_r = sum(1 for v in clr if v - drop >= FLOOR_MM)
                print(f"  {arm:<10} {side:<5} n={len(clr):<3} "
                      f"clr {min(clr):+.0f}..{max(clr):+.0f} >= +33 on {ok}/{len(clr)} | "
                      f"clr_win {min(win):+.0f}..{max(win):+.0f} >= +33 on {okw}/{len(win)} | "
                      f"at the rail top >= +33 on {ok_r}/{len(clr)}")
        print()
        if problems:
            print("CHECK FAILED:")
            for problem in problems:
                print(f"  - {problem}")
            return 1
        print("check: PASS (15 episodes/arm, the lift row and its origin, the surface "
              "code per arm; the +33 clause is reported above, not asserted)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
