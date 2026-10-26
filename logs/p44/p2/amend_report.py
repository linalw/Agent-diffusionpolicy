"""P44 phase 2 AMEND report (Oracle): S1 / S3-v / S2 against the same-instrument C.

    python3 logs/p44/p2/amend_report.py

Reads `logs/p44/p2/amend_{E,F}_*.log` and prints, per arm:

* **E1** - the per-leg **tick delta** (`[motion] carry <leg>` rows, mean vs C) and
  `s/attempt`, plus the `[cycle]` block means;
* **E4** - the **guard** rows, gated: any `fruit did not follow the gripper` note
  and the `[carry]` rows' `force_min == 0` (the loaded-slide signature) are the
  gate; `clean_slip_max` is quoted **arm-vs-control only** (no absolute bar - the
  live value is not W8-B's offline `clean_slip`);
* the release-cut landing check (battery F): the payload's `[place]` landing
  report rows for both arms, so a shortened release that drops the payload is
  visible rather than inferred.

Nothing here writes outside stdout.
"""

from __future__ import annotations

import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import p2_report as R  # noqa: E402  (the cycle/attempt/[motion] parsers)

OUT = R.OUT

CARRY_DIAG = re.compile(
    r"\[carry\] (\w+) (\w+): ticks=(\d+)/(\d+) clean_slip_max=([\d.]+)mm "
    r"in-hand_vmax=([\d.]+) onset_row=(-?\d+|None) force@onset=([\w/.-]+)N "
    r"sep@onset=([\w/.-]+)mm contacts@onset=(\d+|None) min_contacts=(\d+) "
    r"force_min=(-?[\d.]+)N loss_row=(-?\d+|None) sep@loss=([\w/.-]+)mm "
    r"sep_end=([\d.]+)mm guard=(\d+) events=(\d+) holds=(\d+)"
)
PLACE = re.compile(r"\[place\] (.+)")
ARMS = {"E": ["C", "S1", "S3v"], "F": ["C", "S2"]}


def num(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None


def read_diag(path: str) -> dict:
    rows = {"carry": [], "place": []}
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            m = CARRY_DIAG.search(line)
            if m:
                rows["carry"].append({
                    "side": m.group(1), "leg": m.group(2),
                    "ticks": int(m.group(3)),
                    "clean_slip_max": float(m.group(5)),
                    "in_hand_vmax": float(m.group(6)),
                    "force_at_onset": num(m.group(8)),
                    "force_min": float(m.group(12)),
                    "loss_row": None if m.group(13) == "None" else int(m.group(13)),
                    "sep_end": float(m.group(15)),
                    "events": int(m.group(17)),
                })
                continue
            m = PLACE.search(line)
            if m:
                rows["place"].append(m.group(1).strip())
    return rows


def leg_ticks(rows: dict) -> dict:
    out: dict[str, list[int]] = {}
    for leg in rows["carries"]:
        out.setdefault(leg["leg"], []).append(leg["ticks"])
    return out


def main() -> int:
    for battery, arms in ARMS.items():
        print("=" * 112)
        print(f"battery {battery}  (logs/p44/p2/amend_{battery}_*.log)")
        print("=" * 112)
        base = None
        for arm in arms:
            path = os.path.join(OUT, f"amend_{battery}_{arm}.log")
            rows = R.read(path)
            diag = read_diag(path)
            if not os.path.exists(path):
                print(f"{arm:<4s} MISSING")
                continue
            cyc = R.block_means(rows)
            stats = rows["stats"] or {}
            g = R.guard(rows)
            ticks = leg_ticks(rows)
            if arm == "C":
                base = ticks
            print(f"--- {arm}")
            print(f"  placed {g['placed']}/{g['n']}  cnp {g['cnp']}  no-grasp {g['nograsp']}  "
                  f"sim {stats.get('sim', float('nan')):.1f}s  s/att {stats.get('s_per_attempt', float('nan')):.2f}")
            print("  blocks: " + " ".join(
                f"{k}={cyc.get(k, float('nan')):.2f}" for k in
                ("prepose", "hover", "descent", "close", "grip", "lift", "place",
                 "release", "return", "total")))
            line = []
            for leg in ("grasp_lift", "place0", "place1"):
                vals = ticks.get(leg, [])
                if not vals:
                    continue
                text = f"{leg} {statistics.mean(vals):.1f}t (n={len(vals)})"
                if base and leg in base:
                    ref = statistics.mean(base[leg])
                    text += f" d={statistics.mean(vals) - ref:+.1f}t"
                line.append(text)
            print("  E1 per-leg ticks: " + "; ".join(line))
            notes = sorted({a["notes"] for a in rows["attempts"] if a["notes"]})
            print(f"  E4 grip rows: notes {g['grip_note']} {notes if notes else ''}  "
                  f"no-grasp {g['nograsp']}  cnp {g['cnp']}  rescued {g['rescued']}")
            fmin0 = [d for d in diag["carry"] if d["force_min"] <= 0.0]
            slips = sorted(d["clean_slip_max"] for d in diag["carry"])
            print(f"  E4 [carry] rows {len(diag['carry'])}: force_min==0 on {len(fmin0)} "
                  f"({[d['leg'] for d in fmin0]}); clean_slip_max "
                  f"p50 {statistics.median(slips) if slips else float('nan'):.1f}mm "
                  f"max {max(slips) if slips else float('nan'):.1f}mm "
                  f"(arm-vs-control only)")
            for d in diag["carry"]:
                if d["force_min"] <= 0.0 or d["clean_slip_max"] > 50.0:
                    print(f"     {d['side']} {d['leg']}: clean_slip_max={d['clean_slip_max']:.1f}mm "
                          f"force_min={d['force_min']:.2f}N loss_row={d['loss_row']} "
                          f"in-hand={d['in_hand_vmax']:.3f} events={d['events']} sep_end={d['sep_end']:.1f}mm")
            if diag["place"]:
                print(f"  F4 landing rows ({len(diag['place'])}): {diag['place'][0]}")
                for row in diag["place"][1:3]:
                    print(f"     {row}")
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
