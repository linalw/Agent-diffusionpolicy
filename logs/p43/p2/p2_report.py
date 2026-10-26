"""P43 phase 2 report: the L1 wait/selection endpoints + L2's loop split.

    python3 logs/p43/p2/p2_report.py > logs/p43/p2/p2_report.txt
    python3 logs/p43/p2/p2_report.py --identity   # the stream-identity checks
    python3 logs/p43/p2/p2_report.py --bed logs/p43/p2/d0_accept_A_s5.log

Reads only the logs; no simulator. Everything it prints is re-derivable from a
`[bed-sel]` / `[fruit]` / `[rl]` row.

Sections
  1  D0 census          the usable set, the near-vs-far along delta, the affected
                        fraction, and the pre-registered E1 prediction
  2  the batteries      attempts / placed / span / s-per-attempt / waits / diverted
  3  the mechanism       per-attempt windows + the chosen along (the L1 endpoint)
  4  the cycle          the per-attempt phase decomposition
  5  the direct gate     the `[rl] episode ... y=` selection rows (F5)
  6  the loop split      the per-decision wall decomposition (L2 step 1)
  7  identity            `[fruit]`-stream byte identity between named pairs
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

BED = re.compile(r"\[bed-sel\] attempt (\d+) .*?window=(\d+) .*?pick=(\S+)")
BED_ROW = re.compile(
    r"\[bed-sel\]   (\S+)\s+along=([+-][0-9.]+) x=([+-]?[0-9.]+) .*?-> (.+)$")
CYCLE = re.compile(r"\[cycle\] attempt (\d+): (.*)$", re.MULTILINE)
WAIT = re.compile(r"fruit at pick point: dy=([+-][0-9.]+) m arrived=(\w+) after (\d+) steps")
STATS = re.compile(r"\[stats\] attempts=(\d+) successes=(\d+) diverted=(\d+).*?"
                   r"sim=([0-9.]+)s total, ([0-9.]+)s/attempt.*?"
                   r"gate_open=([0-9.]+)s total, queue_peak=(\d+) recirculated=(\d+)")
PICK = re.compile(r"\[run\] attempt (\d+): picking (\S+) grade (\S) into output lane (\d)")
RESULT = re.compile(
    r"\[run\] attempt (\d+): grasped=(\w+) placed=(\w+) lift=([+-][0-9.]+) m "
    r"force=([0-9.]+) N notes=\[(.*?)\] sim=([0-9.]+)-([0-9.]+)s")
RL_SELECT = re.compile(r"\[rl\] episode (\d+): (\S+) grade=(\S) d=([0-9.]+)cm "
                       r"bin=(\d) arm=(\S+) y=([+-][0-9.]+) presentation=(\S+)")
RL_EP = re.compile(r"\[rl\] episode (\d+): (\S+) d=([0-9.]+)cm bin=(\d) arm=(\S+) "
                   r"success=(\w+) grasped=(\w+) placed=(\w+) ticks=(\d+)")
LOOP = re.compile(r"\[loop\] ep=(\d+) wall=([0-9.]+)s sim=([0-9.]+)s sim/wall=([0-9.]+) "
                  r"decisions=(\d+) obs=(\d+) \| ms/decision: policy=([0-9.]+) "
                  r"render=([0-9.]+) camera=([0-9.]+) other=([0-9.]+) \| share: "
                  r"policy=([0-9.]+)% render=([0-9.]+)% camera=([0-9.]+)% other=([0-9.]+)%")
RTC = re.compile(r"\[rtc\] summary: steps=(\d+) chunks=(\d+) decisions=(\d+) "
                 r"decisions/s=([0-9.]+).*?policy_ms/step ([0-9.]+).*?"
                 r"control_ms n=(\d+) med=([0-9.]+) p90=([0-9.]+) max=([0-9.]+)")
RUNWALL = re.compile(r"\[rl\] run wall end [0-9.]+ duration ([0-9.]+)s")
BIARM_STATS = re.compile(r"\[biarm\] .*?placed/min")


def read(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


INSTRUMENT_TAGS = (
    "[bed-sel]", "[bed-fall]", "[cycle]", "[carry]", "[diag]", "[seat]",
    "[attitude]", "[biarm]",
)


def fruit_lines(path: str) -> list[str]:
    """The `[fruit]` physics stream, instrument rows dropped (AGENTS section 2).

    The filter is the union of the instruments present in these logs (`[bed-sel]`
    / `[bed-fall]` = `FRUIT_BED_DIAG`, `[cycle]` = `FRUIT_CYCLE_REPORT`,
    `[carry]`/`[diag]` = `FRUIT_CARRY_DIAG`/`FRUIT_CLOSURE_DEBUG`, `[seat]`,
    `[attitude]`), so a pair that differs only by an instrument still reads
    IDENTICAL - which is what a print-only claim means.
    """
    return [
        line for line in read(path).splitlines()
        if "[fruit]" in line
        and not any(tag in line for tag in INSTRUMENT_TAGS)
    ]


def stats(text: str) -> dict:
    m = STATS.search(text)
    if not m:
        return {}
    return {
        "attempts": int(m.group(1)),
        "placed": int(m.group(2)),
        "diverted": int(m.group(3)),
        "sim": float(m.group(4)),
        "s_per_attempt": float(m.group(5)),
        "gate_open": float(m.group(6)),
        "queue_peak": int(m.group(7)),
        "recirculated": int(m.group(8)),
        # the tray discharge rows (`[belt] ... discharged to the ...`), i.e. the
        # payloads that reached the output belt's tray
        "discharged": text.count("discharged to the"),
    }


def waits(text: str) -> list[float]:
    return [int(m.group(3)) / 120.0 for m in WAIT.finditer(text)]


def picks(text: str) -> list[tuple[str, str, int]]:
    return [(m.group(2), m.group(3), int(m.group(1))) for m in PICK.finditer(text)]


def results(text: str) -> dict[int, dict]:
    out = {}
    for m in RESULT.finditer(text):
        out[int(m.group(1))] = {
            "grasped": m.group(2) == "True",
            "placed": m.group(3) == "True",
            "lift": float(m.group(4)),
            "notes": m.group(6),
            "sim": float(m.group(8)) - float(m.group(7)),
        }
    return out


def cycle_rows(text: str) -> dict[int, dict[str, float]]:
    rows = {}
    for m in CYCLE.finditer(text):
        row = {}
        for part in m.group(2).split():
            if "=" in part:
                key, value = part.split("=", 1)
                row[key] = float(value.rstrip("s"))
        rows[int(m.group(1))] = row
    return rows


def bed_census(text: str) -> list[dict]:
    """One entry per `[bed-sel] attempt` block: the window and its rows."""
    lines = text.splitlines()
    entries = []
    current = None
    for line in lines:
        head = BED.search(line)
        if head:
            current = {
                "attempt": int(head.group(1)),
                "window": int(head.group(2)),
                "pick": head.group(3),
                "chosen_along": None,
                "rows": [],
            }
            if current["pick"] != "none" and "@" in current["pick"]:
                current["chosen_along"] = float(current["pick"].split("@")[1])
            entries.append(current)
            continue
        row = BED_ROW.search(line)
        if row and current is not None:
            reason = row.group(4).strip()
            current["rows"].append(
                {"category": row.group(1), "along": float(row.group(2)),
                 "x": float(row.group(3)), "reason": reason}
            )
    for entry in entries:
        usable = [r["along"] for r in entry["rows"]
                  if r["reason"] in ("usable", "chosen")]
        entry["usable"] = sorted(usable)
    return entries


def fmt_ms(values: list[float]) -> str:
    if not values:
        return "n/a"
    return (f"mean {st.mean(values):.2f} median {st.median(values):.2f} "
            f"min {min(values):.2f} max {max(values):.2f}")


# --------------------------------------------------------------------------- #
# 1. D0 census
# --------------------------------------------------------------------------- #
def section_bed(paths: list[str]) -> None:
    print("## 1. D0 census (`FRUIT_BED_DIAG=1`, the control arm)\n")
    for path in paths:
        text = read(path)
        entries = bed_census(text)
        if not entries:
            print(f"{os.path.basename(path)}: no `[bed-sel]` rows\n")
            continue
        print(f"### {os.path.basename(path)}")
        print("| attempt | window | usable along (m) | near | far | far-near (m) | "
              "chosen | chosen-far (m) |")
        print("| --- | --- | --- | --- | --- | --- | --- | --- |")
        deltas = []
        for entry in entries:
            usable = entry["usable"]
            chosen = entry["chosen_along"]
            if usable:
                near, far = usable[0], usable[-1]
                delta = far - near
                deltas.append(delta)
                drop = (far - chosen) if chosen is not None else 0.0
                print(f"| {entry['attempt']} | {entry['window']} | "
                      f"{', '.join(f'{u:+.3f}' for u in usable)} | {near:+.3f} | "
                      f"{far:+.3f} | {delta:.3f} | "
                      f"{'n/a' if chosen is None else f'{chosen:+.3f}'} | {drop:+.3f} |")
            else:
                print(f"| {entry['attempt']} | {entry['window']} | (none) | - | - | - | "
                      f"{'n/a' if chosen is None else f'{chosen:+.3f}'} | - |")
        affected = [d for d in deltas if d > 1e-9]
        windows = [len(entry["usable"]) for entry in entries if entry["usable"]]
        print()
        print(f"* attempts with a window: **{len(windows)}/{len(entries)}**; "
              f"usable set size: {fmt_ms([float(w) for w in windows]) if windows else 'n/a'}")
        print(f"* affected attempts (window >= 2, i.e. nearest != farthest): "
              f"**{len(affected)}/{len(entries)} = "
              f"{len(affected) / max(len(entries), 1):.1%}**")
        # The rule's drop is 0 on an unaffected attempt, so the **per-attempt**
        # mean (the unit E1 is stated in) is sum(deltas)/attempts; the
        # affected-only mean is the conditional magnitude.
        per_attempt = sum(deltas) / max(len(entries), 1)
        if affected:
            mean_delta = st.mean(affected)
            print(f"* along delta, affected attempts only: {fmt_ms(affected)}")
            print(f"* along delta, **per attempt** (0 on the {len(entries) - len(affected)} "
                  f"unaffected): {per_attempt:.4f} m")
            print(f"* **E1 prediction** = 0.6 x (mean along drop / 0.12 m/s) = "
                  f"0.6 x ({per_attempt:.4f} / 0.12) = "
                  f"**{0.6 * per_attempt / 0.12:.3f} s** "
                  f"(undiscounted: {per_attempt / 0.12:.3f} s; "
                  f"the affected-only form would read {0.6 * mean_delta / 0.12:.3f} s)")
            big = [d for d in affected if d >= 0.10]
            print(f"* mechanism endpoint (chosen-along drop >= 0.10 m): "
                  f"**{len(big)}/{len(entries)} = {len(big) / max(len(entries), 1):.1%}** "
                  f"of all attempts, {len(big)}/{len(affected)} of the affected ones")
        print()


# --------------------------------------------------------------------------- #
# 2/3. the batteries
# --------------------------------------------------------------------------- #
def section_battery(paths: list[str]) -> None:
    print("## 2. The batteries (per run)\n")
    print("| run | attempts | placed | span (s) | s/attempt | wait mean | wait median "
          "| diverted | discharged | recirc | queue_peak | gate_open |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for path in paths:
        text = read(path)
        s = stats(text)
        w = waits(text)
        name = os.path.basename(path).replace(".log", "")
        if not s:
            print(f"| {name} | (no `[stats]` row) | | | | | | | | | | |")
            continue
        print(f"| {name} | {s['attempts']} | {s['placed']} | {s['sim']:.1f} | "
              f"{s['s_per_attempt']:.2f} | "
              f"{st.mean(w):.2f} | {st.median(w):.2f} | {s['diverted']} | "
              f"{s['discharged']} | {s['recirculated']} | {s['queue_peak']} | "
              f"{s['gate_open']:.1f} |")
    print()
    if len(paths) >= 2:
        print("Wait distributions (per attempt, seconds):\n")
        for path in paths:
            w = waits(read(path))
            name = os.path.basename(path).replace(".log", "")
            print(f"* `{name}`: n={len(w)} [{', '.join(f'{v:.2f}' for v in w)}]")
        print()


def section_sequence(paths: list[str]) -> None:
    print("## 3. The fruit sequence per attempt (A vs B)\n")
    for path in paths:
        text = read(path)
        picked = picks(text)
        res = results(text)
        name = os.path.basename(path).replace(".log", "")
        body = []
        for category, grade, attempt in picked:
            outcome = res.get(attempt, {})
            mark = "P" if outcome.get("placed") else ("c" if outcome.get("grasped") else "x")
            body.append(f"{attempt}:{category}/{grade}/{mark}")
        print(f"* `{name}`: {'  '.join(body)}")
    print()
    print("`P` placed, `c` carried-not-placed (grasped, not placed), `x` no grasp.\n")


# --------------------------------------------------------------------------- #
# 4. the cycle
# --------------------------------------------------------------------------- #
def section_cycle(paths: list[str]) -> None:
    print("## 4. The `[cycle]` decomposition (means over the attempts that print it)\n")
    keys = ["prepose", "hover", "descent", "close", "grip", "lift", "place",
            "release", "return", "end", "total"]
    print("| run | " + " | ".join(keys) + " |")
    print("| --- " * (len(keys) + 1) + "|")
    for path in paths:
        rows = cycle_rows(read(path))
        if not rows:
            print(f"| {os.path.basename(path).replace('.log', '')} | "
                  + " | ".join("n/a" for _ in keys) + " |")
            continue
        cells = []
        for key in keys:
            values = [row[key] for row in rows.values() if key in row]
            cells.append(f"{st.mean(values):.2f} (n={len(values)})" if values else "-")
        print(f"| {os.path.basename(path).replace('.log', '')} | "
              + " | ".join(cells) + " |")
    print()


# --------------------------------------------------------------------------- #
# 5. the direct gate (F5)
# --------------------------------------------------------------------------- #
def section_direct(paths: list[str]) -> None:
    print("## 5. The direct/policy selection rows (F5)\n")
    for path in paths:
        text = read(path)
        rows = [m.groups() for m in RL_SELECT.finditer(text)]
        eps = [m.groups() for m in RL_EP.finditer(text)]
        print(f"### {os.path.basename(path)}")
        for row in rows:
            print(f"* select ep{row[0]}: {row[1]} grade={row[2]} d={row[3]}cm "
                  f"bin={row[4]} arm={row[5]} **y={row[6]}**")
        for row in eps:
            print(f"* outcome ep{row[0]}: {row[1]} d={row[2]}cm bin={row[3]} "
                  f"arm={row[4]} success={row[5]} grasped={row[6]} placed={row[7]} "
                  f"ticks={row[8]}")
        m = RUNWALL.search(text)
        if m:
            print(f"* run wall (episode loop): {m.group(1)}s")
        print()


# --------------------------------------------------------------------------- #
# 6. the loop split (L2)
# --------------------------------------------------------------------------- #
def section_loop(paths: list[str]) -> None:
    print("## 6. The policy loop's wall split (L2 step 1)\n")
    for path in paths:
        text = read(path)
        rows = [m.groups() for m in LOOP.finditer(text)]
        print(f"### {os.path.basename(path)}")
        if rows:
            print("| ep | wall (s) | sim (s) | sim/wall | decisions | obs | "
                  "policy ms/dec | render ms/obs | camera ms/obs | "
                  "other ms/decision-equivalent |")
            print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
            for r in rows:
                print(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | "
                      f"{r[6]} | {r[7]} | {r[8]} | {r[9]} |")
            print()
            print("shares per episode: "
                  + "  ".join(f"ep{r[0]} policy {r[10]}% render {r[11]}% "
                              f"camera {r[12]}% other {r[13]}%" for r in rows))
        else:
            print("(no `[loop]` rows)")
        m = RTC.search(text)
        if m:
            print(f"\n`[rtc] summary`: steps={m.group(1)} chunks={m.group(2)} "
                  f"decisions={m.group(3)} decisions/s={m.group(4)} "
                  f"policy_ms/step={m.group(5)} control_ms med={m.group(7)} "
                  f"p90={m.group(8)} max={m.group(9)}")
        m = RUNWALL.search(text)
        if m:
            print(f"`[rl] run wall`: {m.group(1)}s")
        print("`policy` / `render` / `camera` are the three stages a decision owns (the")
        print("model call, `RenderingManager.render()`, the `get_data` reads). **`other`")
        print("is not a per-decision cost**: it is the episode wall minus those three,")
        print("divided by the decisions, and it contains the *scripted primitive phase*")
        print("(which has no decisions at all) plus the stepping, `ik_step` and the")
        print("observation assembly. Read the shares, not the `other` ms.\n")


# --------------------------------------------------------------------------- #
# 7. identity
# --------------------------------------------------------------------------- #
IDENTITY_PAIRS = [
    # (label, left log, right log)  - `[fruit]`-stream byte identity
    ("L1 no-harm: A(seed 5, knob=0) vs the P41 acceptance record",
     "logs/p43/p2/d0_accept_A_s5.log", "logs/p41/p2/accept_profile.log"),
    ("L1 no-harm: A(pear, seed 5, knob=0) vs the P41 pear record",
     "logs/p43/p2/d0_pear_A_s5.log", "logs/p41/p2/pear_profile.log"),
    ("L1 print-only: B(seed 5, default) vs B(seed 5, +BED_DIAG)",
     "logs/p43/p2/r_accept_B_s5.log", "logs/p43/p2/r_accept_B_s5_diag.log"),
    ("L1 print-only (pear): B(seed 5) vs B(seed 5, +BED_DIAG)",
     "logs/p43/p2/r_pear_B_s5.log", "logs/p43/p2/r_pear_B_s5_diag.log"),
    ("L1 shared-station: A(knob=0) vs B(default)",
     "logs/p43/p2/biarm_A_s5.log", "logs/p43/p2/biarm_B_s5.log"),
    # the revert (the flip measured and not adopted): the shipped default must be
    # the pre-P43 pick, and the treatment must be one env var away
    ("revert: unset (shipped default) vs the knob-0 control",
     "logs/p43/p2/post_revert_accept_unset.log", "logs/p43/p2/d0_accept_A_s5.log"),
    ("revert: =1 vs the measured treatment",
     "logs/p43/p2/post_revert_accept_k1.log", "logs/p43/p2/r_accept_B_s5.log"),
]


def section_identity(only_pairs=None) -> None:
    print("## 7. The `[fruit]`-stream identity checks\n")
    for label, left, right in IDENTITY_PAIRS:
        if only_pairs and not any(p in label for p in only_pairs):
            continue
        if not (os.path.exists(left) and os.path.exists(right)):
            print(f"* {label}: MISSING ({left} / {right})")
            continue
        a, b = fruit_lines(left), fruit_lines(right)
        same = a == b
        print(f"* {label}: {'IDENTICAL' if same else 'DIFFERS'} "
              f"({len(a)} vs {len(b)} `[fruit]` lines)")
        if not same:
            for index, (x, y) in enumerate(zip(a, b)):
                if x != y:
                    print(f"  - first difference at line {index}:")
                    print(f"    A: {x[:150]}")
                    print(f"    B: {y[:150]}")
                    break
    print()


PAIRS = [
    ("acceptance seed 5", "d0_accept_A_s5.log", "r_accept_B_s5.log"),
    ("acceptance seed 6", "r_accept_A_s6.log", "r_accept_B_s6.log"),
    ("pear seed 5", "d0_pear_A_s5.log", "r_pear_B_s5.log"),
    ("pear seed 6", "r_pear_A_s6.log", "r_pear_B_s6.log"),
]


def welch_ci(a: list[float], b: list[float], z: float = 1.96) -> tuple[float, float]:
    """The 95 % interval on mean(a) - mean(b) (Welch, normal approximation)."""
    if len(a) < 2 or len(b) < 2:
        return float("nan"), float("nan")
    se = (st.variance(a) / len(a) + st.variance(b) / len(b)) ** 0.5
    diff = st.mean(a) - st.mean(b)
    return diff - z * se, diff + z * se


def section_pairs() -> None:
    print("## 2b. The paired endpoints (A = knob 0, B = the scoped default)\n")
    print("| pair | wait A | wait B | delta | 95 % CI (Welch) | s/att A | s/att B "
          "| delta | attempts | placed A | placed B |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for label, left, right in PAIRS:
        lp, rp = os.path.join(HERE, left), os.path.join(HERE, right)
        if not (os.path.exists(lp) and os.path.exists(rp)):
            print(f"| {label} | (missing) | | | | | | | | | |")
            continue
        lt, rt = read(lp), read(rp)
        lw, rw = waits(lt), waits(rt)
        ls, rs = stats(lt), stats(rt)
        lo, hi = welch_ci(rw, lw)
        print(f"| {label} | {st.mean(lw):.2f} (n={len(lw)}) | "
              f"{st.mean(rw):.2f} (n={len(rw)}) | "
              f"**{st.mean(rw) - st.mean(lw):+.2f}** | "
              f"[{lo:+.2f}, {hi:+.2f}] | {ls['s_per_attempt']:.2f} | "
              f"{rs['s_per_attempt']:.2f} | "
              f"{rs['s_per_attempt'] - ls['s_per_attempt']:+.2f} | "
              f"{ls['attempts']} -> {rs['attempts']} | {ls['placed']} | {rs['placed']} |")
    print()
    print("The wait is per attempt; the per-attempt spread is ~0.8 s, so at n = 9-10 the")
    print("standard error of a mean is ~0.25 s and of the difference ~0.35 s - the 0.30 s")
    print("bar is ~1 SE (the pre-registered power note). The CI is reported, not a bar.\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bed", nargs="*", default=None)
    parser.add_argument("--identity", action="store_true")
    parser.add_argument("--only", nargs="*", default=None)
    args = parser.parse_args()

    if args.identity:
        section_identity(args.only)
        return 0
    if args.bed is not None:
        section_bed(args.bed)
        return 0

    def existing(names):
        out = []
        for name in names:
            path = os.path.join(HERE, name)
            if os.path.exists(path):
                out.append(path)
        return out

    acceptance = existing([
        "d0_accept_A_s5.log", "r_accept_B_s5.log",
        "r_accept_A_s6.log", "r_accept_B_s6.log",
    ])
    pear = existing([
        "d0_pear_A_s5.log", "r_pear_B_s5.log",
        "r_pear_A_s6.log", "r_pear_B_s6.log",
    ])
    direct = existing([
        "f5_direct_unset_e2.log", "f5_direct_off_e2.log", "f5_direct_on_e2.log",
    ])
    loop = existing(["l2_loop_timing_e5.log"])

    section_bed(acceptance[:1] + pear[:1] + existing(
        ["r_accept_B_s5_diag.log", "r_pear_B_s5_diag.log"]))
    section_battery(acceptance + pear)
    section_pairs()
    section_sequence(acceptance + pear)
    section_cycle(acceptance + pear)
    section_direct(direct)
    section_loop(loop)
    section_identity()
    return 0


if __name__ == "__main__":
    sys.exit(main())
