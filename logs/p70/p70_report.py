#!/usr/bin/env python3
"""P70 report: the rails/height cells on the scripted line.

    python3 logs/p70/p70_report.py logs/p70/{C,A,B}.log > logs/p70/p70_report.txt
    python3 logs/p70/p70_report.py --check logs/p70/{C,A,B}.log

Reads only the run logs (no simulator, no imports of the tree). Four sections:

1. **The arm** - attempts, starved slots (`no eligible fruit`), the `[stats]`
   line, the per-attempt placed flags.
2. **The crossing** - every held `place*` leg's `clr`/`clr_win`/`clr_min` **and
   the surface each was measured against** (`@rail` / `@obelt` / `@belt`), which
   is what proves the P70 instrument reads the authored geometry: a removed rail
   must report `@obelt` (the slab's inboard top edge), a shipped one `@rail`.
3. **The place-leg classes** - held (`clean_slip_max <= 50 mm`), the loaded
   slide the brief names (`clean_slip_max > 800 mm`), the escape band in
   between, and the mechanism fields of every escaping leg.
4. **The release-ledge census** - each attempt's `[task] target` row gives the
   species/diameter and the `[task] over the output belt` row the payload's own
   `(x, y, z)` at the start of the release block, so the release's lateral
   position is classified against the authored surfaces (slab 0.425..0.675,
   the inner rail's top face 0.400..0.425, the main belt inboard of 0.400) with
   the margin to the slab's inner edge, which is the ledge's own edge.

`--check` asserts the internal consistency the read depends on (10 `[run]
attempt` rows, a `[stats]` row, `[stats] successes` == the placed flags, a place
leg for every release row, and that no held leg read a surface that cannot be
there) and exits non-zero on failure.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIL_INNER = 0.400  # the inner rail's inboard face
RAIL_OUTER = 0.425  # its outboard face = the slab's inner edge
SLAB_OUTER = 0.675  # the slab's outer edge

RUN = re.compile(r"^\[fruit\] \[run\] attempt (\d+): (.*)$")
RUN_END = re.compile(r"grasped=(\w+) placed=(\w+)")
ATTEMPT = re.compile(
    r"^\[fruit\] \[task\] target (\w+) \(grade (\w), ([\d.]+) cm\) with (\w+) arm"
)
RELEASE = re.compile(
    r"^\[fruit\] \[task\]\s+over the output belt: jaw=\[([^\]]+)\] fruit=\[([^\]]+)\] "
    r"target=\(([-\d.]+),([-+\d.]+)\) top=([\d.]+)"
)
CARRY = re.compile(r"^\[fruit\] \[carry\] (\w+) ((?:place|grasp_lift)\d*): (.*)$")
MOTION = re.compile(r"^\[fruit\] \[motion\] carry (place\d+): (.*)$")
STATS = re.compile(r"^\[fruit\] \[stats\] (.*)$")


def num(text: str, default: float = float("nan")) -> float:
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def parse(path: Path) -> dict:
    """One log -> {'attempts': {index: record}, 'stats': {...}, 'starved': [..]}."""
    attempts: dict = {}
    starved: list = []
    run_rows: list = []
    stats: dict | None = None
    pending: int | None = None
    current: dict | None = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = RUN.match(line)
        if m:
            index, tail = int(m.group(1)), m.group(2)
            if index not in run_rows:
                run_rows.append(index)
            if tail.startswith("picking "):
                pending = index
            elif tail.startswith("no eligible fruit"):
                starved.append(index)
            else:
                end = RUN_END.search(tail)
                if end:
                    attempts.setdefault(index, {})["run"] = {
                        "grasped": end.group(1) == "True",
                        "placed": end.group(2) == "True",
                    }
            continue
        m = ATTEMPT.match(line)
        if m:
            species, grade, diameter, arm = m.groups()
            index = pending if pending is not None else len(attempts)
            current = attempts.setdefault(index, {})
            current.update(
                {
                    "species": species,
                    "grade": grade,
                    "diameter_m": float(diameter) / 100.0,
                    "arm": arm,
                    "release": None,
                    "carry": {},
                    "motion": {},
                }
            )
            continue
        m = RELEASE.match(line)
        if m and current is not None:
            fruit = [float(v) for v in m.group(2).split(",")]
            current["release"] = {
                "x": fruit[0],
                "y": fruit[1],
                "z": fruit[2],
                "top": float(m.group(5)),
            }
            continue
        m = CARRY.match(line)
        if m and current is not None:
            fields = {}
            for token in m.group(3).split():
                if "=" in token:
                    key, _, value = token.partition("=")
                    fields[key] = value
            current["carry"][m.group(2)] = {"side": m.group(1), **fields}
            continue
        m = MOTION.match(line)
        if m and current is not None:
            text = m.group(2)
            amax = re.search(r"\|a\|max=([\d.]+)", text)
            current["motion"][m.group(1)] = {
                "amax": float(amax.group(1)) if amax else float("nan"),
                "cone": re.search(r"cone=([\d.]+x)", text).group(1)
                if re.search(r"cone=([\d.]+x)", text) else "",
                "slip": num(re.search(r"slip=([\d.]+) mm", text).group(1))
                if re.search(r"slip=([\d.]+) mm", text) else float("nan"),
            }
            continue
        m = STATS.match(line)
        if m:
            text = m.group(1)

            def field(name: str, cast=float, default=None):
                hit = re.search(rf"{name}=([-+\d.]+)", text)
                return cast(hit.group(1)) if hit else default

            stats = {
                "attempts": field("attempts", int),
                "successes": field("successes", int),
                "diverted": field("diverted", int),
                "sim_s": field("sim", float),
                "s_per_attempt": num(
                    re.search(r"([\d.]+)s/attempt", text).group(1)
                ) if re.search(r"([\d.]+)s/attempt", text) else float("nan"),
                "recirculated": field("recirculated", int, 0),
                "gate_open": re.search(r"gate_open=([\d.]+)s", text).group(1)
                if "gate_open=" in text else "?",
                "queue_peak": re.search(r"queue_peak=(\d+)", text).group(1)
                if "queue_peak=" in text else "?",
            }
            continue
    return {"attempts": attempts, "stats": stats, "starved": starved,
            "run_rows": run_rows}


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


def classify_release(rel: dict, diameter: float) -> dict:
    y = abs(rel["y"])
    return {
        "abs_y": y,
        "radius": diameter / 2.0,
        "margin": y - RAIL_OUTER,
        "above_belt": rel["z"] >= rel["top"] - 0.02,
        "on_slab": y >= RAIL_OUTER,
        "centre_on_ledge": RAIL_INNER <= y < RAIL_OUTER,
        "inboard_of_all": y < RAIL_INNER,
        "outboard": y > SLAB_OUTER,
    }


def place_legs(attempts: dict) -> list:
    rows = []
    for index in sorted(attempts):
        attempt = attempts[index]
        for leg, fields in attempt.get("carry", {}).items():
            if not leg.startswith("place"):
                continue
            loss = fields.get("loss_row", "None")
            rows.append(
                {
                    "attempt": index,
                    "leg": leg,
                    "side": fields["side"],
                    "species": attempt.get("species", "?"),
                    "diameter_m": attempt.get("diameter_m", float("nan")),
                    "slip_mm": num(fields.get("clean_slip_max", "nan").replace("mm", "")),
                    "sep_end_mm": num(fields.get("sep_end", "nan").replace("mm", "")),
                    "contacts_at_onset": fields.get("contacts@onset", "?"),
                    "force_min": fields.get("force_min", "?"),
                    "res_end_mm": num(fields.get("res_end", "nan").replace("mm", "")),
                    "loss_row": None if loss in ("None", "n/a") else int(loss),
                    "ticks": int(num(fields.get("ticks", "0/0").split("/")[0], 0)),
                    "crossing": crossing_of(fields),
                    "placed": (attempt.get("run") or {}).get("placed"),
                    "motion": attempt.get("motion", {}).get(leg, {}),
                }
            )
    return rows


def held(row: dict) -> bool:
    """P66's gate convention: a clean grip and still in the hand at the crossing."""
    crossing = row["crossing"]["clr"] or row["crossing"]["clr_win"]
    if row["slip_mm"] > 50.0 or crossing is None:
        return False
    if row["loss_row"] is not None and crossing[2] is not None and row["loss_row"] < crossing[2]:
        return False
    return True


