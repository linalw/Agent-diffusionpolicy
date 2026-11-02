"""P92: the force servo's own travel per attempt - the `closed > 0` signature.

    python3 logs/p92/chase.py [--all]

Read-only, offline. Per attempt the task prints one `[task] force servo:` row
from `note_result`, with one segment per arm:

    left: ref=4.00N F[8.81,10.95]N gap=63.6mm sep=70.3mm closed=0.00mm opened=0.00mm trips=0
    left: ref=0.00N F[0.00,0.00]N  gap=37.2mm sep=37.2mm closed=15.00mm opened=0.00mm trips=38

`closed` is the servo's closure travel (`_force_moves[...]["closed_mm"]`), i.e.
how far its integral law walked the commanded gap **inward** past the gap the
grip closed with. The attempt's arm is the `[biarm] result <arm>` row that
follows it, and the class is `census.py`'s classifier, so this reads the same
attempts the census does.

Printing one row per attempt is what makes the read auditable: the phase's
claim is that `closed > 0` *is* the failure signature on this cell, and a
precision test of 11/11 against 1/29 is only worth quoting if the 11 rows can
be looked at.
"""

from __future__ import annotations

import os
import re
import sys
from math import comb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import census  # noqa: E402

FS = re.compile(r"\[task\] force servo: (?P<body>.*)$")
RESULT = re.compile(
    r"\[biarm\] result (?P<arm>left|right) index=\d+ (?P<fruit>\w+) "
    r"grasped=(?P<grasped>True|False) placed=(?P<placed>True|False)")
#: the shipped-cell pair (`PREREG.md`) and the pre-P87 block (a different clock)
SHIPPED = (("seed 5", "logs/p91/C5.log"), ("seed 6", "logs/p91/C6.log"))
PRE = (("seed 5", "logs/p84/D5.log"), ("seed 6", "logs/p84/D6.log"))


def segments(body: str) -> dict:
    out = {}
    for part in body.split(" | "):
        m = re.match(r"\s*(left|right): (.*)$", part)
        if not m:
            continue
        arm, rest = m.group(1), m.group(2)

        def g(key):
            mm = re.search(rf"(?:^| ){key}=(\[[^\]]*\]|[^\s]+)", rest)
            return mm.group(1) if mm else None

        out[arm] = {"ref": g("ref"), "F": g("F"), "gap": g("gap"),
                    "sep": g("sep"), "closed": g("closed"),
                    "opened": g("opened"), "trips": g("trips")}
    return out


def read(path: str) -> list[dict]:
    rows = []
    pending: dict = {}
    for ln in open(path, errors="replace"):
        if m := FS.search(ln):
            pending.update(segments(m.group("body")))
            continue
        if m := RESULT.search(ln):
            arm = m["arm"]
            s = pending.get(arm) or {}
            closed = s.get("closed")
            rows.append({
                "arm": arm, "fruit": m["fruit"],
                "grasped": m["grasped"] == "True",
                "placed": m["placed"] == "True",
                "ref": s.get("ref"), "force": s.get("F"),
                "gap": s.get("gap"), "sep": s.get("sep"),
                "closed": float(closed.replace("mm", "")) if closed else None,
                "trips": int(s["trips"]) if s.get("trips") else None,
            })
            pending = {}
    return rows


def table(label: str, cells) -> list[dict]:
    print(f"\n== {label}")
    out = []
    for tag, path in cells:
        full = os.path.join(ROOT, path)
        if not os.path.exists(full):
            print(f"  {tag}: MISSING {path}")
            continue
        rows = read(full)
        d = census.parse(full)
        # the census class, matched by the attempt's own result row (same order)
        cls = [a["cls"] for a in d["attempts"]]
        if len(cls) != len(rows):
            print(f"  {tag}: {len(rows)} servo rows vs {len(cls)} attempts - "
                  f"attributing by position only")
        print(f"  {tag} ({path}): {len(rows)} attempts")
        for i, r in enumerate(rows):
            c = cls[i] if i < len(cls) else "?"
            r["cls"] = c
            r["cell"] = tag
            out.append(r)
            closed = "-" if r["closed"] is None else f"{r['closed']:.2f}"
            print(f"    {tag} {r['arm']:5s} {r['fruit']:10s} grasped={str(r['grasped']):5s} "
                  f"placed={str(r['placed']):5s} cls={c:10s} ref={str(r['ref']):7s} "
                  f"closed={closed}mm trips={r['trips']}")
    return out


def precision(rows: list[dict], key: str) -> None:
    hit = [r for r in rows if (r["closed"] or 0.0) > 0.0]
    miss = [r for r in rows if (r["closed"] or 0.0) == 0.0]
    hf = [r for r in hit if not r["placed"]]
    mf = [r for r in miss if not r["placed"]]
    N, K, n = len(rows), len(hf) + len(mf), len(hit)
    p = (comb(K, n) / comb(N, n)) if n <= K else float("nan")
    print(f"\n{key}: `closed > 0` n={n} failed={len(hf)}  |  "
          f"`closed == 0` n={len(miss)} failed={len(mf)}")
    print(f"  hypergeometric, all {len(hf)} of the chased attempts failed: p = {p:.3g}")
    classes = {}
    for r in hf:
        classes[r["cls"]] = classes.get(r["cls"], 0) + 1
    print(f"  the chased failures' classes: {classes}")
    print(f"  the chased attempts by cell: "
          f"{ {c: sum(1 for r in hit if r['cell'] == c) for c in sorted({r['cell'] for r in hit})} }")


def main(argv) -> int:
    rows = table("the shipped cell (P92's own controls, this tree)",
                 SHIPPED)
    precision(rows, "shipped cell")
    if "--all" in argv:
        pre = table("the pre-P87 clock (a different scenario, kept separate)", PRE)
        precision(pre, "pre-P87 block")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
