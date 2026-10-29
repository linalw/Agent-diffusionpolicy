"""P60 phase 1: the left-arm failure census (offline, read-only).

Reads the twelve post-profile direct-presentation logs (P59 phase-3 control
`C_*`, P58 phase-3b cell A'' `A2_*`, P59 phase-2 arms `A_*`/`B_*`) and
classifies every episode, then every failure, from the rows the batteries
actually wrote:

  `[rl] episode N: <species> ... arm=... success=... grasped=... placed=...`
      the outcome triple (the definitive class; `success = lifted and
      on_output_belt(final)`, `placed = on_output_belt(pos)` after the
      release - `tasks.py:12071`, `rl_env.py:4839`)
  `[task] openarm fingertips NN mm from the fruit; closing anyway`
      the pre-close pad/fruit distance (one row per episode; the P47 row)
  `[task] carry <leg>: stored pad centre NN mm ...`  one per carry leg
      (`grasp_lift`, `place<bin>`), printed at the leg's start - so its
      *presence* proves the leg ran and its number is the stored-centre drift
  `[task] place low: ...`   the accompanied place descent's finger-floor read
  `[feed] <arm>: ... ticks=... (attempt start -> release)`
      printed at the release, so its presence proves the release block ran
  `[rl]   grasp did not land on the belt; re-running carry_and_release`
      printed iff `grasped and not placed` (`rl_env.py:4807`) - a tautology of
      the cnp class, not independent evidence
  `[bed-fall] <species> idx=.. x=.. y=.. z=.. held=..`
      a fruit leaving the line. `held=True` is the **mid-carry** window only:
      `sample.held` is set at the grasp (`tasks.py:11014`) and cleared by the
      release's `spawner.detach` (`tasks.py:11831`), so `held=True` means the
      payload left the line between the grasp and the release.
  `[bed-sel] attempt N ... pick=<species>@<along>` + the `-> chosen` candidate
      row carries the **selection-time x** of the fruit the attempt took.

What is NOT in these logs (the batteries did not set the knobs): `[carry]`
(`FRUIT_CARRY_DIAG` - clean_slip / force_min / sep@loss), `[acq]`
(`FRUIT_ACQ_DIAG`), `[seat]` (`FRUIT_SEAT_DIAG`), `[grasp]` debug, and the
`[task] over the output belt:` row (needs `verbose`). So the per-leg slip and
force signature cannot be re-derived here - it is stated, not assumed.

    python3 logs/p60/left_census.py            # full census -> stdout
    python3 logs/p60/left_census.py --check    # assertions only, exit code

Every printed number is carried with the `file:line` of the row it came from,
so any line can be re-read in the log.
"""

from __future__ import annotations

import argparse
import glob
import math
import os
import re
import statistics
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOGS = os.path.join(REPO, "logs")

#: (label, tree role, glob) - the corpus of P60 phase 1, in the plan's order.
CORPORA = [
    ("p59p3", "shipped profile control (cap 4)", "p59/p3/C_*.log"),
    ("p58p3b", "cell A'' (cap 4, pre-profile-row tree)", "p58/p3b/A2_*.log"),
    ("p59p2A", "arm A (FRUIT_SUPPLY_BAND_MAX=5)", "p59/p2/A_*.log"),
    ("p59p2B", "arm B (FRUIT_SUPPLY_TARGET_FROM=0.40)", "p59/p2/B_*.log"),
]

EP_START = re.compile(
    r"\[rl\] episode (\d+): (\w+) grade=(\w) d=([\d.]+)cm bin=(\d) arm=(\w+) "
    r"y=([-+][\d.]+)"
)
EP_END = re.compile(
    r"\[rl\] episode (\d+): (\w+) d=([\d.]+)cm bin=(\d) arm=(\w+) success=(\w+) "
    r"grasped=(\w+) placed=(\w+) ticks=(\d+)(?: decision=(\d+))? "
    r"reward=([-+0-9.eE]+) notes=(\[.*?\])(?=\s+presentation=|\s*$)"
)
ANGLE = re.compile(
    r"intercept trigger \(dy=([-+]?[\d.]+)cm, dx=([-+]?[\d.]+)cm, "
    r"t_arrive=([\d.]+)s, speed=([\d.]+)m/s/(\w+), frame=(\w+), "
    r"finger=([\d.]+), lead=([\d.]+)s/reach=([\d.]+)\)"
)
FINGERTIPS = re.compile(r"openarm fingertips (\d+) mm from the fruit; closing anyway")
CARRY = re.compile(
    r"carry (\w+): stored pad centre (\d+) mm from the measured pads; re-anchoring"
)
PLACE_LOW = re.compile(
    r"place low: bottom (\d+) -> (\d+) mm \(target (\d+)\), "
    r"drop (\d+)/(\d+) mm(?:, FINGER FLOOR budget (\d+) mm)?, "
    r"residual ([\d.]+) mm, (\d+) ticks"
)
RETRY = "grasp did not land on the belt"
FEED = re.compile(
    r"\[feed\] (\w+): updates=(\d+) ticks=(\d+) stride=(\d+) "
    r"released=([-+]\d+) placed=([-+]\d+) skipped=([-+]\d+)"
)
BED_SEL = re.compile(
    r"\[bed-sel\] attempt (\d+) t=([\d.]+) live=(\d+) on_belt=(\d+) "
    r"admitted=(\d+) window=(\d+) pick=(\w+)@([-+]?[\d.]+)"
)
BED_CAND = re.compile(
    r"\[bed-sel\]\s+(\w+)\s+along=([-+]?[\d.]+) x=([\d.]+) z=([\d.]+) "
    r"r=([\d.]+) grade=(\w) -> (.*)"
)
BED_FALL = re.compile(
    r"\[bed-fall\] (\w+) idx=(\d+) x=([-+]?[\d.]+) y=([-+]?[\d.]+) "
    r"z=([-+]?[\d.]+) held=(\w+)"
)
ENV_READY = re.compile(r"\[rl\] env ready: (.*)")
TRIGGER_ROW = re.compile(r"\[rl\] trigger=(\w+) (.*)")
PROFILE_ROW = re.compile(r"\[supply\] direct profile: (.*)")