def fmt(cell) -> str:
    if cell is None:
        return "n/a"
    return f"{cell[0]:+.0f}@{cell[1]}" + (f"/t{cell[2]}" if cell[2] is not None else "")


def main(argv: list[str]) -> int:
    check = "--check" in argv
    paths = [Path(a) for a in argv if not a.startswith("--")]
    if not paths:
        print("usage: p70_report.py [--check] <log> [...]")
        return 2
    parsed = {}
    for path in paths:
        if not path.is_file():
            print(f"FAIL: {path} missing")
            return 1
        parsed[path.name.rsplit(".", 1)[0]] = parse(path)

    problems: list[str] = []
    print("=" * 78)
    print("P70 - the rails/height cells (scripted line, 10 attempts, one claim each)")
    print("=" * 78)
    print("surfaces: slab 0.425..0.675 | inner rail top face 0.400..0.425 | main belt < 0.400")
    print("crossing floor +33 mm (logs/p30a); contact boundary (+7, +14] mm (logs/p69/G0)")
    print()

    for arm, data in parsed.items():
        attempts = data["attempts"]
        stats = data["stats"]
        print(f"--- {arm} " + "-" * (74 - len(arm)))
        if stats:
            print(
                f"  {stats['attempts']} attempts counted, {stats['successes']} placed, "
                f"sim {stats['sim_s']:.1f} s, {stats['s_per_attempt']:.2f} s/attempt, "
                f"diverted={stats['diverted']} recirculated={stats['recirculated']} "
                f"gate_open={stats['gate_open']}s queue_peak={stats['queue_peak']}"
            )
        else:
            problems.append(f"{arm}: no [stats] row")
        if data["starved"]:
            print(f"  starved slots: {['attempt %d' % n for n in data['starved']]}")
        casualties = [
            (index, attempts[index].get("species", "?"), (attempts[index].get("run") or {}))
            for index in sorted(attempts)
            if (attempts[index].get("run") or {}).get("placed") is False
        ]
        print(
            f"  attempts: {len(attempts)} target rows | placed "
            f"{sum(1 for i in attempts if (attempts[i].get('run') or {}).get('placed'))} | "
            f"lost {len(casualties)}: "
            + ", ".join(f"ep{i} {sp}" for i, sp, _ in casualties)
        )

        releases = [
            (index, attempts[index])
            for index in sorted(attempts)
            if attempts[index].get("release")
        ]
        codes = {
            cell[1]
            for attempt in attempts.values()
            for fields in attempt.get("carry", {}).values()
            for cell in crossing_of(fields).values()
            if cell is not None and cell[1] in ("rail", "obelt")
        }
        surface = (
            "rails both (reads @rail)" if "rail" in codes
            else "inner rail removed (reads @obelt)" if "obelt" in codes
            else "?"
        )
        census = [
            classify_release(attempt["release"], attempt["diameter_m"])
            for _, attempt in releases
        ]
        print(f"  release rows: {len(releases)}/{len(attempts)} attempts [{surface}]")
        if census:
            live = [c for c in census if c["above_belt"]]
            print(
                f"  releases still in hand {len(live)}/{len(census)} "
                f"(the rest are payloads already on the main belt, z < top)"
            )
            if live:
                print(
                    "  release |y| (in-hand only): over the slab "
                    f"{sum(1 for c in live if c['on_slab'])}/{len(live)}, "
                    f"centre on the ledge band {sum(1 for c in live if c['centre_on_ledge'])}, "
                    f"inboard of everything {sum(1 for c in live if c['inboard_of_all'])}, "
                    f"outboard {sum(1 for c in live if c['outboard'])}; "
                    f"margin to the slab's inner edge "
                    f"{min(c['margin'] for c in live):+.3f}..{max(c['margin'] for c in live):+.3f} m"
                )
            for (index, attempt), row in zip(releases, census):
                print(
                    f"    ep{index:<2} {attempt['species']:<10} {attempt['arm']:<5} "
                    f"|y|={row['abs_y']:.3f} r={row['radius']:.3f} margin={row['margin']:+.3f} "
                    f"z={attempt['release']['z']:.3f} top={attempt['release']['top']:.2f} "
                    f"{'SLAB' if row['on_slab'] else 'LEDGE' if row['centre_on_ledge'] else 'INBOARD'}"
                    f"{'' if row['above_belt'] else ' (payload already off)'} "
                    f"placed={(attempt.get('run') or {}).get('placed')}"
                )

        rows = place_legs(attempts)
        held_rows = [r for r in rows if held(r)]
        loaded = [r for r in rows if r["slip_mm"] > 800.0]
        escapes = [r for r in rows if 50.0 < r["slip_mm"] <= 800.0]
        print(
            f"  place legs: {len(rows)} total | held {len(held_rows)} | "
            f"loaded slide (>800 mm) {len(loaded)} | escape 50-800 mm {len(escapes)}"
        )
        if held_rows:
            clr = [r["crossing"]["clr"][0] for r in held_rows if r["crossing"]["clr"]]
            win = [r["crossing"]["clr_win"][0] for r in held_rows if r["crossing"]["clr_win"]]
            print(
                f"  held crossing: clr {min(clr):+.0f}..{max(clr):+.0f} mm (n={len(clr)}), "
                f"clr_win {min(win):+.0f}..{max(win):+.0f} mm (n={len(win)})"
            )
            for row in held_rows:
                print(
                    f"    ep{row['attempt']:<2} {row['side']:<5} {row['leg']:<7} "
                    f"{row['species']:<10} clr={fmt(row['crossing']['clr']):<16} "
                    f"clr_win={fmt(row['crossing']['clr_win']):<16} "
                    f"clr_min={fmt(row['crossing']['clr_min']):<14} "
                    f"slip={row['slip_mm']:.1f} mm sep_end={row['sep_end_mm']:.1f} mm "
                    f"placed={row['placed']} "
                    f"|a|max={row['motion'].get('amax', float('nan')):.2f} "
                    f"cone={row['motion'].get('cone', '?')}"
                )
        if loaded or escapes:
            print("  escaping place legs (mechanism):")
            for row in loaded + escapes:
                print(
                    f"    ep{row['attempt']:<2} {row['side']:<5} {row['leg']:<7} "
                    f"{row['species']:<10} slip={row['slip_mm']:.1f} mm "
                    f"contacts@onset={row['contacts_at_onset']} "
                    f"force_min={row['force_min']} loss_row={row['loss_row']} "
                    f"sep_end={row['sep_end_mm']:.1f} mm placed={row['placed']} "
                    f"clr={fmt(row['crossing']['clr'])} clr_win={fmt(row['crossing']['clr_win'])}"
                )
        print()

    if check:
        for arm, data in parsed.items():
            attempts, stats = data["attempts"], data["stats"]
            if len(data["run_rows"]) != 10:
                problems.append(f"{arm}: {len(data['run_rows'])} [run] attempt rows, expected 10")
            if len(attempts) + len(data["starved"]) != 10:
                problems.append(
                    f"{arm}: {len(attempts)} target rows + {len(data['starved'])} starved != 10"
                )
            if stats is None:
                problems.append(f"{arm}: no [stats] row")
                continue
            placed = sum(1 for i in attempts if (attempts[i].get("run") or {}).get("placed"))
            if stats["successes"] != placed:
                problems.append(
                    f"{arm}: [stats] successes={stats['successes']} but {placed} placed flags"
                )
            if stats["attempts"] > len(attempts):
                problems.append(
                    f"{arm}: [stats] attempts={stats['attempts']} > {len(attempts)} rows"
                )
            for index, attempt in attempts.items():
                if attempt.get("release") and not any(
                    leg.startswith("place") for leg in attempt.get("carry", {})
                ):
                    problems.append(f"{arm} ep{index}: release row without a place leg")
            for row in place_legs(attempts):
                clr = row["crossing"]["clr"]
                if held(row) and clr is not None and clr[1] not in ("rail", "obelt"):
                    problems.append(
                        f"{arm} ep{row['attempt']}: held leg measured against {clr[1]}"
                    )
        if problems:
            print("CHECK FAILED:")
            for problem in problems:
                print(f"  - {problem}")
            return 1
        print(
            "check: PASS (10 [run] attempt rows/arm = target rows + starved slots, a "
            "[stats] row whose successes equal the placed flags, a place leg per release "
            "row, held legs read rail/obelt)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
