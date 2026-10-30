"""P69 G0 — the rail-crossing calibration curve, read off the scripted logs.

Read-only: parses the `[carry]` / `[motion] carry` / `[run] attempt` rows of
`20_pick_place.py` runs and prints one row per place leg (the crossing sample,
the leg minimum, the leg's `|a|max`, `clean_slip_max`) plus the held/escape
class, sorted by the crossing clearance.

    python3 logs/p69/g0/g0_report.py logs/p69/g0/*.log

The class rule is the record's: a leg whose reported clearance sits ~200 mm below
the rail top has its payload on the *main* belt (the escaped-payload class,
`logs/p30a/RESULTS.md` §5) and cannot answer the crossing question; so can a leg
that never seated (`contacts@onset=0`, the W8-B reading rule, P69-A §6).
"""

from __future__ import annotations

import re
import sys

CARRY = re.compile(
    r"\[carry\] (?P<side>\w+) (?P<name>\w+): ticks=(?P<ticks>\d+)/(?P<total>\d+) "
    r"clean_slip_max=(?P<slip>[\d.]+)mm.*?"
    r"clr=(?P<clr>[^ ]+) clr_win=(?P<win>[^ ]+) clr_min=(?P<cmin>[^ ]+) "
    r".*?contacts@onset=(?P<con>\w+) min_contacts=(?P<mincon>\w+) "
    r"force_min=(?P<fmin>[-\d.]+)N loss_row=(?P<loss>\w+)"
)
MOTION = re.compile(
    r"\[motion\] carry (?P<name>\w+): (?P<cm>[\d.]+) cm, (?P<ticks>\d+) ticks.*?"
    r"\|a\|max=(?P<a>[\d.]+) m/s\^2"
)
CLEAR = re.compile(
    r"\[motion\] carry (?P<name>\w+) clearance: lowest payload point "
    r"(?P<mm>[+-]\d+) mm to the (?P<where>.*)$"
)
PICK = re.compile(
    r"\[run\] attempt (?P<i>\d+): picking (?P<fruit>\w+) grade (?P<grade>\w+) "
    r"into output lane (?P<lane>\d+)"
)
DONE = re.compile(r"\[run\] attempt (?P<i>\d+): grasped=(?P<g>\w+) placed=(?P<p>\w+)")

KV = re.compile(r"^(?P<key>[a-z_@]+)=(?P<val>[^ ]+)$")


def _mm(field: str) -> float | None:
    """`+30mm@rail/t275` -> 30.0; `n/a` -> None."""
    if field.startswith("n/a"):
        return None
    return float(field.split("mm")[0])


def parse(path: str) -> list[dict]:
    legs: list[dict] = []
    attempt: dict | None = None
    pending: dict | None = None
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if (m := PICK.search(line)) is not None:
                attempt = {
                    "index": int(m.group("i")),
                    "fruit": m.group("fruit"),
                    "grade": m.group("grade"),
                    "lane": int(m.group("lane")),
                    "placed": None,
                    "legs": [],
                }
                continue
            if (m := DONE.search(line)) is not None and attempt is not None:
                attempt["placed"] = m.group("p") == "True"
                attempt["grasped"] = m.group("g") == "True"
                legs.append(attempt)
                attempt = None
                continue
            if (m := CARRY.search(line)) is not None:
                if pending is not None and attempt is not None:
                    attempt["legs"].append(pending)  # no [motion] rows in this log
                    pending = None
                if attempt is None:
                    # A log without `[run] attempt` bookkeeping (the direct env's
                    # `[rl] episode` lines): keep the leg on a synthetic attempt so
                    # the row still reaches the table.
                    attempt = {"index": -1, "fruit": "-", "grade": "-", "lane": -1,
                               "placed": None, "grasped": None, "legs": []}
                pending = {
                    "side": m.group("side"),
                    "name": m.group("name"),
                    "slip": float(m.group("slip")),
                    "clr": _mm(m.group("clr")),
                    "win": _mm(m.group("win")),
                    "cmin": _mm(m.group("cmin")),
                    "contacts": m.group("con"),
                    "fmin": float(m.group("fmin")),
                    "loss": m.group("loss"),
                    "a": None,
                    "legmin": None,
                    "where": None,
                }
                continue
            if pending is None:
                continue
            if (m := MOTION.search(line)) is not None:
                if m.group("name") == pending["name"]:
                    pending["a"] = float(m.group("a"))
                continue
            if (m := CLEAR.search(line)) is not None:
                if m.group("name") == pending["name"]:
                    pending["legmin"] = float(m.group("mm"))
                    pending["where"] = m.group("where").strip()
                    if attempt is not None:
                        attempt["legs"].append(pending)
                    pending = None
    if pending is not None and attempt is not None:
        attempt["legs"].append(pending)
    if attempt is not None and attempt not in legs:
        legs.append(attempt)  # the synthetic (no-[run]) attempt at EOF
    return legs


