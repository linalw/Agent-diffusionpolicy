"""Report a direct-presentation RL A/B from the logs `112_rl_ab.sh` writes.

    python3 scripts/113_rl_report.py logs/rl_ab
    python3 scripts/113_rl_report.py --self-test      # offline parser/sign-test check

Logs come from `scripts/110_rl_rollout.py` (one `[rl] episode ...` line per
episode). The report prints, per arm and per run, the episode table; then the
pooled per-episode outcome, the paired flips between arms (same run, same
episode index; pairs whose fruit class differs are excluded and counted), a
one-sided sign test on the discordant pairs, the per-class table, the median
cycle time (simulated ticks), the failure reasons, and the pass criterion from
the P4 plan:

    (1) pooled candidate rate >= baseline, and
        (candidate beats baseline on discordant pairs, one-sided sign test
         p <= 0.05)  or
        (median cycle time >= 5 % lower with a non-inferior success rate)
    (2) strawberry rate not worse in the candidate
    (3) no failure reason the baseline never produced

Arm A is the baseline by convention (`112_rl_ab.sh` runs the shipped checkpoint
as A); the candidate is B.
"""

from __future__ import annotations

import argparse
import glob
import math
import os
import re
import statistics
import sys
import tempfile

EPISODE = re.compile(
    r"\[rl\] episode (\d+): (\w+) d=([\d.]+)cm bin=(-?\d+) arm=(\w+) "
    r"success=(\w+) grasped=(\w+) placed=(\w+) ticks=(\d+)(?: decision=(\d+))? "
    r"reward=([-+0-9.eE]+) notes=(\[[^\]]*\])"
)
SUMMARY = re.compile(r"\[rl\] rollout success (\d+)/(\d+)")


def parse(path: str) -> list[dict]:
    rows = []
    for line in open(path, encoding="utf-8", errors="ignore"):
        found = EPISODE.search(line)
        if not found:
            continue
        rows.append(
            {
                "index": int(found.group(1)),
                "category": found.group(2),
                "diameter": float(found.group(3)),
                "bin": int(found.group(4)),
                "arm": found.group(5),
                "success": found.group(6) == "True",
                "grasped": found.group(7) == "True",
                "placed": found.group(8) == "True",
                "ticks": int(found.group(9)),
                "decision": int(found.group(10)) if found.group(10) else None,
                "reward": float(found.group(11)),
                "notes": found.group(12),
            }
        )
    return rows


def sign_test_p(better: int, worse: int) -> float:
    """One-sided binomial p = P(X >= better), X ~ Bin(better + worse, 0.5)."""
    n = better + worse
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(better, n + 1)) / (2.0 ** n)


def load(directory: str, a_label: str, b_label: str):
    arms: dict[str, dict[int, list[dict]]] = {a_label: {}, b_label: {}}
    for path in sorted(glob.glob(os.path.join(directory, "*.log"))):
        stem = os.path.basename(path)[:-4]
        if "_" not in stem:
            continue
        label, run = stem.rsplit("_", 1)
        if label not in arms or not run.isdigit():
            continue
        arms[label][int(run)] = parse(path)
    return arms


def _rate(rows: list[dict]) -> float:
    return (sum(1 for r in rows if r["success"]) / len(rows)) if rows else 0.0


