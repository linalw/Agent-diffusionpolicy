"""E-lane no-fire diagnostic: classify every no-fire episode from the enriched
RL_ENV_DEBUG trace (frozen_b1_trigger_diag).

Usage:
    python3 /tmp/opencode/e_nofire_report.py logs/820_*.log logs/830_*.log logs/831_*.log

For each episode it prints category/arm, outcome, and (for episodes where the
intercept trigger did NOT fire) the trigger gate's own numbers plus a mechanism
class:

  recirculated    an upstream (>5 cm) / cross-belt jump of the tracked sample
                  between adjacent rows (the env's sample object was moved back
                  to the feeder or re-placed; not a prediction error)
  off-lane        the fruit is at the station line zone but |dx| > 0.06 the
                  whole time (lateral gate correctly refuses)
  blocked/stalled the fruit is aligned but never reaches the fire line
                  dy <= 0.054 and barely moves over the last 250 steps
  approach-not-finished  aligned, still upstream at the end, still moving
                  (horizon / selected too far)
  passed-station  the last rows are downstream (dy < -0.05)
  near-miss       a sampled row had dy <= 0.054 with |dx| <= 0.06 yet no fire
                  (row cadence / one-tick lead miss)
  policy-close    no intercept but the episode ended early via the policy's own
                  6 cm close (not a timeout; listed for completeness)
  early-end       episode ended early for another reason (fruit fell, etc.)
  other           none of the above

Rows are sampled at the RL_ENV_DEBUG cadence (every 25 steps, every step while
the finger is near closed), so the crossing of the 5.4 cm fire line can fall
between rows; the intercept note on the episode result line is the ground truth
for "fired".
"""
from __future__ import annotations

import re
import sys

ROW = re.compile(
    r"step=(\d+) finger=([\d.]+) \|jaw-fruit\|xy=([\d.]+)cm "
    r"fruit=\(([-+0-9.]+),([-+0-9.]+),([-+0-9.]+)\) "
    r"jaw=\(([-+0-9.]+),([-+0-9.]+),([-+0-9.]+)\) "
    r"station=\(([-+0-9.]+),([-+0-9.]+)\) "
    r"enc=([-+0-9.]+|nan) "
    r"dy=([-+0-9.]+|nan) dx=([-+0-9.]+|nan) "
    r"t_arr=([-+0-9.]+|nan) speed=([-+0-9.]+|nan)/(\w+) fire=(True|False)"
)
START = re.compile(
    r"\[rl\] episode (\d+): (\w+) grade=(\w+) d=([\d.]+)cm bin=(-?\d) arm=(\w+) y=([-+0-9.]+)"
)
RESULT = re.compile(
    r"\[rl\] episode (\d+): (\w+) d=[\d.]+cm bin=-?\d arm=(\w+) success=(\w+) "
    r"grasped=(\w+) placed=(\w+) ticks=(\d+) decision=(\d+) reward=[-0-9.]+ "
    r"notes=(\[.*?\]) presentation"
)

LAT = 0.06
LEAD = 0.90
ENC_SPEED = 0.06
FIRE_LINE = LEAD * ENC_SPEED  # 0.054 m


def f(x: str) -> float:
    return float("nan") if x == "nan" else float(x)


def classify(ep: dict) -> str:
    rows = ep["rows"]
    if not rows:
        return "no-rows"
    near = [r for r in rows if -0.05 <= r["dy"] <= 0.25]
    aligned = [r for r in near if abs(r["dx"]) <= LAT]
    # 1) upstream displacement: the belt can only move fruit downstream (-y),
    # so a sustained net +y motion of the tracked sample over any 100-step
    # window is an external push / re-placement (>= 3 cm net).
    win = 100
    for i, a in enumerate(rows):
        later = [r for r in rows if r["step"] == a["step"] + win]
        if later:
            b = later[0]
            if b["fy"] - a["fy"] > 0.03:
                ep["push_step"] = a["step"]
                ep["push_dy"] = b["fy"] - a["fy"]
                ep["push_dx"] = b["fx"] - a["fx"]
                return "pushed-upstream"
    # 2) lateral gate: never aligned on the station line
    if not aligned:
        min_dx = min((abs(r["dx"]) for r in near), default=float("nan"))
        ep["min_dx_near"] = min_dx
        return "off-lane"
    ep["min_dx_near"] = min(abs(r["dx"]) for r in aligned)
    ep["dy_lo_aligned"] = min(r["dy"] for r in aligned)
    # 3) fire line reached while aligned? (sampled)
    if ep["dy_lo_aligned"] <= FIRE_LINE:
        return "near-miss"
    # 4) aligned, upstream of the line: stalled or still approaching?
    last = rows[-1]
    tail = [r for r in rows if r["step"] >= last["step"] - 250]
    if tail:
        net = ((tail[-1]["fy"] - tail[0]["fy"]) ** 2
               + (tail[-1]["fx"] - tail[0]["fx"]) ** 2) ** 0.5
    else:
        net = 0.0
    ep["tail_net_250"] = net
    if last["dy"] > FIRE_LINE:
        if net < 0.02:
            return "blocked/stalled"
        return "approach-not-finished"
    return "passed-station" if last["dy"] < -0.05 else "near-line-unfinished"


