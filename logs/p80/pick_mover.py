"""P80 R3: which arm's inter-placement interval moved most against S?

    python3 logs/p80/pick_mover.py            # reads whichever of S20/T20/U20/V20 exist

Writes logs/p80/mover.txt printing the arm letter and both relative moves, so the
seed-6 pair the driver spends is the pre-registered one (the arm whose interval
moved most), not a post-hoc choice. Ties: the larger |relative| wins; a tie at
equal magnitude takes the earlier letter (T before U before V).
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p80lib  # noqa: E402

ARMS = ("T", "U", "V")


def load(letter):
    path = os.path.join(HERE, f"{letter}20.log")
    if not os.path.exists(path):
        return None
    return p80lib.metrics(path)


base = p80lib.metrics(os.path.join(HERE, "S20.log"))
base_mean = base["pooled"]["mean"]
rows = []
for letter in ARMS:
    m = load(letter)
    if m is None or not m["pooled"]["mean"] or not base_mean:
        continue
    rel = (m["pooled"]["mean"] - base_mean) / base_mean
    rows.append((abs(rel), letter, rel, m))

lines = [
    "P80 R3 mover - pooled inter-placement interval vs S20 "
    f"({p80lib.fmt(base_mean)}s mean)",
]
for mag, letter, rel, m in sorted(rows, key=lambda r: (-r[0], r[1])):
    lines.append(
        f"  {letter}20: {p80lib.fmt(m['pooled']['mean'])}s mean "
        f"({100.0 * rel:+.1f}%), p90 {p80lib.fmt(m['pooled']['p90'])}s, "
        f"placed {m['placed']}/{m['attempts']}, "
        f"s/attempt {p80lib.fmt(m['stats']['per_attempt'])}")
if not rows:
    lines.append("  no arm to pick")
    text = "\n".join(lines)
    print(text)
    with open(os.path.join(HERE, "mover.txt"), "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    sys.exit(1)
mover = max(rows, key=lambda r: r[0])[1]
lines.append(f"  -> seed-6 pair: S6 + {mover}6")
text = "\n".join(lines)
print(text)
with open(os.path.join(HERE, "mover.txt"), "w", encoding="utf-8") as fh:
    fh.write(text + "\n")
sys.exit(0)
