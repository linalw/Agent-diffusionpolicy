#!/usr/bin/env python3
"""P97: the adoption package's own table - the acceptance trio, the identities,
the shipped default's sanity cell, the pose rows and the census.

    python3 logs/p97/p97_report.py            # -> logs/p97/p97_report.txt
    python3 logs/p97/p97_report.py --same A B # the P96 sealed `[fruit]` stream

Delivered endpoints are P80's through `logs/p86/p86_report.py` / `p80lib`
(`p80lib.metrics`): a placement is the attempt's `t1`, the placement window is
`t_last_place - t_first_place`, the batch span is `t_last_end - t_first_start`,
and the wall comes from the `.stamps` stream. The sanity cell is **report only**
(PREREG §5); the argument is the invariant (the census) and the G1/G2/G3
identities.

Read-only.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import statistics as st
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
p86 = p96.p86
p80lib = p96.p80lib

STATS_RE = re.compile(
    r"\[fruit\] \[stats\] attempts=(\d+) successes=(\d+) diverted=(\d+) "
    r"success_rate=(\d+)% sim=([\d.]+)s total, ([\d.]+)s/attempt"
)


def md5(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.md5(fh.read()).hexdigest()


def stats(path: str) -> dict:
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            m = STATS_RE.search(line)
            if m:
                return {
                    "attempts": int(m.group(1)), "successes": int(m.group(2)),
                    "diverted": int(m.group(3)), "rate": int(m.group(4)),
                    "sim": float(m.group(5)), "per_attempt": float(m.group(6)),
                }
    return {}


def gate_verdict(out_path: str) -> str:
    if not os.path.exists(out_path):
        return "n/a"
    text = open(out_path, encoding="utf-8", errors="ignore").read()
    fp = "matches" if "fingerprint: matches" in text else (
        "DIFFERS" if "fingerprint: DIFFERS" in text else "n/a")
    gate = "PASS" if re.search(r"^(190: PASS|PASS: every)", text, re.M) else (
        "FAIL" if re.search(r"^(190: FAIL|FAIL:)", text, re.M) else "n/a")
    return f"fingerprint {fp}, gate {gate}"


def g3_stream(path: str) -> list[str]:
    """P96's sealed stream **minus the pre-pose row** (P97 PREREG §2 G3).

    The `[biarm] pre-pose` row is `[fruit]`-prefixed, and its `origin` label is
    the one thing the flip changes (`1(explicit)` -> `1(default)`). G3's
    registered statement is "only the origin label differs", so the comparison
    drops that one row - everything else, including both stations' achieved
    jaw/pad/tilt/margin, must be identical.
    """
    return [line for line in p96.fruit_stream_sealed(path)
            if "[biarm] pre-pose " not in line]


def show_same_g3(reference: str, candidate: str) -> int:
    a, b = g3_stream(reference), g3_stream(candidate)
    print(f"[G3] ref={reference} ({len(a)} physics lines, pre-pose row dropped)  "
          f"cand={candidate} ({len(b)})")
    if a == b:
        print("[G3] IDENTICAL - the shipped default is P96's measured arm")
        return 0
    index = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y),
                 min(len(a), len(b)))
    print(f"[G3] DIFFERS at line {index} (common prefix {index})")
    for name, stream in (("ref", a), ("cand", b)):
        if index < len(stream):
            print(f"  {name}: {stream[index][:200]}")
    return 1


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--same":
        rc = p96.show_same(sys.argv[2], sys.argv[3])
        return rc
    if len(sys.argv) > 1 and sys.argv[1] == "--same-g3":
        return show_same_g3(sys.argv[2], sys.argv[3])
    out = []

    def print_(line=""):
        out.append(line)

    print_("P97 - the clearance pre-pose ships as the two-line default")
    print_("=" * 112)
    print_("The invariant is the argument; the count is a draw. Delivered numbers are")
    print_("reports (P80/p86 endpoints), the identities and the census are the gates.")
    print_()

    # ---- section 1: the acceptance trio ------------------------------------ #
    print_("=" * 112)
    print_("1. THE ACCEPTANCE TRIO (10 attempts; the shipped default, its =0 A/B, the")
    print_("   single arm). The rate floor is the two-line 0.60 / the single-arm 0.75.")
    print_("=" * 112)
    print_(f"  {'arm-set':<22} {'placed':>8} {'s/att':>6} {'div':>4}  gate")
    default_stem = ("logs/p97/accept_final"
                    if os.path.exists(os.path.join(ROOT, "logs/p97/accept_final.log"))
                    else "logs/p97/accept_default")
    trio = [
        ("default (clearance)", default_stem),
        ("=0 (pre-P96 path)", "logs/p97/accept_pre97"),
        ("single (BIARM=0)", "logs/p97/accept_single"),
    ]
    for name, stem in trio:
        log = os.path.join(ROOT, stem + ".log")
        if not os.path.exists(log):
            print_(f"  {name:<22} MISSING {stem}.log")
            continue
        s = stats(log)
        print_(f"  {name:<22} {s.get('successes', 0):>3}/{s.get('attempts', 0):<3} "
               f"{s.get('per_attempt', float('nan')):>6.2f} {s.get('diverted', 0):>4}  "
               f"{gate_verdict(os.path.join(ROOT, stem + '.out'))}")
    print_()
    print_("  G1: the =0 arm must be 8/10, `fingerprint: matches` 30fb99f8 and 419/419")
    print_("  physics lines identical to logs/p94/accept_final.log.")
    print_("  G2: the single arm must be 346/346 raw identical to")
    print_("  logs/p71/accept_rails_none.log with the single reference; its rate-only FAIL")
    print_("  is the standing 6/9 branch (P32), not this phase's.")

    # ---- section 2: the identities ----------------------------------------- #
    print_()
    print_("=" * 112)
    print_("2. THE IDENTITIES (P96's sealed `[fruit]` stream; diag/trace rows dropped)")
    print_("=" * 112)
    pairs = [
        ("G3 default sanity cell vs P96's measured T5", "logs/p97/S5.log",
         "logs/p96/T5.log"),
        ("G1 =0 acceptance vs P94's record", "logs/p97/accept_pre97.log",
         "logs/p94/accept_final.log"),
        ("G2 single arm vs the P71 record", "logs/p97/accept_single.log",
         "logs/p71/accept_rails_none.log"),
    ]
    for label, cand, ref in pairs:
        a = os.path.join(ROOT, ref)
        b = os.path.join(ROOT, cand)
        if not (os.path.exists(a) and os.path.exists(b)):
            print_(f"  {label}: MISSING ({ref} / {cand})")
            continue
        g3 = "P96's measured T5" in label
        sa = g3_stream(a) if g3 else p96.fruit_stream_sealed(a)
        sb = g3_stream(b) if g3 else p96.fruit_stream_sealed(b)
        note = " (pre-pose row dropped)" if g3 else ""
        print_(f"  {label}: {'IDENTICAL' if sa == sb else 'DIFFERS'} "
               f"({len(sa)} vs {len(sb)} physics lines){note}")

    # ---- section 3: the sanity cell ---------------------------------------- #
    print_()
    print_("=" * 112)
    print_("3. THE SANITY CELL (seed 5, 20 attempts, FRUIT_BIARM_PREPOSE_CLEAR unset -")
    print_("   the shipped default; report only, never a rate claim)")
    print_("=" * 112)
    cell = os.path.join(ROOT, "logs/p97/S5.log")
    if not os.path.exists(cell):
        print_("  S5: MISSING (the cell has not run)")
    else:
        data = p86.cell(cell)
        m, extra = data["m"], data["extra"]
        s = m.get("stats") or {}
        sv = stats(cell)
        print_(f"  placed {m['placed']}/{m['attempts']} = "
               f"{100.0 * m['placed'] / max(1, m['attempts']):.1f} %   "
               f"{s.get('per_attempt', float('nan')):.2f} s/attempt   "
               f"diverted {sv.get('diverted', '?')}")
        print_(f"  interval mean {m['pooled']['mean']:.2f} s  p90 {m['pooled']['p90']:.2f} s   "
               f"window {m['window_rate']:.2f} / batch {m['batch_rate']:.2f} placed/min   "
               f"wall {s.get('wall', float('nan')):.1f} s   "
               f"wall/pick {s.get('wall_per_pick', float('nan')):.2f} s   "
               f"placed/min wall {60.0 * m['placed'] / s['wall']:.2f}")
        b = (s.get("biarm") or {})
        print_(f"  per arm left {b.get('l')}/{b.get('la')}  right {b.get('r')}/{b.get('ra')}")
        print_(f"  classes {m['classes']}")
        print_(f"  reasons {m['reasons']}")
        spans = [x["span"] for x in extra["cycles"]]
        blocks = {k: [x["blocks"].get(k) for x in extra["cycles"] if k in x["blocks"]]
                  for k in ("prepose", "hover", "descent", "close", "grip", "lift",
                            "place", "release", "return")}
        print_(f"  span p50 {st.median(spans):.2f} s; blocks p50 " + " ".join(
            f"{k}={st.median(v):.2f}" for k, v in blocks.items() if v))
        guest = [t for t in extra["traces"] if t["bottom"] >= 0.0]
        lost = [t for t in extra["traces"] if t["bottom"] < 0.0]
        print_(f"  landing: {len(guest)} payload-present releases, "
               f"on_belt {sum(1 for t in guest if t['on_belt'])}/{len(guest)}; "
               f"off-belt/upstream-lost traces {len(lost)} (reported separately)")
        print_(f"  descent budgets: see logs/p97/S5.budgets (105, budgets only)")

    # ---- section 4: the pose rows ------------------------------------------ #
    print_()
    print_("=" * 112)
    print_("4. THE POSE (the `[biarm] pre-pose` rows: a log field, one row per station)")
    print_("=" * 112)
    for name, path in (("default acceptance", "logs/p97/accept_default.log"),
                       ("sanity cell S5", "logs/p97/S5.log")):
        p = os.path.join(ROOT, path)
        if not os.path.exists(p):
            continue
        rows = p96.prepose_rows(p)
        if not rows:
            print_(f"  {name}: no `[biarm] pre-pose` row")
            continue
        for r in rows:
            print_(f"  {name:<20} {r['arm']:<5} jaw belt_top+{r['jaw']:.3f} "
                   f"pad belt_top+{r['pad']:.3f} tilt {r['tilt']:.1f}deg "
                   f"margin {r['margin']:+.3f}@j{r['joint']} res {r['residual']:.1f} mm "
                   f"-> {r['verdict']}")

    # ---- section 5: the census --------------------------------------------- #
    print_()
    print_("=" * 112)
    print_("5. THE CENSUS (logs/p97/census.txt, P95/P96's instrument and criterion)")
    print_("=" * 112)
    census = os.path.join(ROOT, "logs/p97/census.txt")
    if os.path.exists(census):
        for line in open(census, encoding="utf-8"):
            text = line.rstrip("\n")
            if text.startswith("  n=") or text.startswith("  left") or \
                    text.startswith("  right") or "CONTACTS" in text:
                print_("  " + text.strip())
    else:
        print_("  NO census.txt - run `python3 logs/p97/census.py` first")

    # ---- section 6: references and provenance ------------------------------- #
    print_()
    print_("=" * 112)
    print_("6. REFERENCES, ARCHIVES AND PROVENANCE")
    print_("=" * 112)
    for path in ("configs/motion_reference.json", "configs/motion_reference_twoline.json",
                 "configs/motion_reference_single.json",
                 "logs/p97/motion_reference_pre_p97.json",
                 "logs/p97/motion_reference_twoline_pre_p97.json"):
        p = os.path.join(ROOT, path)
        print_(f"  {path:<58} {md5(p) if os.path.exists(p) else 'MISSING'}")
    manifest = os.path.join(ROOT, "logs/p97/shard_manifest.json")
    if os.path.exists(manifest):
        with open(manifest, encoding="utf-8") as fh:
            doc = json.load(fh)
        coll = doc.get("collection") or {}
        print_(f"  fresh shard: collection.prepose_clear={coll.get('prepose_clear')} "
               f"defaulted={coll.get('prepose_clear_defaulted')} "
               f"z={coll.get('prepose_clear_z')} "
               f"mode={coll.get('mode')} biarm_twoline={coll.get('biarm_twoline_resolved')}")
        print_(f"  fresh shard also carries scene={'scene' in doc} "
               f"supply.band={'band' in (doc.get('supply') or {})} "
               f"physics.release={'release' in (doc.get('physics') or {})}")
    else:
        print_("  no logs/p97/shard_manifest.json (the fresh-shard probe has not run)")

    text = "\n".join(out)
    print(text)
    with open(os.path.join(HERE, "p97_report.txt"), "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