def main() -> int:
    from collections import Counter
    totals = Counter()
    for path in sys.argv[1:]:
        print(f"===== {path}")
        episodes: list[dict] = []
        current = None
        for line in open(path, encoding="utf-8", errors="replace"):
            m = START.search(line)
            if m and "success=" not in line:
                current = {
                    "index": int(m.group(1)), "cat": m.group(2), "grade": m.group(3),
                    "arm": m.group(6), "y0": float(m.group(7)), "rows": [],
                    "notes": "",
                }
                episodes.append(current)
                continue
            r = ROW.search(line)
            if r and current is not None:
                current["rows"].append({
                    "step": int(r.group(1)), "finger": float(r.group(2)),
                    "dist": float(r.group(3)) / 100, "fx": float(r.group(4)),
                    "fy": float(r.group(5)), "fz": float(r.group(6)),
                    "jx": float(r.group(7)), "jy": float(r.group(8)),
                    "jz": float(r.group(9)), "sx": float(r.group(10)),
                    "sy": float(r.group(11)), "enc": f(r.group(12)),
                    "dy": f(r.group(13)), "dx": f(r.group(14)),
                    "t_arr": f(r.group(15)), "speed": f(r.group(16)),
                    "source": r.group(17), "fire": r.group(18) == "True",
                })
                continue
            q = RESULT.search(line)
            if q and current is not None and current["index"] == int(q.group(1)):
                current["ok"] = q.group(4) == "True"
                current["decision"] = int(q.group(8))
                current["notes"] = q.group(9)
        for ep in episodes:
            fired = "intercept trigger" in ep["notes"]
            timeout = "timeout" in ep["notes"]
            policy_close = "policy closed" in ep["notes"]
            cls = "-"
            if not fired:
                if timeout:
                    cls = classify(ep)
                elif policy_close:
                    cls = "policy-close"
                elif "success=True" in ep["notes"] or ep.get("ok"):
                    cls = "no-fire-success"
                else:
                    cls = "early-end-no-timeout"
            extra = ""
            for key, label, fmt in (
                ("min_dx_near", "min|dx|@near", "{:.1f}c"),
                ("dy_lo_aligned", "dy_lo@aligned", "{:+.1f}c"),
                ("tail_net_250", "net250", "{:.1f}c"),
            ):
                if key in ep:
                    v = ep[key]
                    if key.startswith("min_dx") or key.startswith("tail"):
                        v *= 100
                    extra += f" {label}={fmt.format(v)}"
            if "push_step" in ep:
                extra += (f" push@step{ep['push_step']} +{ep['push_dy']*100:.1f}/"
                          f"{ep['push_dx']*100:+.1f}c")
            if "recirc_step" in ep:
                extra += (f" recirc@step{ep['recirc_step']} "
                          f"+{ep['recirc_dy']*100:.1f}/{ep['recirc_dx']*100:+.1f}c")
            print(
                f"ep{ep['index']:>2} {ep['cat']:<11}{ep['arm']:<6} ok={str(ep.get('ok')):<5} "
                f"fired={str(fired):<5} timeout={str(timeout):<5} fire={cls}{extra}"
            )
            if not fired:
                key = "no-fire-timeout" if timeout else (
                    "policy-close" if policy_close else "no-fire-other")
                totals[(key, cls, ep["arm"])] += 1
    print("\n===== pool")
    for (key, cls, arm), n in sorted(totals.items()):
        print(f"  {key:<16} {cls:<26} {arm}: {n}")
    print("  fire classes are shown for no-fire episodes; '-' entries are the")
    print("  no-fire categories (policy-close / no-fire-other).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
