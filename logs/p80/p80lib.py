"""P80 shared parsing: the throughput endpoints of one scripted log.

Read-only. It borrows `scripts/186_w6_report.py`'s parser (the W6/P33 metric
definitions) rather than re-deriving them, and adds only what 186 does not
print: the wall side (from `*.stamps`), the `s/attempt` summary figure, and the
grasp/place class split.

Definitions, fixed in `logs/p80/PREREG.md`:
* a placement is the attempt's `t1` (186's convention);
* the **placement window** is `t_last_place - t_first_place`, so the steady-state
  rate is `60 / pooled_interval_mean` (186's own identity, quoted by P3);
* the **batch span** is `t_last_end - t_first_start`;
* the wall is `[run] attempt 0` -> `[fruit] DONE` on the stamp stream.
"""

from __future__ import annotations

import importlib.util
import os
import re
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
_spec = importlib.util.spec_from_file_location(
    "w6", os.path.join(ROOT, "scripts/186_w6_report.py"))
w6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(w6)

STATS = re.compile(
    r"\[stats\] attempts=(?P<att>\d+) successes=(?P<ok>\d+) diverted=(?P<div>\d+) "
    r"success_rate=(?P<rate>\d+)% sim=(?P<sim>[\d.]+)s total, (?P<per>[\d.]+)s/attempt")
BIARM = re.compile(
    r"\[biarm\] (?P<slots>\d+) pipelined slots, (?P<att>\d+) attempts, "
    r"(?P<ok>\d+) successes, (?P<span>[\d.]+)s sim span, "
    r"(?P<per>[\d.]+)s/attempt, (?P<per_ok>[\d.]+)s/success, "
    r"(?P<rate>[\d.]+) fruits/min; per arm left=(?P<l>\d+)/(?P<la>\d+) "
    r"right=(?P<r>\d+)/(?P<ra>\d+)")
STAMP_RUN = re.compile(r"\s\[fruit\] \[run\] attempt 0[: (]")
STAMP_ACQ = re.compile(r"\s\[fruit\] \[biarm\] (?:left|right): station acquired at t=")
STAMP_DONE = re.compile(r"\s\[fruit\] DONE")
#: The `[run] summary` block (`scripts/20_pick_place.py`): one row per executed
#: attempt **in attempt order**, carrying the arm the line actually used. On the
#: single-arm line the `[run]` row itself has no arm, so this is the only place
#: the left/right split is recorded - and the split is what the pooled rate
#: mixes (P59 P3 / P43: the pooled number is an arm-mix artifact).
SUMMARY_ROW = re.compile(
    r"(?P<fruit>\w+)\s+arm=(?P<arm>\w+)\s+grasped=(?P<grasped>True|False)\s+"
    r"placed=(?P<placed>True|False)\s+lift=(?P<lift>[+\-\d.]+)\s+"
    r"N=(?P<force>[\d.]+)\s+sim=(?P<sim>[\d.]+)s")
APP_CLOCK = re.compile(r"^\[(\d+\.\d+)s\] Simulation App Shutting Down", re.M)


def _mean(v):
    return st.fmean(v) if v else None


def _p90(v):
    if not v:
        return None
    s = sorted(v)
    return s[min(len(s) - 1, int(0.9 * len(s)))]


def _median(v):
    return st.median(v) if v else None


def rows_of(path: str) -> list[dict]:
    data = w6.parse(path)
    return [dict(row, slot=slot) for slot, row in sorted(data["attempts"].items())]


