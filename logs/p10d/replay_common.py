#!/usr/bin/env python3
"""P10-D shared offline parser for two-line (FRUIT_BIARM_TWOLINE=1) pick logs.

Tier C: pure text parsing of existing logs, no simulator, no src/ change.
Used by `selection_replay.py` (Task A) and `lockon_attribution.py` (Task B).

What the logs carry (verified against src/fruit_sorting/tasks.py, the tree
pinned by the battery's `00_tree_pins.txt`):

* `[biarm] <arm>: station acquired at t=Xs` - printed *before* the selection in
  the same run-permit segment (tasks.py `_biarm_worker`), so the acquisition
  time **is** the selection time (also the 186 report's definition).
* `[biarm] <arm>: no eligible fruit; station released` - a starved poll
  (selection returned None); no timestamp of its own, but each poll is a
  60-tick (0.5 s) step loop, so it sits between the previous and the next
  acquisition of the same arm.
* `[task] target <fruit> (grade G, S cm) with <arm> arm` - opens an attempt's
  task block at the attempt start (same tick as the acquisition).
* `[task]   wait step=N fruit_y=... fruit_x=... fruit_z=... dy=...` - the
  *chosen* fruit's position at wait-loop entry (step 0) and every tick for the
  first 6 ticks (0.0010 m/tick = 0.12 m/s at 120 Hz; the belt speed), then
  every 400 ticks. `dy = fruit_y - jaw_y` read live, and jaw_y ~ the arm's
  station (left +0.000, right -0.100), so `round(y - dy, 1)` recovers the arm.
* `[task]   intercept handover: fruit_y=... dy=... lead=... queue=N` - the
  handover tick and the queue depth (main-belt fruit in
  `[pick_y-0.05, pick_y+0.45]`, held/parked excluded).
* `[task] fruit at pick point: dy=... arrived=True after N steps` - ticks from
  wait-loop entry to the handover.
* `[task] dynamic descent: waited N ticks, intercept=... (station S, shift
  ...)` - the descent start; the station is printed explicitly.
* `[run] attempt N (arm): picking ... sim=t0-t1s` - the attempt window; t0 ==
  the acquisition time.
* `[cycle] attempt N: prepose=... hover=... ...` - per-attempt segment
  durations, printed at completion; matched to attempts by total duration
  (the 186 convention).

Known measurement limit (stated in SELECTION_REPLAY.md): positions are printed
only for the *selected* fruit. Fruit that are never selected (grade C under
pure routing, or lane fruit that pass while the arm is busy) have no logged
position, so the full candidate set at a selection instant is NOT
reconstructible from the logs; the replay uses the chosen-fruit geometry plus
the handover queue counts, with that caveat.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

BELT_V = 0.12  # m/s, |belt speed| (scatter scenario; confirmed by the wait rows)
TICK = 1.0 / 120.0
STARVED_POLL_S = 0.5  # 60-tick step loop per starved slot
FEED_GAP_S = 0.25  # 30-tick feed gap between attempts (FRUIT_BIARM_GAP_TICKS=30)
STATION = {"left": 0.0, "right": -0.1}

RE_ACQ = re.compile(r"\[biarm\] (?P<arm>\w+): station acquired at t=(?P<t>[\d.]+)s")
RE_NOEL = re.compile(r"\[biarm\] (?P<arm>\w+): no eligible fruit")
RE_RESULT = re.compile(
    r"\[biarm\] result (?P<arm>\w+) index=(?P<index>\d+) (?P<fruit>\w+) "
    r"grasped=(?P<grasped>True|False) placed=(?P<placed>True|False) "
    r"lift=(?P<lift>[+\-\d.]+) force=(?P<force>[\d.]+) sim=(?P<span>[\d.]+)s "
    r"notes=(?P<notes>\[.*\])"
)
RE_PICK = re.compile(
    r"\[run\] attempt (?P<slot>\d+) \((?P<arm>\w+)\): picking (?P<fruit>\w+) "
    r"grade (?P<grade>\w+) into output lane (?P<lane>\d+) at "
    r"\((?P<x>[-\d.]+), (?P<y>[+\-\d.]+)\) sim=(?P<t0>[\d.]+)-(?P<t1>[\d.]+)s"
)
RE_OUTCOME = re.compile(
    r"\[run\] attempt (?P<slot>\d+) \((?P<arm>\w+)\): grasped=(?P<grasped>True|False) "
    r"placed=(?P<placed>True|False) lift=(?P<lift>[+\-\d.]+) m "
    r"force=(?P<force>[\d.]+) N sim=(?P<span>[\d.]+)s notes=(?P<notes>\[.*\])"
)
RE_TARGET = re.compile(
    r"\[task\] target (?P<fruit>\w+) \(grade (?P<grade>\w+), (?P<cm>[\d.]+) cm\) "
    r"with (?P<arm>\w+) arm"
)
RE_WAIT = re.compile(
    r"\[task\]   wait step=(?P<step>\d+) fruit_y=(?P<y>[-\d.]+) "
    r"fruit_x=(?P<x>[+\-\d.]+) fruit_z=(?P<z>[-\d.]+) dy=(?P<dy>[+\-\d.]+)"
)
RE_HANDOVER = re.compile(
    r"\[task\]   intercept handover: fruit_y=(?P<y>[-\d.]+) dy=(?P<dy>[+\-\d.]+) "
    r"m lead=(?P<lead>[\d.]+) m at (?P<v>[+\-\d.]+) m/s .*queue=(?P<queue>\d+)"
)
RE_PICKPOINT = re.compile(
    r"\[task\] fruit at pick point: dy=(?P<dy>[+\-\d.]+) m arrived=(?P<arrived>\w+) "
    r"after (?P<steps>\d+) steps"
)
RE_DESCENT = re.compile(
    r"\[task\] dynamic descent: waited (?P<waited>\d+) ticks, intercept=(?P<intercept>[+\-\d.]+) m "
    r"\(station (?P<station>[+\-\d.]+), shift (?P<shift>[+\-\d.]+) m\), "
    r"fruit dy=(?P<dy>[+\-\d.]+) m, deadline=(?P<deadline>[+\-\d.]+) m, "
    r"t_desc=(?P<t_desc>[\d.]+) s"
)
RE_CYCLE = re.compile(
    r"\[cycle\] attempt (?P<n>\d+): (?P<body>.*?) total=(?P<total>[\d.]+)s"
)
RE_CYCLE_SEG = re.compile(r"(?P<name>\w+)=(?P<dur>[\d.]+)s")


def _station_of(y: float, dy: float) -> float:
    """Recover the arm's station from a wait/handover row: station = y - dy."""
    return round((y - dy) * 10.0) / 10.0


