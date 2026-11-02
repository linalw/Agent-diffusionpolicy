#!/usr/bin/env python3
"""P98: the revert's own table - the flip-back, the restored references, the
acceptance reading and the `=1` A/B.

    python3 logs/p98/p98_report.py            # -> logs/p98/p98_report.txt
    python3 logs/p98/p98_report.py --check    # assert P1/P2 (exit 1 on a miss)
    python3 logs/p98/p98_report.py --same REF CAND        # the P96 sealed stream
    python3 logs/p98/p98_report.py --same-pose REF CAND   # ... + pre-pose rows

Read-only. `--same` is `logs/p96/p96_report.py`'s sealed `[fruit]` filter (the
P84/P85 diag rows + P95's `[ftrace]` arming row); `--same-pose` additionally
drops the two `[fruit] [biarm] pre-pose` rows, whose only cross-cell difference
is the registered origin label (`1(default)` vs `1(explicit)`) - the P97 G3
convention.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


p96 = _load("p96_report", os.path.join(ROOT, "logs", "p96", "p96_report.py"))

STATS_RE = re.compile(
    r"\[fruit\] \[stats\] attempts=(\d+) successes=(\d+) diverted=(\d+) "
    r"success_rate=(\d+)% sim=([\d.]+)s total, ([\d.]+)s/attempt"
)
CONST_RE = re.compile(r"^PREPOSE_CLEAR_TWO_LINE_DEFAULT = (True|False)$", re.M)

ACCEPT = {
    "accept_revert": "logs/p98/accept_revert.log",
    "accept_clear1": "logs/p98/accept_clear1.log",
}
P94 = "logs/p94/accept_final.log"
P97 = "logs/p97/accept_final.log"
ARCHIVE = "logs/p97/motion_reference_pre_p97.json"


def md5(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.md5(fh.read()).hexdigest()


def stats(path: str) -> dict:
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            m = STATS_RE.search(line)
            if m:
                return {
                    "attempts": int(m.group(1)),
                    "successes": int(m.group(2)),
                    "diverted": int(m.group(3)),
                    "rate": int(m.group(4)),
                    "sim": float(m.group(5)),
                    "per_attempt": float(m.group(6)),
                }
    return {}


def verdict(path: str) -> list[str]:
    out = []
    full = os.path.join(ROOT, path.replace(".log", ".out"))
    for line in open(full, encoding="utf-8", errors="ignore"):
        if "fingerprint:" in line or line.startswith("190:") or "PASS" in line \
                and "motion gate" in line:
            out.append(line.strip())
    return out


def stream(path: str, drop_pose: bool) -> list[str]:
    rows = p96.fruit_stream_sealed(path)
    if drop_pose:
        rows = [r for r in rows if "[biarm] pre-pose" not in r]
    return rows


def show_same(reference: str, candidate: str, drop_pose: bool) -> int:
    a, b = stream(reference, drop_pose), stream(candidate, drop_pose)
    tag = "same-pose" if drop_pose else "same"
    print(f"[{tag}] ref={reference} ({len(a)} lines)  cand={candidate} ({len(b)})")
    if a == b:
        print(f"[{tag}] IDENTICAL on every physics line")
        return 0
    index = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    print(f"[{tag}] DIFFERS at line {index} (common prefix {index})")
    for name, rows in (("ref", a), ("cand", b)):
        if index < len(rows):
            print(f"  {name}: {rows[index][:200]}")
    return 1


def check() -> int:
    ok = True
    src = open(os.path.join(ROOT, "src", "fruit_sorting", "tasks.py"),
               encoding="utf-8").read()
    value = CONST_RE.search(src)
    print(f"[check] PREPOSE_CLEAR_TWO_LINE_DEFAULT = {value.group(1) if value else '?'}")
    ok &= bool(value and value.group(1) == "False")

    refs = ["configs/motion_reference.json", "configs/motion_reference_twoline.json"]
    arch = md5(os.path.join(ROOT, ARCHIVE))
    for ref in refs:
        got = md5(os.path.join(ROOT, ref))
        print(f"[check] {ref} = {got} (archive {arch})")
        ok &= got == "30fb99f8"[:8] or got == arch
    single = md5(os.path.join(ROOT, "configs/motion_reference_single.json"))
    print(f"[check] configs/motion_reference_single.json = {single}")
    ok &= single == "8952c320d798ef42e03ba815c9e96b23"

    s = stats(os.path.join(ROOT, ACCEPT["accept_revert"]))
    print(f"[check] accept_revert: {s}")
    ok &= s.get("successes") == 8 and s.get("attempts") == 10
    rows_a = stream(os.path.join(ROOT, ACCEPT["accept_revert"]), False)
    rows_b = stream(os.path.join(ROOT, P94), False)
    print(f"[check] accept_revert vs p94: {len(rows_a)} / {len(rows_b)} sealed lines")
    ok &= rows_a == rows_b
    out = open(os.path.join(ROOT, "logs/p98/accept_revert.out"),
               encoding="utf-8", errors="ignore").read()
    ok &= "fingerprint: matches" in out and "190: PASS" in out

    s1 = stats(os.path.join(ROOT, ACCEPT["accept_clear1"]))
    print(f"[check] accept_clear1: {s1}")
    ok &= s1.get("successes") == 6 and s1.get("attempts") == 10
    rows_c = stream(os.path.join(ROOT, ACCEPT["accept_clear1"]), True)
    rows_d = stream(os.path.join(ROOT, P97), True)
    print(f"[check] accept_clear1 vs p97 (-pre-pose): {len(rows_c)} / {len(rows_d)} lines")
    ok &= rows_c == rows_d

    print("[check] PASS" if ok else "[check] FAIL")
    return 0 if ok else 1


def main() -> int:
    if len(sys.argv) > 2 and sys.argv[1] == "--same":
        return show_same(sys.argv[2], sys.argv[3], False)
    if len(sys.argv) > 2 and sys.argv[1] == "--same-pose":
        return show_same(sys.argv[2], sys.argv[3], True)
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        return check()

    print("P98 - the P97 revert: the clearance pre-pose is opt-in again")
    print("=" * 78)
    src = open(os.path.join(ROOT, "src", "fruit_sorting", "tasks.py"),
               encoding="utf-8").read()
    m = CONST_RE.search(src)
    print(f"\n[flip] PREPOSE_CLEAR_TWO_LINE_DEFAULT = {m.group(1) if m else '?'}"
          "  (unset -> the pre-P96 path; =1 arms P96's pose)")
    print("\n[references]")
    for ref in ("configs/motion_reference.json", "configs/motion_reference_twoline.json",
                "configs/motion_reference_single.json"):
        print(f"  {ref}: {md5(os.path.join(ROOT, ref))}")
    print(f"  archive: {ARCHIVE}: {md5(os.path.join(ROOT, ARCHIVE))}")

    print("\n[acceptance]")
    for tag, path in ACCEPT.items():
        s = stats(os.path.join(ROOT, path))
        print(f"  {tag}: {s.get('successes')}/{s.get('attempts')} "
              f"({s.get('rate')}%), {s.get('per_attempt')} s/attempt, "
              f"diverted={s.get('diverted')}, sim={s.get('sim')} s")
        for line in verdict(path):
            print(f"    {line}")

    print("\n[identities]")
    print(f"  accept_revert vs {P94}:")
    show_same(os.path.join(ROOT, P94), os.path.join(ROOT, ACCEPT["accept_revert"]), False)
    print(f"  accept_clear1 vs {P97} (pre-pose rows dropped):")
    show_same(os.path.join(ROOT, P97), os.path.join(ROOT, ACCEPT["accept_clear1"]), True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
