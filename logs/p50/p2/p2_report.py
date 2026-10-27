#!/usr/bin/env python3
"""P50 phase 2 report - the per-pool release-offset compensation, offline read.

    python3 logs/p50/p2/p2_report.py            # -> logs/p50/p2/p2_report.txt

Reads only logs (no simulator). Sections:

* **0** the two tables (what is applied per pool instance);
* **1** M1 - the isolated probe, 96 cells (16 instances x 3 planned x x 2 passes):
      the delivered x (`x_cmd + off_mm`), the cells outside `[0.180, 0.390]`,
      per instance, both arms;
* **2** M1b - the live (release-attributed) probe: the planned-x sequences must
      be identical (the supply is controlled) and `off_mm` is the **compensated
      residual** once the knob is on;
* **3** M2 - the shipped acceptance, C vs O: `[stats]`, the delivered-x rows
      (`wait step=0 fruit_x=`), the acquisition rows (`dynamic catch-up` above
      the 6 mm tolerance + `no grasp` terminals), the failure reasons
      (digit-normalised as `scripts/113_rl_report.py` does), the release shifts;
* **4** M3 - the pear pool, the same read plus the inertness identity check;
* **5** M4 - the no-harm: the physics `[fruit]` stream against
      `logs/p41/p2/accept_profile.log` (TASK) and `logs/p44/p2/accept_s5_C.log`
      (PREREG F5), where the physics stream drops the optional print-only tags
      (`[diag]`, `[carry]`, `[cycle]`, and the P50 `[offset]` row itself).
"""

from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

BAND_LO, BAND_HI = 0.180, 0.390
TOL_MM = 6.0
PRINT_ONLY = ("[fruit] [diag]", "[fruit] [carry]", "[fruit] [cycle]", "[fruit] [offset]")

STATS = re.compile(
    r"\[stats\] attempts=(?P<attempts>\d+) successes=(?P<ok>\d+) diverted=(?P<div>\d+) "
    r"success_rate=(?P<rate>\d+)% sim=(?P<sim>[\d.]+)s total, (?P<spa>[\d.]+)s/attempt"
)
ATTEMPT = re.compile(
    r"\[run\] attempt (?P<idx>\d+): grasped=(?P<grasped>\w+) placed=(?P<placed>\w+) "
    r"lift=(?P<lift>[+-][\d.]+) m force=(?P<force>[\d.]+) N notes=\[(?P<notes>.*?)\] "
    r"sim=(?P<sim>[\d.]+)-(?P<sim1>[\d.]+)s"
)
PICK = re.compile(r"\[run\] attempt (?P<idx>\d+): picking (?P<cat>\w+) grade (?P<grade>\w+)")
DELIVERED = re.compile(r"wait step=0 fruit_y=(?P<y>[+-]?[\d.]+) fruit_x=(?P<x>[+-][\d.]+)")
CATCHUP = re.compile(r"dynamic catch-up: residual=(?P<mm>[\d.]+) mm")
CYCLE = re.compile(r"\[cycle\] attempt (?P<idx>\d+): (?P<block>.*)$")
RELEASE = re.compile(
    r"\[offset\] release idx=(?P<idx>\d+) cat=(?P<cat>\S+)\s+dia_mm=\s*(?P<dia>[\d.]+) "
    r"planned=(?P<planned>[+-][\d.]+) spawn=(?P<spawn>[+-][\d.]+) "
    r"off_mm=\s*(?P<off>[+-][\d.]+) src=(?P<src>\S+)"
)
PROBE_ROW = re.compile(
    r"\[offset\] row pass=(?P<pass>\d+) idx=(?P<idx>\d+) cat=(?P<cat>\S+)\s+"
    r"dia_mm=\s*(?P<dia>[\d.]+) grade=(?P<grade>\S+) x_cmd=(?P<xc>[\d.]+) "
    r"x_settle=(?P<xs>[+-][\d.]+) off_mm=\s*(?P<off>[+-][\d.]+)"
)
LIVE_ROW = re.compile(
    r"\[offset\] live idx=(?P<idx>\d+) cat=(?P<cat>\S+)\s+dia_mm=\s*(?P<dia>[\d.]+) "
    r".*?x_cmd=(?P<xc>[+-][\d.]+) x_first=(?P<xf>[+-][\d.]+) x_edge=(?P<xe>[+-][\d.]+) "
    r"off_mm=\s*(?P<off>[+-][\d.]+)"
)
BANNER = re.compile(r"\[offset\] release compensation: table=(?P<table>\S+) "
                    r"instances=(?P<covered>\d+)/(?P<total>\d+)")