def arm_of_station(station: float) -> str:
    return "left" if abs(station) < 0.05 else "right"


@dataclass
class Block:
    """One attempt's task block: the chosen fruit's logged geometry."""

    arm: str = ""
    fruit: str = ""
    grade: str = ""
    cm: float = 0.0
    waits: list[dict] = field(default_factory=list)
    handover: dict | None = None
    pickpoint: dict | None = None
    descent: dict | None = None


@dataclass
class Attempt:
    """One `[run]` attempt window plus its matched cycle marks and block."""

    slot: int
    arm: str
    fruit: str
    grade: str
    lane: int
    t0: float
    t1: float
    placed: bool | None = None
    grasped: bool | None = None
    notes: str = ""
    blocks: dict | None = None  # prepose/hover/... from the [cycle] line
    cycle_total: float | None = None
    block: Block | None = None

    @property
    def span(self) -> float:
        return self.t1 - self.t0

    @property
    def t_wait(self) -> float | None:
        """Wait-loop entry: t0 + prepose + hover (the [cycle] marks)."""
        if not self.blocks:
            return None
        return self.t0 + self.blocks.get("prepose", 0.0) + self.blocks.get("hover", 0.0)

    @property
    def station(self) -> float:
        return STATION[self.arm]


@dataclass
class LogData:
    path: str
    attempts: list[Attempt] = field(default_factory=list)  # per-arm start order
    acquisitions: list[tuple[float, str]] = field(default_factory=list)
    starved: list[tuple[str, int]] = field(default_factory=list)  # (arm, log order)
    results: list[dict] = field(default_factory=list)
    blocks: list[Block] = field(default_factory=list)  # log order
    cycles: list[dict] = field(default_factory=list)
    summary: dict | None = None


