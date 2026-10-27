#!/usr/bin/env python3
"""P50 phase 2 - the per-pool release-offset tables (`configs/release_offsets_*.json`).

Reads the **phase-1 probe logs** (no simulator here) and writes one table per
pool:

    python3 logs/p50/p2/make_offset_table.py            # writes the two configs

The construction is the one `logs/p50/PREREG.md` section 2 registers:

* the per-instance source is the **live** run at the arm's own seed
  (`offset_probe.py FRUIT_MODE=live`), where every release is attributed by the
  `respawn` wrapper - i.e. the *shipped* free-cadence condition, not the bare
  drop (`logs/p50/OFFSET_TABLE.md` section 4);
* an instance's value is the **mean of its attributed releases**, except
* **the mode rule**: if its releases fall into >= 2 clusters separated by more
  than `MODE_GAP_MM`, its value is the **midpoint of the extreme modes**
  (minimax) - at seed 5 that is the two rollers, kiwi idx 02 (+35.0/+39.7 vs
  +54.5/+54.6) and strawberry idx 05 (-22.1/-24.3 vs -35.7).

The isolated 3-x tables (`offset_probe_s5.log`, the wake variant
`offset_probe_s5_wake.log`, `offset_pear_s5.log`) are carried in the provenance
block as the cross-check: they are the deterministic per-cell measurement, and
the live value has to agree with them to <= 0.5 mm on every single-mode
instance (it does - `OFFSET_TABLE.md` section 4).

The pear table is **identity** by construction (TASK: the pear pool's table is
identity): the pear pool has no release tail (offsets `-3.33..+2.69 mm`, 0.00 %
outside the band before and after), so its arm in phase 2 is an inertness
control of the knob path, and an identity table is what makes "the compensated
arm must be physics-identical to the control" a sharp prediction. Its measured
per-instance offsets are recorded in the provenance block, not applied.

Neither file is a *reference*: `configs/motion_reference*.json` are untouched.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
P1 = os.path.join(ROOT, "logs", "p50", "p1")

#: Two live releases of one instance belong to different *modes* when they are
#: further apart than this. The measured instance sd on the single-mode set is
#: <= 0.12 mm and the two rollers' modes are 11.4 / 14.9 mm apart, so 5 mm
#: separates the classes with an order of magnitude to spare (PREREG section 2).
MODE_GAP_MM = 5.0

LIVE = re.compile(
    r"\[offset\] live idx=(?P<idx>\d+) cat=(?P<cat>\S+)\s+dia_mm=\s*(?P<dia>[\d.]+) "
    r"grade=(?P<grade>\S+) x_cmd=(?P<xc>[+-][\d.]+) .*?off_mm=\s*(?P<off>[+-][\d.]+) "
)
CELL = re.compile(
    r"\[offset\] instance idx=(?P<idx>\d+) cat=(?P<cat>\S+)\s+dia_mm=\s*(?P<dia>[\d.]+) "
    r"grade=(?P<grade>\S+) (?P<cells>.*)$"
)
CELL_ONE = re.compile(r"x(?P<x>\d\.\d\d):\s*(?P<off>[+-][\d.]+)\((?P<spread>[\d.]+)\)")


def md5(path: str) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def rel(path: str) -> str:
    return os.path.relpath(path, ROOT)


def read_live(name: str) -> dict:
    """The `[offset] live idx=` attribution rows of one probe log, by instance."""
    path = os.path.join(P1, name)
    out: dict[int, dict] = {}
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            match = LIVE.search(line)
            if not match:
                continue
            row = match.groupdict()
            index = int(row["idx"])
            rec = out.setdefault(
                index,
                {"idx": index, "cat": row["cat"], "dia_mm": float(row["dia"]),
                 "grade": row["grade"], "offsets": []},
            )
            rec["offsets"].append(float(row["off"]))
    return out


def read_cells(name: str) -> dict:
    """The `[offset] instance` per-cell (isolated/wake) table of one probe log."""
    path = os.path.join(P1, name)
    out: dict[int, dict] = {}
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            match = CELL.search(line)
            if not match:
                continue
            row = match.groupdict()
            cells = {float(one.group("x")): float(one.group("off"))
                     for one in CELL_ONE.finditer(row["cells"])}
            out[int(row["idx"])] = {
                "cat": row["cat"], "dia_mm": float(row["dia"]),
                "grade": row["grade"], "cells": cells,
            }
    return out


def clusters(values: list[float], gap: float = MODE_GAP_MM) -> list[list[float]]:
    """Split a sorted instance's offsets where the consecutive gap exceeds `gap`."""
    ordered = sorted(values)
    out: list[list[float]] = []
    for value in ordered:
        if out and value - out[-1][-1] <= gap:
            out[-1].append(value)
        else:
            out.append([value])
    return out


def instance_value(offsets: list[float]) -> tuple[float, str]:
    """`(offset_mm, rule)`: the mode-rule minimax, else the live mean."""
    groups = clusters(offsets)
    if len(groups) >= 2:
        low = groups[0][0]
        high = groups[-1][-1]
        return (low + high) / 2.0, f"mode-midpoint [{low:+.2f}, {high:+.2f}]"
    return sum(offsets) / len(offsets), f"mean n={len(offsets)}"


def signature(cat: str, dia_mm: float) -> str:
    return f"{cat}|{dia_mm:.1f}"