def metrics(path: str) -> dict:
    """Every endpoint P80 reads from one log (plus its optional stamp file)."""
    data = w6.parse(path)
    rows = rows_of(path)
    real = [r for r in rows if not r.get("no_fruit")]
    timed = [r for r in real if r.get("t0", 0.0) > 0.0 and r.get("t1", 0.0) > 0.0]
    placed = [r for r in real if r.get("placed")]
    placed_t = sorted(r["t1"] for r in placed if "t1" in r)
    pooled = [b - a for a, b in zip(placed_t, placed_t[1:])]
    arms = sorted({r["arm"] for r in timed})
    per_arm = {}
    for arm in arms:
        marks = sorted(r["t1"] for r in placed if r["arm"] == arm and "t1" in r)
        gaps = [b - a for a, b in zip(marks, marks[1:])]
        arm_rows = [r for r in timed if r["arm"] == arm]
        placed_arm = sum(1 for r in arm_rows if r.get("placed"))
        idle = 0.0
        for previous, current in zip(arm_rows, arm_rows[1:]):
            idle += max(0.0, current["t0"] - previous["t1"])
        span = (arm_rows[-1]["t1"] - arm_rows[0]["t0"]) if len(arm_rows) > 1 else 0.0
        per_arm[arm] = {
            "placed": placed_arm,
            "attempts": len(arm_rows),
            "intervals": gaps,
            "interval_mean": _mean(gaps),
            "interval_p90": _p90(gaps),
            "idle_frac": (idle / span) if span > 0 else None,
        }
    batch_span = (max(r["t1"] for r in timed) - min(r["t0"] for r in timed)) if timed else None
    window = (placed_t[-1] - placed_t[0]) if len(placed_t) > 1 else None
    stats = {"per_attempt": None, "sim_total": None, "pl_ok": None, "pl_att": None,
             "biarm": None, "wall": None, "wall_per_pick": None, "wall_over_sim": None,
             "app_clock": None}
    with open(path, encoding="utf-8", errors="ignore") as fh:
        text = fh.read()
    m = STATS.search(text)
    if m:
        stats.update(per_attempt=float(m.group("per")), sim_total=float(m.group("sim")),
                     pl_ok=int(m.group("ok")), pl_att=int(m.group("att")))
    m = BIARM.search(text)
    if m:
        stats["biarm"] = {k: (float(v) if k not in ("slots", "att", "ok", "l", "la", "r", "ra")
                              else int(v)) for k, v in m.groupdict().items()}
    stamps = os.path.splitext(path)[0] + ".stamps"
    if os.path.exists(stamps):
        first = done = None
        with open(stamps, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                elapsed = float(line.split(None, 1)[0])
                if STAMP_RUN.search(line) or STAMP_ACQ.search(line):
                    first = elapsed if first is None else min(first, elapsed)
                elif STAMP_DONE.search(line):
                    done = elapsed
        if first is not None and done is not None:
            stats["wall"] = done - first
            stats["wall_per_pick"] = stats["wall"] / len(real) if real else None
            if batch_span:
                stats["wall_over_sim"] = stats["wall"] / batch_span
    m = APP_CLOCK.search(text)
    if m:
        stats["app_clock"] = float(m.group(1))
    classes = {}
    for r in real:
        if r.get("placed"):
            key = "placed"
        elif r.get("grasped"):
            key = "carried-not-placed"
        elif r.get("grasped") is False:
            key = "never-grasped"
        else:
            key = "unknown"
        classes[key] = classes.get(key, 0) + 1
    reasons = {}
    for r in real:
        if r.get("placed"):
            continue
        reason = w6._first_reason(r.get("notes", "") or "")
        if reason == "-":
            reason = "grasped, not placed (no note)" if r.get("grasped") else "no grasp (no note)"
        reasons[reason] = reasons.get(reason, 0) + 1
    starved = sum(1 for r in rows if r.get("no_fruit"))
    # the summary block: one row per executed attempt, in attempt order, with the
    # arm the line used - the single-arm `[run]` rows carry no arm of their own.
    summary_rows = []
    for line in text.splitlines():
        m = SUMMARY_ROW.search(line)
        if m:
            summary_rows.append(
                {"fruit": m.group("fruit"), "arm": m.group("arm"),
                 "grasped": m.group("grasped") == "True",
                 "placed": m.group("placed") == "True",
                 "focus": float(m.group("force"))})
    arm_split = {}
    ordered = [r for r in rows if not r.get("no_fruit")]
    for row, summ in zip(ordered, summary_rows):
        row["arm_line"] = summ["arm"]
        row["focus"] = summ["focus"]
        cell = arm_split.setdefault(summ["arm"], {"attempts": 0, "placed": 0})
        cell["attempts"] += 1
        cell["placed"] += 1 if summ["placed"] else 0
    for cell in arm_split.values():
        cell["rate"] = cell["placed"] / cell["attempts"] if cell["attempts"] else None
    return {
        "path": path,
        "attempts": len(real),
        "placed": len(placed),
        "rate": (len(placed) / len(real)) if real else None,
        "pending_slots": starved,
        "pooled": {
            "n": len(pooled),
            "mean": _mean(pooled),
            "p50": _median(pooled),
            "p90": _p90(pooled),
            "min": min(pooled) if pooled else None,
            "max": max(pooled) if pooled else None,
        },
        "per_arm": per_arm,
        "batch_span": batch_span,
        "window": window,
        "window_rate": (60.0 / _mean(pooled)) if pooled else None,
        "batch_rate": (60.0 * len(placed) / batch_span) if batch_span else None,
        "classes": classes,
        "reasons": reasons,
        "arm_split": arm_split,
        "stats": stats,
        "lock_on": _lock_on(timed),
    }


def standardised_rate(m: dict, mix: dict) -> dict:
    """`m`'s placed rate re-weighted to `mix` ({arm: share}), and the audit.

    The pooled placed rate of the scripted line mixes the arms by the *supply
    draw* (grade A -> left), so a pooled count difference between two arms can be
    a different mix rather than a different per-arm rate (P43/P59). This
    re-weights each arm's own rate to the reference mix and prints the share it
    moved, so the reader can see which of the two it is.
    """
    total = sum(mix.values()) or 1.0
    shares = {arm: n / total for arm, n in mix.items()}
    out = {"shares": shares, "rate": None, "cells": {}}
    acc = 0.0
    for arm, share in shares.items():
        cell = m["arm_split"].get(arm)
        rate = cell["rate"] if cell else None
        out["cells"][arm] = {"share": share, "rate": rate,
                             "attempts": cell["attempts"] if cell else 0}
        if rate is None:
            return out
        acc += share * rate
    out["rate"] = acc
    return out


def _lock_on(timed: list[dict]) -> dict:
    """Per-arm lock-on (previous attempt end -> station acquired), two-line only."""
    out = {}
    for arm in sorted({r["arm"] for r in timed if r.get("acq") is not None}):
        rows = sorted((r for r in timed if r["arm"] == arm and r.get("acq") is not None),
                      key=lambda r: r["t0"])
        gaps = [cur["acq"] - prev["t1"] for prev, cur in zip(rows, rows[1:])]
        retries = [cur.get("retries", 0) for cur in rows[1:]]
        out[arm] = {"mean": _mean(gaps), "p50": _median(gaps), "p90": _p90(gaps),
                    "n": len(gaps), "retries_total": sum(retries)}
    return out


def fmt(v, nd=2):
    return "n/a" if v is None else f"{v:.{nd}f}"
