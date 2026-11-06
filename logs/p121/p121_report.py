#!/usr/bin/env python3
"""P121 report: the direct env's instruction cells (ledger + outcomes).

    python3 logs/p121/p121_report.py logs/p121/direct/*.log
    python3 logs/p121/p121_report.py --check logs/p121/direct/{C,T1,T2,T3}.log

Reads only the run logs: the `[rl] episode ... success=` outcome rows, the
`[sort] attempt` rows (destination, arrow, rule, in_dest), the per-destination
`[sort] ledger dest=` rows and the `[sort]` refusal/coverage rows. The direct
loop is not reproducible, so the report never computes a rate: the endpoint is
the ledger's `in_destination / released` and the per-destination table.

Exit 0 unless `--check` fails:

* a placed attempt with `in_dest=0` (a mis-sort under the instruction);
* the summary `[sort] ledger` counts not summing to the attempt rows;
* the un-instructed cell printing any `[sort]`/`[scenario]` row (the unset
  path moved) or an instructed cell printing none (inert wiring).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ATTEMPT = re.compile(
    r"\[sort\] attempt (?P<attempt>\d+) idx=(?P<idx>\d+) (?P<species>\S+) "
    r"d=(?P<dia>[\d.]+)cm grade=(?P<grade>\S+) ripeness=[\d.]+ "
    r"arm=(?P<arm>\w+) rule=(?P<rule>\S+) dest=(?P<dest>\d+) "
    r"target=\([-\d.]+,(?P<ty>[+-][\d.]+)\)"
)
PLACED = re.compile(r"placed=(?P<placed>\d)")
IN_DEST = re.compile(r"in_dest=(?P<in_dest>\d)")
RELEASE = re.compile(
    r"release=\((?P<x>[-\d.]+),(?P<y>[+-][\d.]+),(?P<z>[\d.]+)\)"
)
EPISODE = re.compile(
    r"\[rl\] episode (?P<ep>\d+): (?P<species>\S+) d=(?P<dia>[\d.]+)cm "
    r"bin=(?P<bin>-?\d+) arm=(?P<arm>\w+) success=(?P<success>\w+) "
    r"grasped=(?P<grasped>\w+) placed=(?P<placed>\w+) ticks=(?P<ticks>\d+)"
    r".*?notes=\[(?P<notes>.*?)\] presentation="
)
SEED = re.compile(r"\[rl\] seed (?P<seed>\d+): (?P<ok>\d+)/(?P<n>\d+) success")
LEDGER = re.compile(
    r"\[sort\] ledger: attempts=(?P<attempts>\d+) assigned=(?P<assigned>\d+) "
    r"released=(?P<released>\d+) in_destination=(?P<in_destination>\d+) "
    r"mis_sorted=(?P<mis_sorted>\d+) not_placed=(?P<not_placed>\d+) "
    r"refused=(?P<refused>\d+)"
)
LEDGER_DEST = re.compile(
    r"\[sort\] ledger dest=(?P<dest>\d+): attempts=(?P<attempts>\d+) "
    r"released=(?P<released>\d+) in_destination=(?P<in_destination>\d+) "
    r"mis_sorted=(?P<mis_sorted>\d+) not_placed=(?P<not_placed>\d+)"
)
SORT_ROW = re.compile(r"\[sort\]|\[scenario\]")


def parse(path: Path) -> dict:
    cell = {
        "name": path.stem,
        "path": str(path),
        "episodes": [],
        "seeds": [],
        "attempts": [],
        "ledger": None,
        "by_dest": {},
        "coverage": "",
        "sort_rows": 0,
        "refusals": [],
        "unreachable": False,
    }
    for line in path.read_text(errors="replace").splitlines():
        if SORT_ROW.search(line):
            cell["sort_rows"] += 1
        if "[sort] coverage:" in line:
            cell["coverage"] = line.split("[sort] coverage:", 1)[1].strip()
        if "UNREACHABLE" in line:
            cell["unreachable"] = True
        m = EPISODE.search(line)
        if m:
            cell["episodes"].append(m.groupdict())
        m = SEED.search(line)
        if m:
            cell["seeds"].append(m.groupdict())
        m = LEDGER.search(line)
        if m:
            cell["ledger"] = {k: int(v) for k, v in m.groupdict().items()}
        m = LEDGER_DEST.search(line)
        if m:
            cell["by_dest"][int(m.group("dest"))] = {
                k: int(v) for k, v in m.groupdict().items()
            }
        if "REFUSED" in line or "refused:" in line:
            cell["refusals"].append(line.strip())
        m = ATTEMPT.search(line)
        if m:
            row = m.groupdict()
            for name in ("attempt", "idx", "dest", "dia"):
                row[name] = float(row[name]) if name == "dia" else int(row[name])
            placed = PLACED.search(line)
            in_dest = IN_DEST.search(line)
            release = RELEASE.search(line)
            row["placed"] = int(placed.group("placed")) if placed else 0
            row["in_dest"] = int(in_dest.group("in_dest")) if in_dest else 0
            row["release"] = release.groupdict() if release else None
            cell["attempts"].append(row)
    return cell


def classify(episode: dict) -> str:
    """P37/P43's outcome classes, from the env's own row (no new definition)."""
    if episode["placed"] == "True":
        return "placed"
    notes = episode.get("notes") or ""
    if "fell off the line" in notes:
        return "fell_off"
    if "timeout" in notes:
        return "timeout"
    if episode["grasped"] == "False":
        return "never_held"
    return "cnp"


def note_key(episode: dict) -> str:
    """The failure note text with digits stripped (P38's method).

    The env's `notes` list carries the fire tick's `intercept trigger (...)` on
    most attempts, success and failure alike; it is not a failure reason, so it
    is filtered out and only the remaining note(s) name the class.
    """
    notes = episode.get("notes") or ""
    parts = [part.strip(" '") for part in notes.split("', '")]
    failure = [part for part in parts if not part.startswith("intercept trigger")]
    key = "; ".join(failure) if failure else "(no failure note)"
    return re.sub(r"[-+]?\d[\d.]*", "#", key)


def summarize(cell: dict) -> list[str]:
    eps = cell["episodes"]
    placed = sum(1 for e in eps if e["placed"] == "True")
    grasped = sum(1 for e in eps if e["grasped"] == "True")
    lines = [
        f"== {cell['name']}  ({cell['path']})",
        f"  episodes={len(eps)} placed={placed} grasped={grasped} seeds="
        + str([(s["seed"], s["ok"] + "/" + s["n"]) for s in cell["seeds"]]),
    ]
    classes: dict[str, int] = {}
    notes: dict[str, int] = {}
    for ep in eps:
        classes[classify(ep)] = classes.get(classify(ep), 0) + 1
        if classify(ep) != "placed":
            notes[note_key(ep)] = notes.get(note_key(ep), 0) + 1
    lines.append(f"  classes: {dict(sorted(classes.items()))}")
    for key in sorted(notes):
        lines.append(f"    failure note x{notes[key]}: {key[:110]}")
    if cell["ledger"] is not None:
        led = cell["ledger"]
        acc = (
            f"{led['in_destination']}/{led['released']}"
            if led["released"]
            else "0/0"
        )
        lines.append(
            f"  ledger: attempts={led['attempts']} released={led['released']} "
            f"in_destination={led['in_destination']} mis_sorted={led['mis_sorted']} "
            f"not_placed={led['not_placed']} refused={led['refused']} "
            f"-> assignment {acc}"
        )
        for dest in sorted(cell["by_dest"]):
            row = cell["by_dest"][dest]
            lines.append(
                f"    dest={dest}: attempts={row['attempts']} "
                f"released={row['released']} in_dest={row['in_destination']} "
                f"mis_sorted={row['mis_sorted']} not_placed={row['not_placed']}"
            )
    if cell["attempts"]:
        pairs = {}
        for row in cell["attempts"]:
            pairs.setdefault((row["grade"], row["arm"], row["dest"]), [0, 0])
            pairs[(row["grade"], row["arm"], row["dest"])][0] += 1
            pairs[(row["grade"], row["arm"], row["dest"])][1] += row["in_dest"]
        lines.append("  grade/arm/dest (n, in_dest):")
        for key in sorted(pairs):
            lines.append(f"    grade={key[0]} arm={key[1]} dest={key[2]} -> {pairs[key]}")
    if cell["coverage"]:
        lines.append(f"  coverage: {cell['coverage']}")
    if cell["unreachable"]:
        lines.append("  ** an UNREACHABLE destination row is present **")
    if cell["refusals"]:
        lines.append(f"  refusals: {len(cell['refusals'])} row(s)")
    return lines


def check(cells: list[dict]) -> list[str]:
    fails: list[str] = []
    for cell in cells:
        name = cell["name"]
        armed = name != "C"
        if armed and cell["sort_rows"] == 0:
            fails.append(f"{name}: an instructed cell printed no [sort] row")
        if not armed and cell["sort_rows"]:
            fails.append(f"{name}: the un-instructed control printed [sort]/[scenario]")
        if not armed:
            continue
        if cell["ledger"] is None:
            fails.append(f"{name}: no [sort] ledger summary")
            continue
        led = cell["ledger"]
        if led["mis_sorted"]:
            fails.append(f"{name}: {led['mis_sorted']} mis-sorted release(s)")
        bad = [row for row in cell["attempts"] if row["placed"] and not row["in_dest"]]
        if bad:
            fails.append(
                f"{name}: {len(bad)} placed attempt(s) with in_dest=0 "
                f"(attempt {[r['attempt'] for r in bad]})"
            )
        rows = cell["attempts"]
        if len(rows) != led["attempts"]:
            fails.append(
                f"{name}: {len(rows)} attempt rows against ledger attempts="
                f"{led['attempts']}"
            )
        if sum(r["placed"] for r in rows) != led["released"]:
            fails.append(
                f"{name}: attempt placed count {sum(r['placed'] for r in rows)} "
                f"against ledger released={led['released']}"
            )
        if sum(cell["by_dest"][d]["attempts"] for d in cell["by_dest"]) != led[
            "attempts"
        ]:
            fails.append(f"{name}: per-destination attempts do not sum to the summary")
    # T1 must route exactly as the scripted pure-routing file says: A->0, B->1,
    # and grade C (matched by `skip`) is never selected.
    t1 = next((c for c in cells if c["name"] == "T1"), None)
    if t1 is not None:
        for row in t1["attempts"]:
            expected = 0 if row["grade"] == "A" else 1
            if row["grade"] == "C":
                fails.append("T1: a grade-C fruit was selected although the rule is skip")
            elif row["dest"] != expected:
                fails.append(
                    f"T1: grade {row['grade']} went to dest {row['dest']}, "
                    f"expected {expected}"
                )
    # T2 must be grade-independent, not the shipped rule. The discriminating
    # direction is a grade-B/C fruit on dest 0 (the shipped rule sends every
    # non-A fruit to the right); the mirror (a grade-A fruit on dest 1) only
    # appears when the pool draws a small A-grade fruit. P3a was not evaluable
    # on this draw (no grade-A small fruit), P3b fired - see RESULTS.md.
    t2 = next((c for c in cells if c["name"] == "T2"), None)
    if t2 is not None:
        a_right = [r for r in t2["attempts"]
                   if r["grade"] == "A" and r["dest"] == 1]
        nona_left = [r for r in t2["attempts"]
                     if r["grade"] != "A" and r["dest"] == 0]
        if not a_right and not nona_left:
            fails.append("T2: no grade-independent destination witness at all")
        print(
            f"T2 witnesses: grade-B/C -> dest 0 = {len(nona_left)} attempt(s) "
            f"({sum(r['in_dest'] for r in nona_left)} in_dest); "
            f"grade-A -> dest 1 = {len(a_right)} attempt(s) "
            f"({'not evaluable on this draw' if not a_right else 'fired'})"
        )
    # T1b is optional, but when present it must be exactly the direct routing.
    t1b = next((c for c in cells if c["name"] == "T1b"), None)
    if t1b is not None:
        for row in t1b["attempts"]:
            expected = 0 if row["grade"] == "A" else 1
            if row["dest"] != expected:
                fails.append(
                    f"T1b: grade {row['grade']} went to dest {row['dest']}, "
                    f"expected {expected}"
                )
    return fails


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    cells = [parse(Path(name)) for name in args.logs]
    for cell in cells:
        for line in summarize(cell):
            print(line)
        print()
    if args.check:
        fails = check(cells)
        if fails:
            print("P121 report: FAIL")
            for msg in fails:
                print(f"  - {msg}")
            return 1
        print("P121 report: PASS (ledger + per-destination + no mis-sort)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
