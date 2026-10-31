#!/usr/bin/env python3
"""P70 direct report: the low lift with the rails/height choice (`[carry]` read).

    python3 logs/p70/p70_direct_report.py [--check] logs/p70/direct/{D0,D1}.log

The direct loop conditions on rendered frames and is **not** bit-reproducible, so
nothing here is a rate: the sections are (1) the episode outcomes by class -
`placed`, `carried-not-placed` (the closed loaded-slide class, `logs/p42/
SIM_LIMIT.md`), `never-held`; (2) the arm split, because the direct env sets the
arm from the fruit's grade (`arm = left if grade == A`) and the treatment is the
left's; (3) every `place*` leg's crossing `clr`/`clr_win` **and the surface it
was measured against** (with the inner rail dropped it must read `@obelt`, i.e.
the slab's inboard top edge); (4) the mechanism fields of the escaping legs.
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
        if slip == slip and slip > 800.0:
            return "carried-not-placed (loaded slide)"
        return "carried-not-placed (other)"
    return "placed"


def held(leg: dict) -> bool:
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


def main(argv: list[str]) -> int:
    check = "--check" in argv
    paths = [Path(a) for a in argv if not a.startswith("--")]
    parsed = {}
    for path in paths:
        if not path.is_file():
            print(f"FAIL: {path} missing")
            return 1
        parsed[path.name.rsplit(".", 1)[0]] = parse(path)

    problems: list[str] = []
    print("=" * 78)
    print("P70 - the direct line, the low lift (FRUIT_LIFT_DZ=-0.08), 15 episodes, seed 77")
    print("=" * 78)
    for arm, data in parsed.items():
        episodes = data["episodes"]
        legs = data["legs"]
        print(f"--- {arm} " + "-" * (74 - len(arm)))
        print(f"  lift : {data['lift'] or '?'}")
        if data["wall_s"]:
            print(f"  wall : {data['wall_s']:.0f} s")
        classes: dict = {}
        for index in sorted(episodes):
            episode = episodes[index]
            label = classify(episode, legs)
            classes[label] = classes.get(label, 0) + 1
            print(
                f"    ep{index:<2} {episode['species']:<10} {episode['arm']:<5} "
                f"{'PLACED' if episode.get('placed') else '-':<6} {label:<32} "
                f"{(episode.get('notes') or '')[:60]}"
            )
        placed = sum(1 for e in episodes.values() if e.get("placed"))
        print(f"  {placed}/{len(episodes)} placed by class: " + ", ".join(
            f"{k} {v}" for k, v in sorted(classes.items())))
        for side in ("left", "right"):
            side_eps = [e for e in episodes.values() if e["arm"] == side]
            side_placed = sum(1 for e in side_eps if e.get("placed"))
            print(f"  {side:<5} {side_placed}/{len(side_eps)} placed")
        place = [leg for leg in legs if leg["leg"].startswith("place")]
        held_legs = [leg for leg in place if held(leg)]
        loaded = [leg for leg in place if num(
            leg["fields"].get("clean_slip_max", "nan").replace("mm", "")) > 800.0]
        codes = {
            cell[1] for leg in place for cell in leg["crossing"].values()
            if cell is not None and cell[1] in ("rail", "obelt")
        }
        print(
            f"  place legs {len(place)} | held {len(held_legs)} | "
            f"loaded slide (>800 mm) {len(loaded)} | surfaces {sorted(codes)}"
        )
        for leg in held_legs:
            clr = leg["crossing"]["clr"]
            edge = rail_cf = ""
            if clr is not None:
                # the transit's own straight-line slope from the lift end to the
                # transfer: (1.530 - 1.370) / 0.50 = 0.32 m of z per m of y, so the
                # 12.5 mm from the rail's centreline to the slab's inboard edge
                # buys +4.0 mm (an estimate; the achieved path also sags along it)
                edge = f"edge~{clr[0] + 4.0:+.0f}"
                # had the rail been authored, the same tick would read 35 mm less
                rail_cf = f"rail_cf~{clr[0] - 35.0:+.0f}"
            print(
                f"    ep{leg['episode']} {leg['side']:<5} {leg['leg']:<7} "
                f"clr={fmt(clr):<16} {edge:<10} {rail_cf:<14} "
                f"slip={leg['fields'].get('clean_slip_max', '?')} "
                f"sep_end={leg['fields'].get('sep_end', '?')} "
                f"|a|max={leg.get('amax', float('nan')):.2f}"
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
        print()

    if check:
        for arm, data in parsed.items():
            if len(data["episodes"]) != 15:
                problems.append(f"{arm}: {len(data['episodes'])} episodes, expected 15")
            if not any("clr=" in line for line in []):
                pass
            codes = {
                cell[1] for leg in data["legs"] for cell in leg["crossing"].values()
                if cell is not None and cell[1] in ("rail", "obelt")
            }
            if not codes:
                problems.append(f"{arm}: no leg read a rail/obelt surface")
            if not data["lift"]:
                problems.append(f"{arm}: no lift_dz row")
        if problems:
            print("CHECK FAILED:")
            for problem in problems:
                print(f"  - {problem}")
            return 1
        print("check: PASS (15 episodes/arm, a lift row, a rail/obelt surface read)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