def report(directory: str, a_label: str, b_label: str) -> int:
    arms = load(directory, a_label, b_label)
    if not arms[a_label] or not arms[b_label]:
        print(f"no {a_label}_*/{b_label}_*.log pairs in {directory}")
        return 2
    runs = sorted(set(arms[a_label]) & set(arms[b_label]))
    if not runs:
        print("the two arms share no run index (file names must be A_1.log / B_1.log ...)")
        return 2

    for label in (a_label, b_label):
        print(f"=== arm {label}")
        for run in runs:
            rows = arms[label][run]
            line = "  ".join(
                f"{r['index']}:{r['category'][:4]}/{r['diameter']:.1f}/"
                f"{'ok' if r['success'] else 'FAIL'}"
                for r in rows
            )
            print(f"  run {run}: {sum(1 for r in rows if r['success'])}/{len(rows)}  {line}")

    pooled = {label: [r for run in runs for r in arms[label][run]] for label in (a_label, b_label)}
    print()
    for label in (a_label, b_label):
        rows = pooled[label]
        print(f"  pooled {label}: {sum(1 for r in rows if r['success'])}/{len(rows)} "
              f"({_rate(rows):.0%})  median ticks {statistics.median([r['ticks'] for r in rows]):.0f}"
              if rows else f"  pooled {label}: no episodes")

    # ---- paired flips (same run, same episode index, same fruit class) ---- #
    better = worse = both_ok = both_fail = mismatched = 0
    for run in runs:
        left = {r["index"]: r for r in arms[a_label][run]}
        right = {r["index"]: r for r in arms[b_label][run]}
        for index in sorted(set(left) & set(right)):
            a, b = left[index], right[index]
            if a["category"] != b["category"]:
                mismatched += 1
                continue
            if a["success"] and b["success"]:
                both_ok += 1
            elif a["success"] and not b["success"]:
                worse += 1
            elif not a["success"] and b["success"]:
                better += 1
            else:
                both_fail += 1
    p = sign_test_p(better, worse)
    print()
    print(f"  paired: {both_ok} both ok, {both_fail} both fail, "
          f"{better} {b_label}-only ok, {worse} {a_label}-only ok"
          + (f", {mismatched} excluded (fruit class differs)" if mismatched else ""))
    print(f"  sign test ({b_label} better): p = {p:.4f} "
          f"(discordant {better + worse})")

    # ---- per class ---- #
    categories = sorted({r["category"] for r in pooled[a_label] + pooled[b_label]})
    print(f"  {'class':<12s} {a_label:>10s} {b_label:>10s}  delta")
    for category in categories:
        ra = [r for r in pooled[a_label] if r["category"] == category]
        rb = [r for r in pooled[b_label] if r["category"] == category]
        delta = _rate(rb) - _rate(ra)
        print(f"  {category:<12s} {sum(1 for r in ra if r['success']):>4d}/{len(ra):<5d} "
              f"{sum(1 for r in rb if r['success']):>4d}/{len(rb):<5d}  {delta:+.0%}")

    # ---- cycle time ---- #
    ta = statistics.median([r["ticks"] for r in pooled[a_label]])
    tb = statistics.median([r["ticks"] for r in pooled[b_label]])
    print(f"  median cycle: {a_label} {ta:.0f} ticks, {b_label} {tb:.0f} ticks "
          f"({(tb - ta) / ta:+.1%})")

    # ---- failure reasons ---- #
    def reasons(rows):
        out = set()
        for r in rows:
            if r["success"]:
                continue
            text = r["notes"].strip("[]").strip()
            key = "empty note" if not text else re.sub(r"[-+0-9.]+", "#", text)
            out.add(key)
        return out

    ra, rb = reasons(pooled[a_label]), reasons(pooled[b_label])
    new = sorted(rb - ra)
    print(f"  failure reasons {a_label}: {sorted(ra) or 'none'}")
    print(f"  failure reasons {b_label}: {sorted(rb) or 'none'}")
    if new:
        print(f"  NEW failure reasons in {b_label}: {new}")

    # ---- verdict ---- #
    rate_a, rate_b = _rate(pooled[a_label]), _rate(pooled[b_label])
    straw_a = [r for r in pooled[a_label] if r["category"] == "strawberry"]
    straw_b = [r for r in pooled[b_label] if r["category"] == "strawberry"]
    strawberry_ok = (not straw_a) or (not straw_b) or _rate(straw_b) >= _rate(straw_a)
    success_ok = rate_b >= rate_a
    beats = success_ok and p <= 0.05 and better > worse
    faster = (tb <= 0.95 * ta) and rate_b >= rate_a
    improved = (beats or faster) and strawberry_ok and not new
    print()
    print(f"  criteria: rate {b_label} {rate_b:.0%} vs {a_label} {rate_a:.0%} "
          f"[{'ok' if success_ok else 'worse'}]; "
          f"sign p={p:.4f} [{'ok' if p <= 0.05 and better > worse else 'no'}]; "
          f"strawberry {_rate(straw_b):.0%} vs {_rate(straw_a):.0%} "
          f"[{'ok' if strawberry_ok else 'worse'}]; new reasons {'none' if not new else new}; "
          f"cycle {tb:.0f} vs {ta:.0f} ({'>=5% faster' if tb <= 0.95 * ta else 'not faster'})")
    if improved:
        print(f"  VERDICT: {b_label} PASSES the improvement criterion")
        return 0
    print(f"  VERDICT: no measured improvement of {b_label} over {a_label} "
          f"(publish the negative and re-plan)")
    return 1


