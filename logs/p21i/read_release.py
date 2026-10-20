#!/usr/bin/env python3
"""P21-B read: the release tail-trim battery (logs/p21/RELEASE_DESIGN.md §4).

Per log: the [cycle] release phase p50 (P1; bar <= 1.45 s pooled / <= 1.55 per seed), the
[cycle] total span p50 (P2; <= 14.50 / <= 15.10), the placed census (K2: pooled >= 45/60), the
falls (the F6 convention), and the arm's place-trace presence. Read-only.

Usage: python3 logs/p21i/read_release.py
"""
import re
import statistics as st

CONTROLS = {11: "logs/p12a2/10_seed11_mass.log", 5: "logs/p12a2/11_seed5_mass.log",
            23: "logs/p12a2/12_seed23_mass.log"}
ARMS = {
    "A": ["logs/p21i/10_seed11_relA_1.log", "logs/p21i/12_seed11_relA_2.log",
          "logs/p21i/10_seed5_relA_1.log", "logs/p21i/12_seed5_relA_2.log",
          "logs/p21i/10_seed23_relA_1.log", "logs/p21i/12_seed23_relA_2.log"],
    "B": ["logs/p21i/11_seed11_relB_1.log", "logs/p21i/13_seed11_relB_2.log",
          "logs/p21i/11_seed5_relB_1.log", "logs/p21i/13_seed5_relB_2.log",
          "logs/p21i/11_seed23_relB_1.log", "logs/p21i/13_seed23_relB_2.log"],
}
CYCLE = re.compile(r"\[cycle\] attempt \d+: (.+)")
REL = re.compile(r"release=([0-9.]+)s")
TOT = re.compile(r"total=([0-9.]+)")
ATT = re.compile(r"\[run\] attempt (\d+) \((\w+)\): grasped=(\w+) placed=(\w+)")
FALL = re.compile(r"lowest payload point (-[0-9]+) mm")


def read(paths):
    rel, tot, placed, carried, nograsp, fall, n = [], [], 0, 0, 0, 0, 0
    rows = {}
    for p in paths:
        try:
            txt = open(p, errors="replace").read()
        except FileNotFoundError:
            continue
        for m in CYCLE.finditer(txt):
            r = REL.search(m.group(1))
            if r:
                rel.append(float(r.group(1)))
            t = TOT.search(m.group(1))
            if t:
                tot.append(float(t.group(1)))
        for m in ATT.finditer(txt):
            rows[(p, int(m.group(1)), m.group(2))] = (m.group(3) == "True", m.group(4) == "True")
        for m in FALL.finditer(txt):
            if int(m.group(1)) <= -1000:
                fall += 1
    placed = sum(1 for g, pl in rows.values() if pl)
    carried = sum(1 for g, pl in rows.values() if g and not pl)
    nograsp = sum(1 for g, pl in rows.values() if not g)
    return dict(n=len(rows), rel=rel, tot=tot, placed=placed, carried=carried,
                nograsp=nograsp, fall=fall)


def main():
    print("| arm | attempts | release p50 s | total p50 s | placed | nc | carried | falls |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for arm, paths in ARMS.items():
        d = read(paths)
        print(f"| {arm} | {d['n']} | {st.median(d['rel']) if d['rel'] else float('nan'):.2f} | "
              f"{st.median(d['tot']) if d['tot'] else float('nan'):.2f} | {d['placed']} | "
              f"{d['nograsp']} | {d['carried']} | {d['fall']} |")
    c = read(list(CONTROLS.values()))
    print(f"| control (on disk) | {c['n']} | - | - | {c['placed']} | {c['nograsp']} | "
          f"{c['carried']} | {c['fall']} |")
    print()
    print("bars: P1 release p50 <= 1.45 pooled / <= 1.55 per seed; P2 total p50 <= 14.50 / 15.10;")
    print("      K2 pooled placed >= 45/60 and the release-block failures <= 2/46.")


if __name__ == "__main__":
    main()