def _match_cycles(attempts: list[Attempt], cycles: list[dict], tol: float = 0.35) -> int:
    """Attach the closest-duration cycle line to each attempt (186 convention)."""
    pending = list(cycles)
    matched = 0
    for att in attempts:
        best_i, best_d = None, tol
        for i, cyc in enumerate(pending):
            d = abs(cyc["total"] - att.span)
            if d < best_d:
                best_i, best_d = i, d
        if best_i is None:
            continue
        cyc = pending.pop(best_i)
        att.blocks = dict(cyc["segs"])
        att.cycle_total = cyc["total"]
        matched += 1
    return len(attempts) - matched


def parse(path: str) -> LogData:
    data = LogData(path=path)
    #: Two-line logs interleave the two arms' `[task]` rows (the wait loops of
    #: both arms run concurrently), so a block is NOT "the rows after its
    #: target line". The target line names its arm explicitly and the per-arm
    #: target order equals the per-arm attempt order; wait rows are grouped
    #: into runs by the arm implied by their station (`round(y - dy, 1)`), and
    #: run k of an arm belongs to that arm's target k. Handover/descent rows
    #: carry the station too; the pickpoint follows its handover in log order.
    targets: dict[str, list[Block]] = {"left": [], "right": []}
    wait_rows: dict[str, list[dict]] = {"left": [], "right": []}
    last_handover_arm: str = "left"
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            m = RE_ACQ.search(line)
            if m:
                data.acquisitions.append((float(m.group("t")), m.group("arm")))
                continue
            m = RE_NOEL.search(line)
            if m:
                data.starved.append((m.group("arm"), len(data.starved)))
                continue
            m = RE_RESULT.search(line)
            if m:
                d = m.groupdict()
                data.results.append(
                    {
                        "arm": d["arm"],
                        "index": int(d["index"]),
                        "fruit": d["fruit"],
                        "grasped": d["grasped"] == "True",
                        "placed": d["placed"] == "True",
                        "span": float(d["span"]),
                        "notes": d["notes"],
                    }
                )
                continue
            m = RE_PICK.search(line)
            if m:
                d = m.groupdict()
                data.attempts.append(
                    Attempt(
                        slot=int(d["slot"]),
                        arm=d["arm"],
                        fruit=d["fruit"],
                        grade=d["grade"],
                        lane=int(d["lane"]),
                        t0=float(d["t0"]),
                        t1=float(d["t1"]),
                    )
                )
                continue
            m = RE_OUTCOME.search(line)
            if m:
                d = m.groupdict()
                for att in data.attempts:
                    if att.slot == int(d["slot"]) and att.arm == d["arm"]:
                        att.grasped = d["grasped"] == "True"
                        att.placed = d["placed"] == "True"
                        att.notes = d["notes"]
                        break
                continue
            m = RE_TARGET.search(line)
            if m:
                d = m.groupdict()
                arm = d["arm"]
                targets.setdefault(arm, []).append(
                    Block(arm=arm, fruit=d["fruit"], grade=d["grade"], cm=float(d["cm"]))
                )
                cur_run = None
                cur_run_station = None
                continue
            m = RE_WAIT.search(line)
            if m:
                d = m.groupdict()
                y, dy = float(d["y"]), float(d["dy"])
                station = _station_of(y, dy)
                wait_rows.setdefault(arm_of_station(station), []).append(
                    {
                        "step": int(d["step"]),
                        "y": y,
                        "x": float(d["x"]),
                        "z": float(d["z"]),
                        "dy": dy,
                        "station": station,
                    }
                )
                continue
            m = RE_HANDOVER.search(line)
            if m:
                d = m.groupdict()
                station = _station_of(float(d["y"]), float(d["dy"]))
                arm = arm_of_station(station)
                blk = _find_block(targets[arm], want="handover")
                if blk is not None:
                    blk.handover = {
                        "y": float(d["y"]),
                        "dy": float(d["dy"]),
                        "lead": float(d["lead"]),
                        "queue": int(d["queue"]),
                    }
                    last_handover_arm = arm
                continue
            m = RE_PICKPOINT.search(line)
            if m:
                d = m.groupdict()
                blk = _find_block(targets[last_handover_arm], want="pickpoint")
                if blk is not None:
                    blk.pickpoint = {
                        "dy": float(d["dy"]),
                        "steps": int(d["steps"]),
                    }
                continue
            m = RE_DESCENT.search(line)
            if m:
                d = m.groupdict()
                station = round(float(d["station"]) * 10.0) / 10.0
                arm = arm_of_station(station)
                blk = _find_block(targets[arm], want="descent")
                if blk is not None:
                    blk.descent = {
                        "waited": int(d["waited"]),
                        "station": station,
                        "dy": float(d["dy"]),
                        "t_desc": float(d["t_desc"]),
                    }
                continue
            m = RE_CYCLE.search(line)
            if m:
                data.cycles.append(
                    {
                        "n": int(m.group("n")),
                        "total": float(m.group("total")),
                        "segs": {
                            s.group("name"): float(s.group("dur"))
                            for s in RE_CYCLE_SEG.finditer(m.group("body"))
                        },
                    }
                )
                continue
    # group each arm's wait rows into runs (step resets to 0 for a new attempt;
    # the two arms' rows interleave tick-by-tick, and a station flip from a few
    # mm of jaw drift must NOT split a run - grouping is per arm by step order)
    for arm in ("left", "right"):
        rows = wait_rows.get(arm, [])
        runs: list[list[dict]] = []
        for row in rows:
            if not runs or row["step"] <= runs[-1][-1]["step"]:
                runs.append([])
            runs[-1].append(row)
        for blk, run in zip(targets.get(arm, []), runs):
            blk.waits = run
    # flatten the per-arm target order back into one list (log order of the
    # first row of each block is not tracked; the per-arm order is what the
    # report uses, plus the block index in `data.blocks`)
    data.blocks = targets.get("left", []) + targets.get("right", [])
    # match attempts -> blocks per arm (both are per-arm sequential)
    for arm in ("left", "right"):
        arm_attempts = sorted(
            (a for a in data.attempts if a.arm == arm), key=lambda a: a.t0
        )
        arm_blocks = [b for b in data.blocks if b.arm == arm]
        for att, blk in zip(arm_attempts, arm_blocks):
            att.block = blk
    _match_cycles(data.attempts, data.cycles)
    return data