def read(name: str) -> list[str]:
    path = name if os.path.isabs(name) else os.path.join(HERE, name)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read().splitlines()


def physics(lines: list[str]) -> list[str]:
    """The `[fruit]` stream minus the optional print-only tags."""
    return [line for line in lines
            if line.startswith("[fruit]") and not line.startswith(PRINT_ONLY)]


def norm_reason(note: str) -> str:
    text = note.strip().strip("[]").strip()
    if not text:
        return "empty note"
    return re.sub(r"[-+0-9.]+", "#", text)


def parse_run(name: str) -> dict:
    lines = read(name)
    out = {"lines": lines, "stats": None, "attempts": [], "delivered": [],
           "catchup": [], "cycles": [], "releases": [], "banner": None, "picks": []}
    for line in lines:
        if match := STATS.search(line):
            out["stats"] = match.groupdict()
        if match := ATTEMPT.search(line):
            row = match.groupdict()
            row["idx"] = int(row["idx"])
            out["attempts"].append(row)
        if match := PICK.search(line):
            out["picks"].append(match.groupdict())
        if match := DELIVERED.search(line):
            out["delivered"].append({"y": float(match.group("y")),
                                     "x": float(match.group("x"))})
        if match := CATCHUP.search(line):
            out["catchup"].append(float(match.group("mm")))
        if match := CYCLE.search(line):
            out["cycles"].append(match.groupdict())
        if match := RELEASE.search(line):
            out["releases"].append(match.groupdict())
        if match := BANNER.search(line):
            out["banner"] = match.groupdict()
    return out


def parse_probe(name: str) -> dict:
    rows, live = [], []
    for line in read(name):
        if match := PROBE_ROW.search(line):
            row = match.groupdict()
            rows.append({
                "pass": int(row["pass"]), "idx": int(row["idx"]), "cat": row["cat"],
                "dia": float(row["dia"]), "x_cmd": float(row["xc"]),
                "x_settle": float(row["xs"]), "off_mm": float(row["off"]),
                # delivered = the *planned* x + the residual the probe measured
                "delivered": float(row["xc"]) + float(row["off"]) / 1000.0,
            })
        elif match := LIVE_ROW.search(line):
            row = match.groupdict()
            live.append({"idx": int(row["idx"]), "cat": row["cat"],
                         "dia": float(row["dia"]), "x_cmd": float(row["xc"]),
                         "x_edge": float(row["xe"]), "off_mm": float(row["off"])})
    return {"rows": rows, "live": live}


def tail(values: list[float]) -> str:
    if not values:
        return "n/a"
    low = sum(1 for v in values if v < BAND_LO)
    high = sum(1 for v in values if v > BAND_HI)
    below = sum(1 for v in values if v < 0.200)
    above = sum(1 for v in values if v > 0.360)
    ordered = sorted(values)
    return (f"n={len(values)} min={ordered[0]:.4f} p50={ordered[len(ordered) // 2]:.4f} "
            f"max={ordered[-1]:.4f}  <0.180: {low} ({100 * low / len(values):.1f} %)  "
            f"<0.200: {below} ({100 * below / len(values):.1f} %)  "
            f">0.360: {above} ({100 * above / len(values):.1f} %)  "
            f">0.390: {high} ({100 * high / len(values):.1f} %)")


def reasons(run: dict) -> set[str]:
    out = set()
    for row in run["attempts"]:
        if row["placed"] == "True":
            continue
        out.add(norm_reason(row["notes"]))
    return out


