"""E-lane sweep report: per-setting episode outcomes for the intercept-trigger
gate sweep (direct presentation, moe_v10).

Usage:
    python3 /tmp/opencode/e_sweep_report.py logs/832_gate_sweep/*.log ...
    python3 /tmp/opencode/e_sweep_report.py --pair <logA> <logB> ...

Parses the one-line `[rl] episode ...` results; reports per setting:
success rate, intercept fires, policy closes, no-fire timeouts, grip losses,
per-class rows, and (paired mode) the per-episode agreement on (run, index).
"""
from __future__ import annotations

import re
import sys

RESULT = re.compile(
    r"\[rl\] episode (\d+): (\w+) d=([\d.]+)cm bin=(-?\d) arm=(\w+) success=(\w+) "
    r"grasped=(\w+) placed=(\w+) ticks=(\d+) decision=(\d+) reward=([-0-9.]+) "
    r"notes=(\[.*?\]) presentation"
)
START = re.compile(
    r"\[rl\] episode (\d+): (\w+) grade=(\w+) d=[\d.]+cm bin=-?\d arm=(\w+)"
)


def parse(path: str):
    episodes = []
    for line in open(path, encoding="utf-8", errors="replace"):
        m = RESULT.search(line)
        if m:
            notes = m.group(12)
            episodes.append({
                "index": int(m.group(1)), "cat": m.group(2),
                "diam": float(m.group(3)), "arm": m.group(5),
                "ok": m.group(6) == "True",
                "ticks": int(m.group(9)),
                "notes": notes,
                "fire": "intercept trigger" in notes,
                "policy": "policy closed" in notes,
                "timeout": "timeout" in notes,
                "grip": "did not follow" in notes,
            })
    return episodes


def summary(path: str) -> None:
    eps = parse(path)
    n = len(eps)
    ok = sum(e["ok"] for e in eps)
    fire = sum(e["fire"] for e in eps)
    pol = sum(e["policy"] and not e["fire"] for e in eps)
    nofire_timeout = sum(e["timeout"] and not e["fire"] and not e["policy"] for e in eps)
    grip = sum(e["grip"] for e in eps)
    fire_ok = sum(e["ok"] for e in eps if e["fire"])
    print(f"{path}")
    print(f"  n={n} success={ok}/{n} ({ok/n:.0%}) fires={fire} fire_ok={fire_ok}"
          f" policy-only={pol} nofire-timeout={nofire_timeout} grip-loss={grip}")
    classes: dict[str, list[int]] = {}
    for e in eps:
        bit = classes.setdefault(e["cat"], [0, 0])
        bit[0] += 1
        bit[1] += int(e["ok"])
    print("  class: " + "  ".join(f"{k} {v[1]}/{v[0]}" for k, v in sorted(classes.items())))
    bad = [f"{e['index']}:{e['cat'][:4]}/{e['arm'][0]}" for e in eps if not e["ok"]]
    print(f"  failures: {' '.join(bad)}")


def pair(path_a: str, path_b: str) -> None:
    a, b = parse(path_a), parse(path_b)
    by_a = {e["index"]: e for e in a}
    both_ok = both_fail = b_only = a_only = excl = 0
    for e in b:
        other = by_a.get(e["index"])
        if other is None or other["cat"] != e["cat"]:
            excl += 1
            continue
        if e["ok"] and other["ok"]:
            both_ok += 1
        elif e["ok"] and not other["ok"]:
            b_only += 1
        elif not e["ok"] and other["ok"]:
            a_only += 1
        else:
            both_fail += 1
    print(f"PAIR {path_a} (A) vs {path_b} (B): both_ok={both_ok} both_fail={both_fail} "
          f"B_only={b_only} A_only={a_only} excluded={excl}")
    if b_only + a_only:
        # exact one-sided sign test (binomial)
        from math import comb
        k = b_only
        n = b_only + a_only
        p = sum(comb(n, i) for i in range(k, n + 1)) / (2 ** n)
        print(f"  one-sided sign p={p:.4f} (discordant {n})")


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "--pair":
        pair(args[1], args[2])
        return 0
    for path in args:
        summary(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