def build(scenario: str, live_log: str | None, isolated_log: str, wake_log: str | None,
          identity: bool, note: str) -> dict:
    """One pool's table: the live per-release value (or the measured cell) per instance."""
    live = read_live(live_log) if live_log else {}
    isolated = read_cells(isolated_log)
    wake = read_cells(wake_log) if wake_log else {}
    if live and sorted(live) != sorted(isolated):
        raise SystemExit(
            f"{scenario}: the live log covers {sorted(live)} but the isolated "
            f"table covers {sorted(isolated)} - not the same pool"
        )
    source = live if live else isolated
    offsets: dict[str, float] = {}
    rows: list[dict] = []
    for index in sorted(source):
        rec = source[index]
        if live:
            value, rule = instance_value(rec["offsets"])
            mean = sum(rec["offsets"]) / len(rec["offsets"])
            cells = isolated[index]["cells"]
            live_offsets = [round(v, 2) for v in rec["offsets"]]
            live_n = len(rec["offsets"])
        else:
            # No live run for this pool: the deterministic isolated cell at the
            # planned x is the measured value (the pear's is x-independent to
            # <= 0.02 mm, OFFSET_TABLE section 8), and the table is identity
            # anyway, so nothing is applied.
            value = isolated[index]["cells"][0.28]
            mean = value
            rule = "measured isolated cell at x=0.28 (no live run for this pool)"
            cells = isolated[index]["cells"]
            live_offsets = []
            live_n = 0
        key = signature(rec["cat"], rec["dia_mm"])
        if key in offsets:
            raise SystemExit(f"{scenario}: duplicate signature {key!r} - the pool "
                             "has two instances the table cannot tell apart")
        applied = 0.0 if identity else round(value, 3)
        offsets[key] = applied
        rows.append({
            "idx": index,
            "signature": key,
            "category": rec["cat"],
            "diameter_mm": round(rec["dia_mm"], 1),
            "grade": rec["grade"],
            "live_n": live_n,
            "live_offsets_mm": live_offsets,
            "live_mean_mm": round(mean, 3),
            "rule": rule,
            "measured_mm": round(value, 3),
            "applied_mm": applied,
            "isolated_mm_at_0.20/0.28/0.36": [round(cells[x], 2) for x in sorted(cells)],
            "wake_mm_at_0.28": round(wake[index]["cells"][0.28], 2) if wake else None,
            "applied_vs_live_mean_mm": round(applied - mean, 2),
            "applied_vs_wake_mm": (
                round(applied - wake[index]["cells"][0.28], 2) if wake else None
            ),
        })
    head = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True, check=False).stdout.strip()
    payload = {
        "schema": "fruit_sorting.release_offsets/v1",
        "scenario": scenario,
        "units": "mm",
        "meaning": "offset = x_delivered - x_spawn for this pool instance "
                   "(applied as x_spawn = planned_x - offset/1000)",
        "identity": bool(identity),
        "note": note,
        "provenance": {
            "phase": "P50 phase 2 (P38b), 2026-10-27",
            "tree_head": head or "unknown",
            "tree_md5": {
                "src/fruit_sorting/fruits.py": md5(os.path.join(ROOT, "src/fruit_sorting/fruits.py")),
                "src/fruit_sorting/meshes.py": md5(os.path.join(ROOT, "src/fruit_sorting/meshes.py")),
                "configs/motion_reference.json": md5(os.path.join(ROOT, "configs/motion_reference.json")),
            },
            "probe_logs": {name: md5(os.path.join(P1, name))
                           for name in (live_log, isolated_log, wake_log) if name},
            "table_rule": "per-instance live mean; >=2 clusters > "
                          f"{MODE_GAP_MM:g} mm apart -> midpoint of the extreme modes "
                          "(PREREG section 2)",
            "measurement": "logs/p50/OFFSET_TABLE.md (sections 2, 4, 7, 8)",
        },
        "rows": rows,
        "offsets": offsets,
    }
    return payload


def write(payload: dict) -> str:
    path = os.path.join(ROOT, "configs", f"release_offsets_{payload['scenario']}.json")
    if os.path.exists(path):
        raise SystemExit(f"{rel(path)} already exists - refusing to overwrite a "
                         "recorded artefact")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")
    return path


def main() -> int:
    accept = build(
        "accept_s5",
        "offset_live_s5.log",
        "offset_probe_s5.log",
        "offset_probe_s5_wake.log",
        identity=False,
        note="the shipped scattered acceptance pool (FRUIT_SUPPLY_SCATTER=1, 16 "
             "instances, SEED=5); offsets are the shipped-condition live values, "
             "compensation ON",
    )
    pear = build(
        "pear_s5",
        None,
        "offset_pear_s5.log",
        None,
        identity=True,
        note="the pear pool (FRUIT_SUPPLY_SPECIES=pear, 16 instances, SEED=5); "
             "IDENTITY by design - the pool has no release tail (-3.33..+2.69 mm, "
             "0.00 % outside [0.180, 0.390] before and after), so this table is the "
             "phase-2 inertness control of the knob path, not a compensation",
    )
    for payload in (accept, pear):
        path = write(payload)
        print(f"[make_offset_table] wrote {rel(path)} ({len(payload['offsets'])} instances)")
        for row in payload["rows"]:
            print(f"  idx {row['idx']:02d} {row['signature']:<14s} "
                  f"live={row['live_offsets_mm']} rule={row['rule']:<34s} "
                  f"applied={row['applied_mm']:+7.2f} mm "
                  f"(vs live mean {row['applied_vs_live_mean_mm']:+5.2f}, "
                  f"vs wake {row['applied_vs_wake_mm']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