def cell_read(name: str, title: str, say) -> dict:
    probe = parse_probe(name)
    rows = probe["rows"]
    if not rows:
        say(f"  ({title}: absent)")
        return probe
    values = [row["delivered"] for row in rows]
    outside = [row for row in rows if not (BAND_LO <= row["delivered"] <= BAND_HI)]
    say(f"  {title}: cells={len(rows)} outside={len(outside)}  {tail(values)}")
    if outside:
        for row in outside:
            say(f"    outside: pass={row['pass']} idx={row['idx']:02d} {row['cat']:<10s} "
                f"x_cmd={row['x_cmd']:.2f} delivered={row['delivered']:.4f}")
    by_cell: dict[tuple[int, float], list[float]] = {}
    for row in rows:
        by_cell.setdefault((row["idx"], round(row["x_cmd"], 2)), []).append(row["off_mm"])
    spread = [max(v) - min(v) for v in by_cell.values() if len(v) > 1]
    if spread:
        say(f"    pass-to-pass spread over {len(spread)} cells: max={max(spread):.2f} mm")
    return probe


def main() -> int:
    out: list[str] = []

    def say(line: str = "") -> None:
        out.append(line)
        print(line)

    say("# P50 phase 2 - the per-pool release-offset compensation (offline read)")
    say()
    say("Generated by `logs/p50/p2/p2_report.py` from the logs in this directory. "
        "Every count is a count of a deterministic branch, not a rate.")
    say()

    # ------------------------------------------------------------------ #
    say("## 0. The tables")
    say()
    for name in ("accept_s5", "pear_s5"):
        path = os.path.join(ROOT, "configs", f"release_offsets_{name}.json")
        payload = json.load(open(path, encoding="utf-8"))
        rows = payload["rows"]
        say(f"`configs/release_offsets_{name}.json` - {len(payload['offsets'])} instances, "
            f"identity={payload['identity']}")
        say()
        say("| idx | signature | live n | live offsets mm | rule | measured mm | applied mm |")
        say("| --- | --- | --- | --- | --- | --- | --- |")
        for row in rows:
            say(f"| {row['idx']:02d} | {row['signature']} | {row['live_n']} | "
                f"{row['live_offsets_mm'] or '-'} | {row['rule']} | "
                f"{row['measured_mm']:+7.2f} | {row['applied_mm']:+7.2f} |")
        say()

    # ------------------------------------------------------------------ #
    say("## 1. M1 - the isolated probe, 96 cells (the powered endpoint)")
    say()
    say("`delivered = x_cmd + off_mm` where `off_mm` is the probe's measured "
        "offset; with the knob on it is the **compensated residual**, so this is "
        "the delivered x after compensation.")
    say()
    for name, title in (("../p1/offset_probe_s5.log", "M1-C (phase-1 log, knob unset)"),
                        ("m1o_probe.log", "M1-O (knob on, the acceptance table)")):
        cell_read(name, title, say)
        say()
    m1o = parse_probe("m1o_probe.log")
    if m1o["rows"]:
        say("M1-O per instance (delivered x at planned 0.20 / 0.28 / 0.36):")
        say()
        say("| idx | species | dia mm | applied mm | delivered @0.20 | @0.28 | @0.36 |")
        say("| --- | --- | --- | --- | --- | --- | --- |")
        table = json.load(open(os.path.join(ROOT, "configs", "release_offsets_accept_s5.json"),
                               encoding="utf-8"))["offsets"]
        by: dict[int, dict[float, float]] = {}
        for row in m1o["rows"]:
            by.setdefault(row["idx"], {})[round(row["x_cmd"], 2)] = row["delivered"]
        for idx in sorted(by):
            row0 = next(r for r in m1o["rows"] if r["idx"] == idx)
            key = f"{row0['cat']}|{row0['dia']:.1f}"
            say(f"| {idx:02d} | {row0['cat']} | {row0['dia']:.1f} | "
                f"{table.get(key, float('nan')):+7.2f} | "
                + " | ".join(f"{by[idx][x]:.4f}" for x in sorted(by[idx])) + " |")
        say()

    # ------------------------------------------------------------------ #
    say("## 2. M1b - the live probe: the draws must not move")
    say()
    m1bc = parse_probe("../p1/offset_live_s5.log")
    m1bo = parse_probe("m1bo_live.log")
    a = [round(rec["x_cmd"], 5) for rec in m1bc["live"]]
    b = [round(rec["x_cmd"], 5) for rec in m1bo["live"]]
    say(f"* releases reaching the edge: C {len(a)}, O {len(b)}")
    say(f"* the planned-x sequence: **{'IDENTICAL' if a == b else 'DIFFERS'}** "
        f"({sum(1 for x, y in zip(a, b) if x == y)}/{min(len(a), len(b))} equal)")
    for label, probe in (("M1-C", m1bc), ("M1-O", m1bo)):
        values = [rec["x_edge"] for rec in probe["live"]]
        residual = [rec["off_mm"] for rec in probe["live"]]
        if values:
            say(f"* {label}: delivered x {tail(values)}")
            say(f"  - residual (off_mm) {min(residual):+.2f} .. {max(residual):+.2f} mm, "
                f"|residual| p50 {sorted(abs(v) for v in residual)[len(residual) // 2]:.2f} mm, "
                f"max {max(abs(v) for v in residual):.2f} mm")
    say()

    # ------------------------------------------------------------------ #
    say("## 3. M2 - the shipped acceptance, SEED=5, C vs O")
    say()
    runs = {"C": parse_run("m2_c.log"), "O": parse_run("m2_o.log")}
    for label, run in runs.items():
        say(f"### M2-{label}")
        say()
        if run["banner"]:
            say(f"banner: `table={run['banner']['table']} "
                f"instances={run['banner']['covered']}/{run['banner']['total']}`")
            say()
        stats = run["stats"]
        if stats:
            say(f"* `[stats]`: attempts={stats['attempts']} successes={stats['ok']} "
                f"({stats['rate']} %) diverted={stats['div']} sim={stats['sim']} s, "
                f"**{stats['spa']} s/attempt**")
        say(f"* delivered x at the selection instant ({len(run['delivered'])} rows): "
            f"{tail([d['x'] for d in run['delivered']])}")
        over = [v for v in run["catchup"] if v > TOL_MM]
        say(f"* acquisition: `dynamic catch-up` rows={len(run['catchup'])}, "
            f"above {TOL_MM:g} mm = {len(over)}"
            + (f" {sorted(over)}" if over else "")
            + f"; no-grasp terminals = "
            f"{sum(1 for r in run['attempts'] if r['grasped'] == 'False')}")
        say(f"* placed {sum(1 for r in run['attempts'] if r['placed'] == 'True')}"
            f"/{len(run['attempts'])}; failure reasons "
            f"{sorted(reasons(run)) or 'none'}")
        src = {}
        for rec in run["releases"]:
            src[rec["src"]] = src.get(rec["src"], 0) + 1
        shifts = [float(rec["off"]) for rec in run["releases"]]
        say(f"* releases: n={len(run['releases'])} src={src}; applied shift "
            f"{min(shifts):+.2f}..{max(shifts):+.2f} mm" if shifts else
            "* releases: none recorded")
        if run["releases"]:
            say(f"  planned->spawn: max |spawn - (planned - shift)| = "
                f"{max(abs(float(r['spawn']) - (float(r['planned']) - float(r['off']) / 1000.0)) for r in run['releases']) * 1000:.3f} mm "
                f"(the print's 5-dp rounding)")
        if run["cycles"]:
            spans = [float(dict(p.split("=") for p in
                                [kv for kv in re.findall(r"[a-z]+=[\d.]+s", c["block"])])
                          .get("total", "0s")[:-1]) for c in run["cycles"]]
            say(f"* `[cycle]` totals: {len(spans)} rows, mean {sum(spans) / len(spans):.2f} s")
        say()
    say("Per attempt (category, grasped, placed, lift) - the class read:")
    say()
    say("| # | C | O |")
    say("| --- | --- | --- |")
    cats = {}
    for row in runs["C"]["picks"]:
        cats.setdefault(int(row["idx"]), {})["C"] = row["cat"]
    for row in runs["O"]["picks"]:
        cats.setdefault(int(row["idx"]), {})["O"] = row["cat"]
    crows = {int(r["idx"]): r for r in runs["C"]["attempts"]}
    orows = {int(r["idx"]): r for r in runs["O"]["attempts"]}
    for idx in sorted(set(crows) | set(orows)):
        def fmt(row, label):
            if row is None:
                return "-"
            return (f"{cats.get(idx, {}).get(label, '?')} "
                    f"{'P' if row['placed'] == 'True' else 'cnp'} "
                    f"lift={row['lift']} F={row['force']}")
        say(f"| {idx} | {fmt(crows.get(idx), 'C')} | {fmt(orows.get(idx), 'O')} |")
    say()
    say("(`P` = placed, `cnp` = grasped-not-placed: on the shipped dynamic line an "
        "unplaced attempt is overwhelmingly the carried-not-placed class, "
        "`logs/p42/SIM_LIMIT.md`.)")
    say()
    new_reasons = reasons(runs["O"]) - reasons(runs["C"])
    say(f"* **new failure reasons in O vs C**: {sorted(new_reasons) or 'none'}")
    say()

    # ------------------------------------------------------------------ #
    say("## 4. M3 - the pear pool (identity table, the inertness control)")
    say()
    pruns = {"C": parse_run("m3_c.log"), "O": parse_run("m3_o.log")}
    for label, run in pruns.items():
        stats = run["stats"]
        say(f"* M3-{label}"
            + (f": successes={stats['ok']}/{stats['attempts']} diverted={stats['div']} "
               f"{stats['spa']} s/attempt" if stats else ": absent"))
        say(f"  delivered x {tail([d['x'] for d in run['delivered']])}")
        over = [v for v in run["catchup"] if v > TOL_MM]
        say(f"  acquisition rows above {TOL_MM:g} mm: {len(over)}; no-grasp terminals: "
            f"{sum(1 for r in run['attempts'] if r['grasped'] == 'False')}; reasons "
            f"{sorted(reasons(run)) or 'none'}")
        shifts = [float(rec["off"]) for rec in run["releases"]]
        say(f"  releases: n={len(run['releases'])} applied shift "
            f"{min(shifts):+.2f}..{max(shifts):+.2f} mm" if shifts else "  releases: none")
    pc, po = physics(pruns["C"]["lines"]), physics(pruns["O"]["lines"])
    same = sum(1 for x, y in zip(pc, po) if x == y)
    say(f"* **inertness**: the pear physics `[fruit]` streams are "
        f"{'IDENTICAL' if pc == po else 'DIFFERENT'} "
        f"({len(pc)} vs {len(po)} lines, identical prefix {same})")
    say()

    # ------------------------------------------------------------------ #
    say("## 5. M4 - the no-harm arm (every P50 knob unset)")
    say()
    m4 = read("m4_unset.log")
    our = physics(m4)
    m4_stats = next((STATS.search(line).groupdict() for line in m4 if STATS.search(line)), None)
    if m4_stats:
        say(f"* M4 `[stats]`: successes={m4_stats['ok']}/{m4_stats['attempts']} "
            f"diverted={m4_stats['div']} sim={m4_stats['sim']} s, "
            f"**{m4_stats['spa']} s/attempt**")
    say(f"* physics `[fruit]` lines: {len(our)}")
    for ref, label in (("../../p41/p2/accept_profile.log", "TASK reference"),
                       ("../../p44/p2/accept_s5_C.log", "PREREG F5 reference")):
        other = physics(read(ref))
        same = sum(1 for x, y in zip(our, other) if x == y)
        say(f"* vs `{ref}` ({label}): {len(other)} lines, identical prefix {same} -> "
            f"**{'IDENTICAL' if our == other else 'DIFFERS'}**")
        if our != other:
            for index, (x, y) in enumerate(zip(our, other)):
                if x != y:
                    say(f"    first difference at line {index + 1}:")
                    say(f"      ref : {x}")
                    say(f"      ours: {y}")
                    break
    say()

    text = "\n".join(out) + "\n"
    with open(os.path.join(HERE, "p2_report.txt"), "w", encoding="utf-8") as handle:
        handle.write(text)
    print(f"\n[p2_report] wrote {os.path.join(HERE, 'p2_report.txt')} ({len(out)} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