def classify(leg: dict) -> str:
    if leg["clr"] is None and leg["win"] is None:
        return "no-rail-read"
    worst = min(v for v in (leg["clr"], leg["win"]) if v is not None)
    if worst <= -150.0:
        return "escape"  # payload on the main belt, 180 mm below
    if leg["contacts"] == "0":
        return "never-held"
    return "held"


def main(argv: list[str]) -> int:
    rows: list[dict] = []
    for path in argv:
        tag = path.rsplit("/", 1)[-1].removesuffix(".log")
        for attempt in parse(path):
            for leg in attempt["legs"]:
                if not leg["name"].startswith("place"):
                    continue
                rows.append(
                    {
                        "run": tag,
                        **leg,
                        "fruit": attempt["fruit"],
                        "lane": attempt["lane"],
                        "placed": attempt["placed"],
                        "cls": classify(leg),
                    }
                )
    held = [r for r in rows if r["cls"] == "held"]
    held.sort(key=lambda r: (r["clr"] if r["clr"] is not None else 9e9))

    print("== all place legs (sorted by the crossing clearance `clr`) ==")
    print(
        f"{'run':6s} {'leg':7s} {'fruit':10s} {'lane':4s} {'clr':>6s} {'clr_win':>8s} "
        f"{'legmin':>7s} {'|a|max':>7s} {'slip':>8s} {'placed':>6s}  class"
    )
    for r in held + [r for r in rows if r["cls"] != "held"]:
        clr = "n/a" if r["clr"] is None else f"{r['clr']:+.0f}"
        win = "n/a" if r["win"] is None else f"{r['win']:+.0f}"
        mn = "n/a" if r["legmin"] is None else f"{r['legmin']:+.0f}"
        a = "n/a" if r["a"] is None else f"{r['a']:.2f}"
        pl = "?" if r["placed"] is None else str(r["placed"])
        print(
            f"{r['run']:6s} {r['name']:7s} {r['fruit']:10s} {r['lane']:4d} {clr:>6s} "
            f"{win:>8s} {mn:>7s} {a:>7s} {r['slip']:7.1f}m {pl:>6s}  {r['cls']}"
        )

    print()
    print("== held legs only: the calibration curve ==")
    if not held:
        print("(none)")
        return 0
    for r in held:
        a = "n/a" if r["a"] is None else f"{r['a']:6.2f}"
        print(
            f"clr={r['clr']:+4.0f}mm  clr_win={r['win']:+4.0f}mm  "
            f"|a|max={a} m/s^2  clean_slip={r['slip']:7.1f}mm  "
            f"{r['run']:6s} {r['fruit']:10s} lane{r['lane']} placed={r['placed']}"
        )
    jolt = [r for r in held if r["a"] is not None and r["a"] > 10.0]
    clean = [r for r in held if r["a"] is not None and r["a"] <= 10.0]
    print()
    print(f"held legs: {len(held)}; no-jolt (|a|max <= 10): {len(clean)}; "
          f"jolt (|a|max > 10): {len(jolt)}")
    if clean:
        lo = min(clean, key=lambda r: r["clr"])
        a = "n/a" if lo["a"] is None else f"{lo['a']:.2f}"
        print(f"lowest clr that PLACED WITHOUT A JOLT: {lo['clr']:+.0f} mm "
              f"({lo['run']} {lo['fruit']}, |a|max {a}, "
              f"placed={lo['placed']})")
    if jolt:
        hi = max(jolt, key=lambda r: r["clr"])
        print(f"highest clr WITH A JOLT: {hi['clr']:+.0f} mm "
              f"({hi['run']} {hi['fruit']}, |a|max {hi['a']:.2f})")  # jolt => a is set
    else:
        print("no jolt appears at any measured crossing clearance -> the "
              "boundary is BELOW the lowest held leg above")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