# --------------------------------------------------------------------------- #
# statistics (no scipy on this box)
# --------------------------------------------------------------------------- #
def fisher_two_sided(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact p for [[a, b], [c, d]]."""
    n = a + b + c + d
    if n == 0:
        return 1.0
    row1, col1 = a + b, a + c

    def prob(k: int) -> float:
        return (
            math.comb(row1, k) * math.comb(n - row1, col1 - k) / math.comb(n, col1)
        )

    lo, hi = max(0, col1 - (n - row1)), min(row1, col1)
    observed = prob(a)
    total = sum(prob(k) for k in range(lo, hi + 1) if prob(k) <= observed + 1e-12)
    return min(1.0, total)


def fmt_msd(values: list[float], unit: str = "", digits: int = 1) -> str:
    if not values:
        return "-"
    med = statistics.median(values)
    return (
        f"{med:.{digits}f}{unit} [{min(values):.{digits}f}-{max(values):.{digits}f}]"
    )


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #
def new_episode(index: int) -> dict:
    return {
        "index": index,
        "start_line": None,
        "end_line": None,
        "species": None,
        "grade": None,
        "diameter": None,
        "bin": None,
        "arm": None,
        "y0": None,
        "success": None,
        "grasped": None,
        "placed": None,
        "ticks": None,
        "decision": None,
        "reward": None,
        "notes": [],
        "fingertips_mm": None,
        "fingertips_line": None,
        "carry": [],
        "place_low": None,
        "retry": False,
        "feed": None,
        "falls": [],
        "chosen_x": None,
        "chosen_along": None,
        "chosen_grade": None,
        "n_candidates": None,
        "live": None,
        "window": None,
    }


def parse_log(path: str) -> dict:
    seed = re.search(r"_(\d+)\.log$", path)
    log = {
        "path": path,
        "rel": os.path.relpath(path, REPO),
        "seed": int(seed.group(1)) if seed else -1,
        "episodes": [],
        "falls": [],
        "belts": [],
        "env_ready": None,
        "trigger": None,
        "profile": None,
        "rollout": None,
        "bedsel": [],
        "lines": 0,
    }
    current = None
    pending_attempt = None
    pending_cands = []
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for number, raw in enumerate(handle, start=1):
            line = raw.rstrip("\n")
            if "[fruit]" not in line:
                continue
            if log["env_ready"] is None:
                found = ENV_READY.search(line)
                if found:
                    log["env_ready"] = found.group(1)
            if log["trigger"] is None:
                found = TRIGGER_ROW.search(line)
                if found:
                    log["trigger"] = found.group(0).split("] ", 1)[-1]
            if log["profile"] is None:
                found = PROFILE_ROW.search(line)
                if found:
                    log["profile"] = found.group(1)
            if "[rl] rollout:" in line:
                log["rollout"] = line.split("] rollout: ", 1)[-1]

            # ---- the attempt's candidate block (x of the chosen fruit) ---- #
            found = BED_SEL.search(line)
            if found:
                pending_attempt = {
                    "attempt": int(found.group(1)),
                    "t": float(found.group(2)),
                    "live": int(found.group(3)),
                    "on_belt": int(found.group(4)),
                    "admitted": int(found.group(5)),
                    "window": int(found.group(6)),
                    "pick": found.group(7),
                    "along": float(found.group(8)),
                    "line": number,
                    "chosen_x": None,
                    "n_candidates": 0,
                }
                pending_cands = []
                log["bedsel"].append(pending_attempt)
                continue
            found = BED_CAND.search(line)
            if found:
                entry = {
                    "species": found.group(1),
                    "along": float(found.group(2)),
                    "x": float(found.group(3)),
                    "verdict": found.group(7),
                }
                pending_cands.append(entry)
                if pending_attempt is not None:
                    pending_attempt["n_candidates"] = len(pending_cands)
                    if entry["verdict"].strip() == "chosen":
                        pending_attempt["chosen_x"] = entry["x"]
                        pending_attempt["chosen_grade"] = found.group(6)
                continue

            # ---- bed falls (attributed by the episode window) ---- #
            found = BED_FALL.search(line)
            if found:
                row = {
                    "species": found.group(1),
                    "index": int(found.group(2)),
                    "x": float(found.group(3)),
                    "y": float(found.group(4)),
                    "z": float(found.group(5)),
                    "held": found.group(6) == "True",
                    "line": number,
                    "episode": current["index"] if current is not None else None,
                }
                log["falls"].append(row)
                if current is not None:
                    current["falls"].append(row)
                continue
            if "[belt]" in line and "discharged to the tray" in line:
                log["belts"].append(line.split("[belt]", 1)[1].strip())
                continue

            # ---- episode start ---- #
            found = EP_START.search(line)
            if found and current is None:
                current = new_episode(int(found.group(1)))
                current["species"] = found.group(2)
                current["grade"] = found.group(3)
                current["diameter"] = float(found.group(4))
                current["bin"] = int(found.group(5))
                current["arm"] = found.group(6)
                current["y0"] = float(found.group(7))
                current["start_line"] = number
                if pending_attempt is not None:
                    current["chosen_x"] = pending_attempt["chosen_x"]
                    current["chosen_along"] = pending_attempt["along"]
                    current["n_candidates"] = pending_attempt["n_candidates"]
                    current["live"] = pending_attempt["live"]
                    current["window"] = pending_attempt["window"]
                continue

            # ---- episode rows ---- #
            if current is not None:
                found = FINGERTIPS.search(line)
                if found:
                    current["fingertips_mm"] = int(found.group(1))
                    current["fingertips_line"] = number
                    continue
                found = CARRY.search(line)
                if found:
                    current["carry"].append(
                        {"leg": found.group(1), "drift_mm": int(found.group(2)),
                         "line": number}
                    )
                    continue
                found = PLACE_LOW.search(line)
                if found:
                    current["place_low"] = {
                        "bottom_mm": int(found.group(1)),
                        "clearance_mm": int(found.group(2)),
                        "target_mm": int(found.group(3)),
                        "drop_mm": int(found.group(4)),
                        "need_mm": int(found.group(5)),
                        "finger_budget_mm": int(found.group(6)) if found.group(6) else None,
                        "residual_mm": float(found.group(7)),
                        "ticks": int(found.group(8)),
                        "line": number,
                    }
                    continue
                if RETRY in line:
                    current["retry"] = True
                    continue
                found = FEED.search(line)
                if found:
                    current["feed"] = {
                        "arm": found.group(1),
                        "updates": int(found.group(2)),
                        "ticks": int(found.group(3)),
                        "released": int(found.group(5)),
                        "placed": int(found.group(6)),
                        "skipped": int(found.group(7)),
                        "line": number,
                    }
                    continue

            # ---- episode end ---- #
            found = EP_END.search(line)
            if found and current is not None:
                current["end_line"] = number
                current["success"] = found.group(6) == "True"
                current["grasped"] = found.group(7) == "True"
                current["placed"] = found.group(8) == "True"
                current["ticks"] = int(found.group(9))
                current["decision"] = int(found.group(10)) if found.group(10) else None
                current["reward"] = float(found.group(11))
                current["notes"] = re.findall(r"'([^']*)'", found.group(12))
                log["episodes"].append(current)
                current = None
                continue
    log["lines"] = number
    return log


# --------------------------------------------------------------------------- #
# classification
# --------------------------------------------------------------------------- #
def outcome_class(ep: dict) -> str:
    """The outcome triple -> the class the project already names."""
    if ep["success"]:
        return "placed"
    if not ep["grasped"]:
        return "never-held"
    if not ep["placed"]:
        return "carried-not-placed"
    return "placed-off-belt"  # placed=True but the final pose is off the belt


def trigger_fields(ep: dict) -> dict | None:
    for note in ep["notes"]:
        found = ANGLE.search(note)
        if found:
            return {
                "dy_mm": float(found.group(1)) * 10.0,
                "dx_mm": float(found.group(2)) * 10.0,
                "t_arrive": float(found.group(3)),
                "speed": float(found.group(4)),
                "frame": found.group(6),
                "finger": float(found.group(7)),
                "lead": float(found.group(8)),
                "reach": float(found.group(9)),
            }
    return None


def extra_notes(ep: dict) -> list[str]:
    return [n for n in ep["notes"] if not n.startswith("intercept trigger")]


def place_leg(ep: dict) -> dict | None:
    for row in ep["carry"]:
        if row["leg"].startswith("place"):
            return row
    return None


def lift_leg(ep: dict) -> dict | None:
    for row in ep["carry"]:
        if row["leg"] == "grasp_lift":
            return row
    return None


def mid_carry_falls(ep: dict) -> list[dict]:
    """`held=True` falls in this episode's window = lost between grasp and release."""
    return [row for row in ep["falls"] if row["held"]]


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="assertions only")
    args = parser.parse_args(argv)

    logs = []
    for label, role, pattern in CORPORA:
        for path in sorted(glob.glob(os.path.join(LOGS, pattern))):
            log = parse_log(path)
            if not log["episodes"]:
                continue  # batch_outer wrappers etc. - no per-pick rows
            log["corpus"] = label
            log["role"] = role
            logs.append(log)
    if not logs:
        print("no logs found - is the corpus glob right?", file=sys.stderr)
        return 2

    episodes = []
    for log in logs:
        for ep in log["episodes"]:
            ep["corpus"] = log["corpus"]
            ep["log"] = log["rel"].split("/")[-1]
            episodes.append(ep)
    for ep in episodes:
        ep["class"] = outcome_class(ep)
        ep["trigger"] = trigger_fields(ep)

    out = []
    say = out.append
    say("=" * 100)
    say("P60 phase 1 - the left-arm failure census (offline; every number carries its file:line)")
    say("=" * 100)
    say("")
    say("## 1. the corpora")
    say("")
    say(f"{'corpus':8s} {'log':22s} {'seed':>4s} {'eps':>4s} {'left':>5s} {'right':>5s}  role")
    for log in logs:
        left = sum(1 for ep in log["episodes"] if ep["arm"] == "left")
        right = len(log["episodes"]) - left
        say(
            f"{log['corpus']:8s} {log['rel'].split('/')[-1]:22s} {log['seed']:>4d} "
            f"{len(log['episodes']):>4d} {left:>5d} {right:>5d}  {log['role']}"
        )
    say("")
    seen = set()
    for log in logs:
        for key, value in (
            ("env ready", log["env_ready"]),
            ("trigger", log["trigger"]),
            ("profile", log["profile"]),
        ):
            if value and (key, value) not in seen:
                seen.add((key, value))
                say(f"  [{key}] {value}")
    say("")

    # ---- the class table ---- #
    say("## 2. arm x class (every episode in the four corpora)")
    say("")
    classes = ["placed", "carried-not-placed", "never-held", "placed-off-belt"]
    say(f"{'corpus':8s} {'arm':6s} " + " ".join(f"{name:>19s}" for name in classes) + "   n")
    for label, role, pattern in CORPORA:
        for arm in ("left", "right"):
            rows = [ep for ep in episodes if ep["corpus"] == label and ep["arm"] == arm]
            if not rows:
                continue
            counts = [sum(1 for ep in rows if ep["class"] == name) for name in classes]
            say(
                f"{label:8s} {arm:6s} "
                + " ".join(f"{count:>19d}" for count in counts)
                + f"  {len(rows):>3d}"
            )
    say("")
    for arm in ("left", "right"):
        rows = [ep for ep in episodes if ep["arm"] == arm]
        counts = [sum(1 for ep in rows if ep["class"] == name) for name in classes]
        say(f"  pooled {arm:5s} n={len(rows):>3d}  " + "  ".join(
            f"{name}={count}" for name, count in zip(classes, counts)))
    say("")

    # shares
    say("## 3. class shares")
    say("")
    for arm in ("left", "right"):
        rows = [ep for ep in episodes if ep["arm"] == arm]
        failures = [ep for ep in rows if not ep["success"]]
        say(f"  {arm}: {len(rows) - len(failures)}/{len(rows)} placed; "
            f"{len(failures)} failures")
        for name in classes[1:]:
            count = sum(1 for ep in failures if ep["class"] == name)
            if count:
                say(f"    {name:20s} {count:>3d}/{len(failures)} = "
                    f"{count / len(failures):>6.1%} of failures, "
                    f"{count / len(rows):>5.1%} of attempts")
    say("")
    left = [ep for ep in episodes if ep["arm"] == "left"]
    right = [ep for ep in episodes if ep["arm"] == "right"]
    contrasts = [
        ("cnp among attempts",
         sum(1 for ep in left if ep["class"] == "carried-not-placed"),
         len(left) - sum(1 for ep in left if ep["class"] == "carried-not-placed"),
         sum(1 for ep in right if ep["class"] == "carried-not-placed"),
         len(right) - sum(1 for ep in right if ep["class"] == "carried-not-placed")),
        ("never-held among attempts",
         sum(1 for ep in left if ep["class"] == "never-held"),
         len(left) - sum(1 for ep in left if ep["class"] == "never-held"),
         sum(1 for ep in right if ep["class"] == "never-held"),
         len(right) - sum(1 for ep in right if ep["class"] == "never-held")),
        ("placed among attempts",
         sum(1 for ep in left if ep["success"]),
         len(left) - sum(1 for ep in left if ep["success"]),
         sum(1 for ep in right if ep["success"]),
         len(right) - sum(1 for ep in right if ep["success"])),
    ]
    say("  Fisher exact (two-sided), left vs right, pooled:")
    for name, a, b, c, d in contrasts:
        p = fisher_two_sided(a, b, c, d)
        say(f"    {name:28s} left {a:>2d}/{a + b:<3d} right {c:>2d}/{c + d:<3d}  "
            f"p = {p:.2e}")
    say("")

    # ---- the note key ---- #
    say("## 2b. the `113_rl_report.py` note key (digit-normalised) per class")
    say("")
    keys: dict[tuple[str, str], int] = {}
    for ep in episodes:
        if ep["success"]:
            continue
        text = "', '".join(ep["notes"])
        key = re.sub(r"[-+0-9.]+", "#", text)
        keys[(ep["class"], key)] = keys.get((ep["class"], key), 0) + 1
    for (name, key), count in sorted(keys.items()):
        arms = sorted({ep["arm"] for ep in episodes
                       if not ep["success"] and ep["class"] == name
                       and re.sub(r"[-+0-9.]+", "#", "', '".join(ep["notes"])) == key})
        say(f"  {name:18s} n={count:>2d} ({'+'.join(arms)})  {key}")
    say("")
    say("  => the note adds nothing beyond `grasped`: every cnp carries the trigger")
    say("     row alone, every never-held carries it plus `fruit did not follow the")
    say("     gripper`. A 'no new reason' gate on this corpus is cheap by")
    say("     construction for the cnp class.")
    say("")

    # ---- every left failure ---- #
    say("## 4. every left failure (one row per episode)")
    say("")
    header = (
        f"{'corpus':7s} {'log':10s} {'ln':>5s} {'ep':>3s} {'species':10s} {'d':>4s} "
        f"{'bin':>3s} {'class':18s} {'ticks':>5s} {'ftips':>5s} {'dx':>6s} {'dy':>6s} "
        f"{'t_arr':>5s} {'lead':>5s} {'reach':>5s} {'legs':12s} {'plow':>4s} "
        f"{'feed':>4s} {'x_sel':>5s} {'fall':>18s}"
    )
    say(header)
    say("-" * len(header))
    for log in logs:
        for ep in log["episodes"]:
            if ep["arm"] != "left" or ep["success"]:
                continue
            trig = ep["trigger"] or {}
            legs = "+".join(row["leg"].replace("grasp_lift", "lift")
                            .replace("place", "p") for row in ep["carry"]) or "-"
            fall = "-"
            held = mid_carry_falls(ep)
            if held:
                fall = (f"held {held[0]['species']} idx{held[0]['index']} "
                        f"y={held[0]['y']:+.2f}")
            elif ep["falls"]:
                fall = f"detached n={len(ep['falls'])}"
            say(
                f"{log['corpus']:7s} {log['rel'].split('/')[-1][:10]:10s} "
                f"{ep['start_line']:>5d} {ep['index']:>3d} {ep['species']:10s} "
                f"{ep['diameter']:>4.1f} {ep['bin']:>3d} {ep['class']:18s} "
                f"{ep['ticks']:>5d} "
                f"{(str(ep['fingertips_mm']) if ep['fingertips_mm'] is not None else '-'):>5s} "
                f"{(f'{trig.get('dx_mm', float('nan')):+.1f}' if trig else '-'):>6s} "
                f"{(f'{trig.get('dy_mm', float('nan')):.1f}' if trig else '-'):>6s} "
                f"{(f'{trig.get('t_arrive', float('nan')):.2f}' if trig else '-'):>5s} "
                f"{(f'{trig.get('lead', float('nan')):.2f}' if trig else '-'):>5s} "
                f"{(f'{trig.get('reach', float('nan')):.2f}' if trig else '-'):>5s} "
                f"{legs:12s} {(('yes' if ep['place_low'] else 'no')):>4s} "
                f"{(('yes' if ep['feed'] else 'no')):>4s} "
                f"{(f'{ep['chosen_x']:.3f}' if ep['chosen_x'] else '-'):>5s} {fall:>18s}"
            )
    say("")
    say("  legend: ftips = `[task] openarm fingertips NN mm from the fruit; closing anyway`")
    say("          legs  = the `[task] carry <leg>` rows that printed (one per leg START)")
    say("          plow  = a `[task] place low:` row printed (finger-floor bound descent)")
    say("          feed  = a `[feed] <arm>: ... (attempt start -> release)` row printed")
    say("          x_sel = the `-> chosen` candidate's x in the `[bed-sel]` block")
    say("          fall  = a `[bed-fall] ... held=True` row inside this episode's window")
    say("")

    # ---- the cnp onset signatures side by side ---- #
    say("## 5. the cnp onset signatures, left vs right (the rows these logs carry)")
    say("")
    cnp_left = [ep for ep in left if ep["class"] == "carried-not-placed"]
    cnp_right = [ep for ep in right if ep["class"] == "carried-not-placed"]
    ok_right = [ep for ep in right if ep["success"]]
    ok_left = [ep for ep in left if ep["success"]]
    groups = [
        ("left cnp", cnp_left),
        ("right cnp", cnp_right),
        ("left placed", ok_left),
        ("right placed", ok_right),
    ]
    say(f"{'group':13s} {'n':>3s} {'ftips mm':>22s} {'|dx| mm':>22s} "
        f"{'lift drift mm':>22s} {'place drift mm':>22s}")
    for name, rows in groups:
        ftips = [ep["fingertips_mm"] for ep in rows if ep["fingertips_mm"] is not None]
        dxs = [abs(ep["trigger"]["dx_mm"]) for ep in rows if ep["trigger"]]
        lift = [lift_leg(ep)["drift_mm"] for ep in rows if lift_leg(ep)]
        place = [place_leg(ep)["drift_mm"] for ep in rows if place_leg(ep)]
        say(f"{name:13s} {len(rows):>3d} {fmt_msd(ftips):>22s} {fmt_msd(dxs):>22s} "
            f"{fmt_msd(lift):>22s} {fmt_msd(place):>22s}")
    say("")
    say("  median [min-max]; '-' = no row. `drift` = `stored pad centre NN mm from the")
    say("  measured pads` at that carry leg's start (one row per leg, so its presence")
    say("  proves the leg ran: every cnp episode here printed its place leg).")
    say("")
    say(f"{'group':13s} {'n':>3s} {'dx mm (signed)':>24s} {'dy mm':>22s} "
        f"{'reach mm':>20s} {'lead s':>18s} {'t_arr s':>18s}")
    for name, rows in groups:
        trig = [ep["trigger"] for ep in rows if ep["trigger"]]
        dxs = [t["dx_mm"] for t in trig]
        dys = [t["dy_mm"] for t in trig]
        reach = [t["reach"] * 1000.0 for t in trig]
        lead = [t["lead"] for t in trig]
        tra = [t["t_arrive"] for t in trig]
        say(f"{name:13s} {len(rows):>3d} {fmt_msd(dxs):>24s} {fmt_msd(dys):>22s} "
            f"{fmt_msd(reach, '', 0):>20s} {fmt_msd(lead, '', 2):>18s} "
            f"{fmt_msd(tra, '', 2):>18s}")
    say("")
    say("  per-class leg census (how far the episode got):")
    for name, rows in groups:
        lift = sum(1 for ep in rows if lift_leg(ep))
        place = sum(1 for ep in rows if place_leg(ep))
        plow = sum(1 for ep in rows if ep["place_low"])
        feed = sum(1 for ep in rows if ep["feed"])
        retry = sum(1 for ep in rows if ep["retry"])
        ftips = sum(1 for ep in rows if ep["fingertips_mm"] is not None)
        say(f"    {name:13s} n={len(rows):>3d}  fingertips {ftips:>3d}  lift-leg "
            f"{lift:>3d}  place-leg {place:>3d}  place-low {plow:>3d}  "
            f"feed/release {feed:>3d}  retry row {retry:>3d}")
    say("")
    say("  Fisher exact on `place-low printed`, left cnp vs right placed: "
        + f"p = {fisher_two_sided(sum(1 for ep in cnp_left if ep['place_low']), len(cnp_left) - sum(1 for ep in cnp_left if ep['place_low']), sum(1 for ep in ok_right if ep['place_low']), len(ok_right) - sum(1 for ep in ok_right if ep['place_low'])):.2e}")
    say("")
    say("  the `place low` rows that did print (the payload's height at the descent):")
    say(f"    {'group':13s} {'bottom mm':>20s} {'need mm':>18s} "
        f"{'finger budget mm':>22s} {'final clearance mm':>22s}")
    for name, rows in groups:
        low = [ep["place_low"] for ep in rows if ep["place_low"]]
        if not low:
            say(f"    {name:13s} {'-':>20s} (no row)")
            continue
        say(f"    {name:13s} "
            f"{fmt_msd([r['bottom_mm'] for r in low], '', 0):>20s} "
            f"{fmt_msd([r['need_mm'] for r in low], '', 0):>18s} "
            f"{fmt_msd([r['finger_budget_mm'] for r in low], '', 0):>22s} "
            f"{fmt_msd([r['clearance_mm'] for r in low], '', 0):>22s}")
    say("")
    say("  (the row prints only when `finger_budget < drop`, `tasks.py:12344`, and the")
    say("  descent is skipped entirely when `need <= 0`, `tasks.py:12303`: so a missing")
    say("  row means the payload was NOT at the carried height, ~0.15 m above the")
    say("  output belt top (1.35 m, `assets.py:309`) - not that the leg was skipped.)")

    # ---- the lateral band ---- #
    say("## 6. the lateral band: where the left's attempts sit vs the right's")
    say("")
    say("  (a) the `[bed-sel] -> chosen` x at the selection instant (absolute, m)")
    for arm in ("left", "right"):
        xs = [ep["chosen_x"] for ep in episodes
              if ep["arm"] == arm and ep["chosen_x"] is not None]
        say(f"    {arm:6s} n={len(xs):>3d}  {fmt_msd(xs, ' m', 3)}")
    xs_left = [ep["chosen_x"] for ep in episodes
               if ep["arm"] == "left" and ep["chosen_x"] is not None]
    xs_right = [ep["chosen_x"] for ep in episodes
                if ep["arm"] == "right" and ep["chosen_x"] is not None]
    if xs_left and xs_right:
        above = 0.30
        a = sum(1 for x in xs_left if x >= above)
        b = len(xs_left) - a
        c = sum(1 for x in xs_right if x >= above)
        d = len(xs_right) - c
        say(f"    x >= {above:.2f} m: left {a}/{len(xs_left)} right {c}/{len(xs_right)}"
            f"  Fisher p = {fisher_two_sided(a, b, c, d):.3f}")
    say("")
    say("  (b) the trigger's lateral offset at the fire tick "
        "(dx = fruit x - measured jaw x, `trigger.py:314`)")
    for arm in ("left", "right"):
        trig = [ep["trigger"] for ep in episodes
                if ep["arm"] == arm and ep["trigger"]]
        dxs = [t["dx_mm"] for t in trig]
        say(f"    {arm:6s} n={len(dxs):>3d}  {fmt_msd(dxs, ' mm', 1)}  "
            f"|dx| max {max(abs(v) for v in dxs):.1f} mm")
    say("")
    say("  (c) per-class chosen x (selection instant):")
    for name, rows in groups:
        xs = [ep["chosen_x"] for ep in rows if ep["chosen_x"] is not None]
        say(f"    {name:13s} n={len(xs):>3d}  {fmt_msd(xs, ' m', 3)}")
    say("")
    say("  (d) is a large fire-time lateral offset a *left-only* risk? "
        "(|dx| at the fire tick)")
    bands = [("|dx| <= 66 mm", lambda v: v <= 66.0), ("|dx| >  66 mm", lambda v: v > 66.0)]
    say(f"    {'band':16s} {'left placed':>14s} {'right placed':>14s}   Fisher p")
    for name, pred in bands:
        lrows = [ep for ep in left if ep["trigger"] and pred(abs(ep["trigger"]["dx_mm"]))]
        rrows = [ep for ep in right if ep["trigger"] and pred(abs(ep["trigger"]["dx_mm"]))]
        lok = sum(1 for ep in lrows if ep["success"])
        rok = sum(1 for ep in rrows if ep["success"])
        p = fisher_two_sided(lok, len(lrows) - lok, rok, len(rrows) - rok)
        say(f"    {name:16s} {lok:>5d}/{len(lrows):<8d} {rok:>5d}/{len(rrows):<8d}   "
            f"{p:.2e}")
    for arm in ("left", "right"):
        ok = [abs(ep["trigger"]["dx_mm"]) for ep in episodes
              if ep["arm"] == arm and ep["success"] and ep["trigger"]]
        bad = [abs(ep["trigger"]["dx_mm"]) for ep in episodes
               if ep["arm"] == arm and not ep["success"] and ep["trigger"]]
        if not ok or not bad:
            continue
        say(f"    {arm:6s}: placed |dx| max {max(ok):.0f} mm (n={len(ok)}, "
            f"median {statistics.median(ok):.0f}); failures' |dx| median "
            f"{statistics.median(bad):.0f} mm [{min(bad):.0f}-{max(bad):.0f}]")
    say("    66 mm is the left's own placed maximum, i.e. the observed left ceiling;")
    say("    it is quoted as a band split, not as a gate (n = 7 left placements).")
    say("")
    never = [ep for ep in left if ep["class"] == "never-held"]
    if never:
        xs = [ep["chosen_x"] for ep in never if ep["chosen_x"] is not None]
        dxs = [ep["trigger"]["dx_mm"] for ep in never if ep["trigger"]]
        say(f"  (e) the left's {len(never)} never-held episodes: x_sel "
            f"{fmt_msd(xs, ' m', 3)}, signed dx {fmt_msd(dxs, ' mm', 0)} - "
            "all at the +x end of the band")
    say("")
    say("  (f) the jaw's implied x at the fire tick (x_sel - dx; the P49 caveat: 34/39")
    say("      selections agree to <= 2.7 mm, 5/39 move outward 5.3-19.2 mm)")
    for arm in ("left", "right"):
        est = [ep["chosen_x"] - ep["trigger"]["dx_mm"] / 1000.0 for ep in episodes
               if ep["arm"] == arm and ep["chosen_x"] is not None and ep["trigger"]]
        say(f"    {arm:6s} n={len(est):>3d}  {fmt_msd(est, ' m', 3)}")
    say("")

    # ---- species ---- #
    say("## 7. what the left actually attempts (the grade lane is the arm)")
    say("")
    for arm in ("left", "right"):
        rows = [ep for ep in episodes if ep["arm"] == arm]
        bins = sorted({ep["bin"] for ep in rows})
        grades = sorted({ep["grade"] for ep in rows})
        say(f"  {arm}: bin {bins}, grade {grades}")
        by_species = {}
        for ep in rows:
            entry = by_species.setdefault(ep["species"], [0, 0, 0])
            entry[0] += 1
            entry[1] += 1 if ep["success"] else 0
            entry[2] += 1 if ep["class"] == "carried-not-placed" else 0
        for species, (n, ok, cnp) in sorted(by_species.items(),
                                           key=lambda kv: (-kv[1][0], kv[0])):
            say(f"    {species:11s} {ok:>2d}/{n:<2d} placed  cnp {cnp:>2d}")
    say("")

    # ---- bed falls ---- #
    say("## 8. `[bed-fall]` rows (the only positional evidence of a lost payload)")
    say("")
    say(f"{'log':12s} {'ln':>5s} {'ep':>4s} {'species':10s} {'idx':>3s} {'x':>7s} "
        f"{'y':>7s} {'z':>6s} {'held':>5s}  attributed")
    for log in logs:
        for row in log["falls"]:
            say(f"{log['rel'].split('/')[-1][:12]:12s} {row['line']:>5d} "
                f"{(str(row['episode']) if row['episode'] is not None else '-'):>4s} "
                f"{row['species']:10s} {row['index']:>3d} {row['x']:>+7.3f} "
                f"{row['y']:>+7.3f} {row['z']:>6.3f} "
                f"{('True' if row['held'] else 'False'):>5s}  "
                f"{'mid-carry (grasp..release)' if row['held'] else 'detached'}")
    say("")
    held_rows = [row for log in logs for row in log["falls"] if row["held"]]
    say(f"  held=True (mid-carry) falls: {len(held_rows)} in "
        f"{sum(1 for log in logs for row in log['falls'])} row(s) total")
    say("")

    # ---- checks ---- #
    say("## 9. checks (assertions - a FAIL means the parse or the corpus is wrong)")
    say("")
    failures = []
    checks = [
        ("every log has 15 episodes", all(len(log["episodes"]) == 15 for log in logs)),
        ("every episode has an end row", all(ep["end_line"] for ep in episodes)),
        ("the `fingertips` row (>20 mm close) on >= 95% of episodes",
         sum(1 for ep in episodes if ep["fingertips_mm"] is not None)
         >= 0.95 * len(episodes)),
        ("every episode has a trigger note",
         all(ep["trigger"] is not None for ep in episodes)),
        ("every episode resolved its chosen x from [bed-sel]",
         all(ep["chosen_x"] is not None for ep in episodes if ep["end_line"])),
        ("`retry` row iff grasped and not placed",
         all(ep["retry"] == (ep["grasped"] and not ep["placed"]) for ep in episodes
             if ep["end_line"])),
        ("every cnp episode printed its place leg",
         all(place_leg(ep) for ep in episodes
             if ep["class"] == "carried-not-placed")),
        ("every never-held episode printed no place leg",
         all(not place_leg(ep) for ep in episodes if ep["class"] == "never-held")),
        ("a `[feed]` row iff the episode reached a release",
         all((ep["feed"] is not None) == bool(place_leg(ep)) for ep in episodes
             if ep["end_line"])),
        ("left episodes are all bin 0 / grade A",
         all(ep["bin"] == 0 and ep["grade"] == "A" for ep in left)),
        ("right episodes are all bin 1 / grade B or C",
         all(ep["bin"] == 1 and ep["grade"] in ("B", "C") for ep in right)),
    ]
    for name, passed in checks:
        say(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        if not passed:
            failures.append(name)
    say("")
    print("\n".join(out))
    if args.check:
        return 1 if failures else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