def _find_block(blocks: list[Block], want: str) -> Block | None:
    """Most recent block in the (per-arm) list missing its `want` field."""
    for blk in reversed(blocks):
        if getattr(blk, want) is None:
            return blk
    return None


def starved_instants(data: LogData) -> list[tuple[str, float]]:
    """Approximate selection times of the starved polls.

    Each starved slot is a 60-tick (0.5 s) step loop after its own acquisition;
    walking the log order, a `no eligible` row belongs to the acquisition that
    preceded it (same arm) with no acquisition of that arm in between, and the
    next acquisition of that arm follows ~0.5 s later. The instant reported is
    the acquisition time of the starved poll (the selection instant).
    """
    events: list[tuple[str, float, str]] = []  # (kind, t, arm) in log order
    for t, arm in data.acquisitions:
        events.append(("acq", t, arm))
    # the starved rows carry no time; interleave them by log order using the
    # acquisition stream: rebuild by walking the file again in order
    events = _ordered_events(data.path)
    out: list[tuple[str, float]] = []
    last_acq: dict[str, float] = {}
    for kind, t, arm in events:
        if kind == "acq":
            last_acq[arm] = t
        elif kind == "starved":
            if arm in last_acq:
                out.append((arm, last_acq[arm]))
    return out


def _ordered_events(path: str) -> list[tuple[str, float, str]]:
    events: list[tuple[str, float, str]] = []
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            m = RE_ACQ.search(line)
            if m:
                events.append(("acq", float(m.group("t")), m.group("arm")))
                continue
            m = RE_NOEL.search(line)
            if m:
                events.append(("starved", float("nan"), m.group("arm")))
    return events
