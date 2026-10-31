#!/usr/bin/env python3
"""P72 report: the corner clearance (`clr_edge`) of the shipped P71 package.

    python3 logs/p72/p72_report.py [--check] logs/p72/direct/treat_77.log [...]

The direct loop conditions on rendered frames and is **not** bit-reproducible, so
nothing here is a rate. Per log the sections are

(1) the `[carry]` row's **four** clearance reductions on the place legs -
    `clr` (rail centreline, 0.4125), `clr_win` (the rail's former 25 mm
    footprint, from 0.400), `clr_min` (the leg minimum) and the P72
    `clr_edge`/`clr_edge_min` (the output slab's own inboard edge, 0.425 - the
    surface that remains after the P71 rail removal). `clr`/`clr_win` begin
    25 mm **inboard of the slab** (a void the plane reading charges),
    `clr_edge` begins where the surface does;

(2) the **held** place legs - still in hand when the payload reaches the edge -
    with each leg's corner sample, the G0 contact channel (`|a|max` from the
    `[motion] carry` row: 2.6-5.7 m/s^2 is its clean population, 14.9-32.7 its
    rail-contact one) and the W8-B slip, so a negative corner sample can be
    read against the contact signature rather than in isolation;

(3) the distribution of `clr_edge` and `clr_edge_min` over the held legs: n,
    min, median, max, and how many are `<= 0` (the P72 floor's own quantity);

(4) the failure reasons, so a new one is visible.

`--check` exits non-zero when a held leg's corner sample is missing (the field
did not fire), when the surfaces are not `obelt` (a rail is still authored), or
when a `clr_edge <= 0` leg carries a contact signature - i.e. it gates the
instrument's *presence*, never a rate.
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
SLIDE_MM = 800.0
CELL = re.compile(r"([-+\d.]+)mm@(\w+)(?:/t(\d+))?$")


def num(text, default=float("nan")):
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def cell_of(text: str):
    m = CELL.match(text or "")
    if not m:
        return None
    return (
        float(m.group(1)),
        m.group(2),
        int(m.group(3)) if m.group(3) else None,
    )


def parse(path: Path) -> dict:
    episodes: dict = {}
    legs: list = []
    current = None
    index = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = EPISODE.match(line)
        if m:
            index = int(m.group(1))
            current = episodes.setdefault(index, {"index": index})
            current.update(
                {"species": m.group(2), "arm": m.group(6),
                 "diameter_m": float(m.group(4)) / 100.0}
            )
            outcome = OUTCOME.search(m.group(8))
            if outcome:
                current["success"] = outcome.group(1) == "True"
                current["grasped"] = outcome.group(2) == "True"
                current["placed"] = outcome.group(3) == "True"
                notes = NOTES.search(m.group(8))
                current["notes"] = notes.group(1) if notes else ""
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
                    "episode": index,
                    "species": current["species"] if current else "?",
                    "fields": fields,
                    "clr": cell_of(fields.get("clr", "")),
                    "clr_win": cell_of(fields.get("clr_win", "")),
                    "clr_min": cell_of(fields.get("clr_min", "")),
                    "edge": cell_of(fields.get("clr_edge", "")),
                    "edge_min": cell_of(fields.get("clr_edge_min", "")),
                }
            )
            continue
        m = MOTION.match(line)
        if m and legs:
            amax = re.search(r"\|a\|max=([\d.]+)", m.group(2))
            legs[-1]["amax"] = float(amax.group(1)) if amax else float("nan")
    return {"episodes": episodes, "legs": legs}


def classify(episode: dict, legs: list) -> str:
    if not episode.get("success"):
        if not episode.get("grasped"):
            return "never-held"
        place = [leg for leg in legs if leg["episode"] == episode["index"]
                 and leg["leg"].startswith("place")]
        slip = max(
            (num(leg["fields"].get("clean_slip_max", "").replace("mm", ""))
             for leg in place),
            default=float("nan"),
        )
        if slip == slip and slip > SLIDE_MM:
            return "carried-not-placed (loaded slide)"
        return "carried-not-placed (other)"
    return "placed"


def held(leg: dict) -> bool:
    """In hand when the payload reached the corner (the `p71` convention)."""
    crossing = leg["clr"] or leg["clr_win"] or leg["edge"]
    slip = num(leg["fields"].get("clean_slip_max", "").replace("mm", ""))
    loss = leg["fields"].get("loss_row", "None")
    if crossing is None or slip > 50.0:
        return False
    if loss not in ("None", "n/a") and crossing[2] is not None and int(loss) < crossing[2]:
        return False
    return True


def fmt(cell) -> str:
    if cell is None:
        return "n/a"
    return f"{cell[0]:+.0f}@{cell[1]}" + (f"/t{cell[2]}" if cell[2] is not None else "")


def stats(values: list) -> str:
    if not values:
        return "n=0"
    ordered = sorted(values)
    n = len(ordered)
    median = ordered[n // 2] if n % 2 else 0.5 * (ordered[n // 2 - 1] + ordered[n // 2])
    return (
        f"n={n} min={ordered[0]:+.0f} med={median:+.1f} max={ordered[-1]:+.0f} "
        f"<=0: {sum(1 for v in ordered if v <= 0)}"
    )


def main(argv: list[str]) -> int:
    check = "--check" in argv
    paths = [Path(a) for a in argv if not a.startswith("--")]
    if not paths:
        print("usage: p72_report.py [--check] <direct log> ...")
        return 2
    problems: list[str] = []
    print("=" * 84)
    print("P72 - the corner clearance of the shipped P71 package "
          "(rails=none, direct lift +0.20)")
    print("=" * 84)
    for path in paths:
        if not path.is_file():
            print(f"FAIL: {path} missing")
            return 1
        data = parse(path)
        legs = data["legs"]
        place = [leg for leg in legs if leg["leg"].startswith("place")]
        held_legs = [leg for leg in place if held(leg)]
        classes: dict = {}
        reasons: dict = {}
        for index in sorted(data["episodes"]):
            episode = data["episodes"][index]
            label = classify(episode, legs)
            classes[label] = classes.get(label, 0) + 1
            if label != "placed":
                text = re.sub(r"\d+(\.\d+)?", "#", (episode.get("notes") or "").strip())
                key = text.split(";")[0][:60] or "-"
                reasons[key] = reasons.get(key, 0) + 1
        print(f"--- {path.stem} " + "-" * max(0, 60 - len(path.stem)))
        print(f"  placed {classes.get('placed', 0)}/{len(data['episodes'])} by class: "
              + ", ".join(f"{k} {v}" for k, v in sorted(classes.items())))
        print(f"  place legs {len(place)} | held {len(held_legs)} | "
              f"surfaces {sorted({c[1] for leg in place for c in (leg['clr'], leg['edge']) if c})}")
        if reasons:
            for key, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
                print(f"    x{count}  {key}")
        for leg in held_legs:
            slip = leg["fields"].get("clean_slip_max", "?")
            sep = leg["fields"].get("sep_end", "?")
            amax = leg.get("amax", float("nan"))
            print(
                f"    ep{leg['episode']:<2} {leg['side']:<5} {leg['leg']:<7} "
                f"clr={fmt(leg['clr']):<16} clr_edge={fmt(leg['edge']):<16} "
                f"edge_min={fmt(leg['edge_min']):<16} "
                f"slip={slip:<8} sep_end={sep:<8} |a|max={amax:.2f}"
            )
        edges = [leg["edge"][0] for leg in held_legs if leg["edge"]]
        edge_mins = [leg["edge_min"][0] for leg in held_legs if leg["edge_min"]]
        print(f"  clr_edge      {stats(edges)}")
        print(f"  clr_edge_min  {stats(edge_mins)}")
        if check:
            if len(edges) != len(held_legs):
                problems.append(f"{path.stem}: {len(held_legs) - len(edges)} held legs "
                                "without clr_edge (did the field fire?)")
            bad = sorted({c[1] for leg in place for c in (leg["clr"], leg["edge"]) if c})
            if "rail" in bad:
                problems.append(f"{path.stem}: a rail surface is still reported {bad}")
            for leg in held_legs:
                if leg["edge"] and leg["edge"][0] <= 0.0 and leg.get("amax", 0.0) > 14.0:
                    problems.append(
                        f"{path.stem}: ep{leg['episode']} reads clr_edge "
                        f"{leg['edge'][0]:+.0f} mm WITH a contact signature "
                        f"(|a|max {leg['amax']:.2f})"
                    )
    if check:
        if problems:
            for line in problems:
                print(f"FAIL: {line}")
            return 1
        print("check: PASS (a corner sample on every held leg, no rail surface, "
              "no negative corner with a contact signature)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