# ------------------------------------------------------------------------- #
def _line(index, category, diameter, success, ticks, notes="[]", reward=0.9,
          decision=400):
    return (
        f"[fruit] [rl] episode {index}: {category} d={diameter}cm bin=1 arm=right "
        f"success={success} grasped=True placed={str(success)} ticks={ticks} "
        f"decision={decision} reward={reward:.4f} notes={notes} "
        f"presentation=direct ablate=none"
    )


def self_test() -> int:
    """Offline check: parser, pairing, sign test and the verdict branches."""
    failures = []
    import contextlib
    import io

    def quiet_report(directory):
        with contextlib.redirect_stdout(io.StringIO()):
            return report(directory, "A", "B")

    with tempfile.TemporaryDirectory() as tmp:
        # Scenario 1: the candidate (B) fixes 8 of the baseline's failures.
        with open(os.path.join(tmp, "A_1.log"), "w", encoding="utf-8") as fh:
            for i in range(10):
                ok = i >= 8  # 8 failures
                fh.write(_line(i, "strawberry" if i % 2 else "lychee",
                               "3.4" if i % 2 else "3.1", ok, 700 + i) + "\n")
        with open(os.path.join(tmp, "B_1.log"), "w", encoding="utf-8") as fh:
            for i in range(10):
                fh.write(_line(i, "strawberry" if i % 2 else "lychee",
                               "3.4" if i % 2 else "3.1", True, 640 + i) + "\n")
        arms = load(tmp, "A", "B")
        if len(arms["A"][1]) != 10 or len(arms["B"][1]) != 10:
            failures.append("parser did not read 10 episodes per arm")
        if not arms["A"][1][9]["success"] or arms["A"][1][0]["success"]:
            failures.append("success flag parsed wrong")
        p = sign_test_p(8, 0)
        if abs(p - 1 / 256) > 1e-12:
            failures.append(f"sign test wrong: {p}")
        if sign_test_p(0, 4) != 1.0 or abs(sign_test_p(4, 0) - 0.0625) > 1e-12:
            failures.append("sign test tail wrong")
        code = quiet_report(tmp)
        if code != 0:
            failures.append("candidate-better scenario did not pass")

        # Scenario 2: the candidate is worse - verdict must be negative.
        with open(os.path.join(tmp, "B_1.log"), "w", encoding="utf-8") as fh:
            for i in range(10):
                ok = i >= 8  # now B fails where A failed, but B also fails 2 A won
                fh.write(_line(i, "strawberry" if i % 2 else "lychee",
                               "3.4" if i % 2 else "3.1", i not in (6, 7, 8, 9), 800 + i) + "\n")
        code = quiet_report(tmp)
        if code == 0:
            failures.append("candidate-worse scenario was marked a pass")

        # Scenario 3: same fruits but a new failure reason must block a pass.
        # A fails 8/10 with the baseline reason; B fixes 6 of them but its two
        # remaining failures carry a reason A never produced.
        with open(os.path.join(tmp, "A_1.log"), "w", encoding="utf-8") as fh:
            for i in range(10):
                fh.write(_line(i, "lychee", "3.1", i >= 8, 700 + i,
                               notes="['fruit fell off the line']") + "\n")
        with open(os.path.join(tmp, "B_1.log"), "w", encoding="utf-8") as fh:
            for i in range(10):
                fh.write(_line(i, "lychee", "3.1", i >= 2, 640 + i,
                               notes="[]" if i >= 2 else "['grip lost at lift']") + "\n")
        code = quiet_report(tmp)
        if code == 0:
            failures.append("new failure reason did not block the pass")

    if failures:
        print("rl report self-test FAIL")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("rl report self-test PASS (parser, pairing, sign test, verdict branches)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", default="logs/rl_ab")
    parser.add_argument("--a", default="A", help="baseline arm label (file prefix before _N.log)")
    parser.add_argument("--b", default="B", help="candidate arm label")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    return report(args.directory, args.a, args.b)


if __name__ == "__main__":
    raise SystemExit(main())
