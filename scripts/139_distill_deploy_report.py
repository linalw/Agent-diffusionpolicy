"""Deployability comparison: distilled student vs teacher, direct interface.

Parses the `[rl] episode ...` lines of two `scripts/110_rl_rollout.py` logs (the
teacher's 3x15 batch and the student's 3x15 batch on the same frozen tree),
prints per-run/per-class/per-fruit tables and applies the v5-C falsifier:

* the pooled student rate may lose at most **1 episode per N** (N = the
  teacher's episode count; e.g. 45 episodes -> at most 1 net loss) to the
  teacher, and
* no **wide-strawberry regression**: the student must not lose a strawberry
  episode the teacher won (strawberries are the class the old 3.4 cm limit
  concentrated on).

    python3 scripts/139_distill_deploy_report.py \
        --teacher logs/distill/138_teacher_trigger.log \
        --student logs/distill/138_student4_trigger.log
"""

from __future__ import annotations

import argparse
import re
from collections import Counter

EPISODE = re.compile(
    r"\[rl\] episode (?P<episode>\d+): (?P<category>\w+) .*?d=(?P<diameter>[\d.]+)cm "
    r".*?success=(?P<success>True|False) .*?notes=(?P<notes>\[.*?\])\s+presentation"
)


def parse(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            match = EPISODE.search(line)
            if not match:
                continue
            rows.append(
                {
                    "episode": int(match.group("episode")),
                    "category": match.group("category"),
                    "diameter": float(match.group("diameter")),
                    "success": match.group("success") == "True",
                    "notes": match.group("notes"),
                }
            )
    return rows


FAILURE_PATTERNS = (
    ("timeout", "timeout"),
    ("did not follow", "grip loss"),
    ("left the pick station", "left station"),
    ("falls off", "fell off"),
    ("fell off", "fell off"),
    ("crush", "crush"),
    ("escape", "escape"),
    ("slip", "slip"),
)


def reason(notes: str) -> str:
    """The failure class of an episode, not its trigger bookkeeping.

    Failure notes (`fruit did not follow the gripper`, timeouts, ...) are the
    informative ones; the intercept-trigger note is present on successes too, so
    it is only the fallback label.
    """
    lowered = notes.lower()
    for key, label in FAILURE_PATTERNS:
        if key in lowered:
            return label
    if "intercept trigger" in notes:
        return "fired, no failure note"
    if "policy closed" in notes:
        return "closed, no failure note"
    return "other"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teacher", required=True,
                        help="log path(s), comma-separated (one per seed run)")
    parser.add_argument("--student", required=True,
                        help="log path(s), comma-separated (one per seed run)")
    parser.add_argument("--per-run", type=int, default=15,
                        help="episodes per seed run (for the per-run table)")
    args = parser.parse_args()

    def load(paths: str) -> list[dict]:
        rows: list[dict] = []
        for run, path in enumerate(p.strip() for p in paths.split(",") if p.strip()):
            for row in parse(path):
                row["run"] = run
                row["source"] = path
                rows.append(row)
        return rows

    teacher = load(args.teacher)
    student = load(args.student)
    if not teacher or not student:
        raise SystemExit("no episodes parsed - check the logs")

    lines = []
    lines.append(f"teacher {args.teacher}: {sum(t['success'] for t in teacher)}/{len(teacher)}")
    lines.append(f"student {args.student}: {sum(s['success'] for s in student)}/{len(student)}")
    lines.append("")
    lines.append("per run (seed order):")
    for label, rows in (("teacher", teacher), ("student", student)):
        for run in sorted({r["run"] for r in rows}):
            sel = [r for r in rows if r["run"] == run]
            lines.append(
                f"  {label:<8s} run {run}: {sum(r['success'] for r in sel)}/{len(sel)}"
            )
    lines.append("")
    lines.append("per class:")
    categories = sorted({r["category"] for r in teacher + student})
    for category in categories:
        t = [r for r in teacher if r["category"] == category]
        s = [r for r in student if r["category"] == category]
        lines.append(
            f"  {category:<11s} teacher {sum(r['success'] for r in t)}/{len(t)}  "
            f"student {sum(r['success'] for r in s)}/{len(s)}"
        )
    lines.append("")
    lines.append("strawberry episodes (category, diameter, outcome):")
    for label, rows in (("teacher", teacher), ("student", student)):
        for r in sorted([r for r in rows if r["category"] == "strawberry"],
                        key=lambda r: -r["diameter"]):
            lines.append(
                f"  {label:<8s} ep{r['episode']:>2d} d={r['diameter']:.1f}cm "
                f"success={r['success']} ({reason(r['notes'])})"
            )
    lines.append("")
    lines.append("per episode (run/episode category d success reason):")
    for label, rows in (("teacher", teacher), ("student", student)):
        lines.append(f"  {label}:")
        for r in rows:
            lines.append(
                f"    r{r['run']} ep{r['episode']:>2d} {r['category']:<10s} "
                f"d={r['diameter']:.1f} {'OK ' if r['success'] else 'FAIL'} "
                f"{reason(r['notes'])}"
            )
    lines.append("")
    lines.append("failure reasons:")
    for label, rows in (("teacher", teacher), ("student", student)):
        failed = Counter(reason(r["notes"]) for r in rows if not r["success"])
        lines.append(f"  {label:<8s} {dict(failed)}")

    t_ok = sum(r["success"] for r in teacher)
    s_ok = sum(r["success"] for r in student)
    t_straw = [r for r in teacher if r["category"] == "strawberry"]
    s_straw = [r for r in student if r["category"] == "strawberry"]
    t_straw_ok = sum(r["success"] for r in t_straw)
    s_straw_ok = sum(r["success"] for r in s_straw)
    net_loss = t_ok - s_ok
    lines.append("")
    lines.append("falsifier:")
    lines.append(
        f"  net episodes: {net_loss:+d} (allowed: at most +1 loss per N={len(teacher)})"
    )
    wide = [r for r in t_straw if r["diameter"] >= 3.9]
    wide_ok_t = sum(r["success"] for r in wide)
    wide_ok_s = sum(
        r["success"] for r in s_straw if r["diameter"] >= 3.9
    )
    lines.append(
        f"  wide strawberry (>= 3.9 cm): teacher {wide_ok_t}/{len(wide)} "
        f"student {wide_ok_s}/{len(wide)}"
    )
    lines.append(
        f"  strawberry overall: teacher {t_straw_ok}/{len(t_straw)} "
        f"student {s_straw_ok}/{len(s_straw)}"
    )
    kept = net_loss <= 1 and s_straw_ok >= t_straw_ok
    wide_kept = net_loss <= 1 and wide_ok_s >= wide_ok_t
    lines.append(
        f"  literal rule (net_loss<=1 and no wide-strawberry regression): "
        f"{'HOLDS' if wide_kept else 'KILLED'}"
    )
    lines.append(
        f"  strawberry overall (all sizes, stricter reading): "
        f"{'regressed' if s_straw_ok < t_straw_ok else 'not worse'}"
    )
    lines.append(f"  VERDICT: {'HOLDS' if kept else 'KILLED'} "
                 f"(net_loss={net_loss:+d}, strawberry {t_straw_ok}->{s_straw_ok})")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
