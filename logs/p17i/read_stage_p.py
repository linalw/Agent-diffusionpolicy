#!/usr/bin/env python3
"""P17-B Stage-P read: the outcome battery for the slide gate (K3 doubles included).

Inputs: logs/p17i/50..55_*_slide*.log (the battery) and the mass-base controls
logs/p12a2/{10_seed11,11_seed5,12_seed23}_mass.log. Endpoints: the class census
per seed + pooled (the total failure mass = no-grasp + carried); the K3
bit-identity of each double's [fruit] stream (modulo the [trace] path lines);
the response counts (the mechanism). Read-only.

Usage: python3 logs/p17i/read_stage_p.py
"""
import os
import re
import subprocess
import sys

BATTERY = [
    (11, "logs/p17i/50_seed11_slide.log", "logs/p17i/51_seed11_slide_double.log"),
    (5, "logs/p17i/52_seed5_slide.log", "logs/p17i/53_seed5_slide_double.log"),
    (23, "logs/p17i/54_seed23_slide.log", "logs/p17i/55_seed23_slide_double.log"),
]
CONTROL = {
    11: "logs/p12a2/10_seed11_mass.log",
    5: "logs/p12a2/11_seed5_mass.log",
    23: "logs/p12a2/12_seed23_mass.log",
}
ATT = re.compile(
    r"\[run\] attempt (\d+) \((\w+)\): grasped=(\w+) placed=(\w+) lift=([+-][0-9.]+)"
)


def census(path):
    rows = {}
    for line in open(path, errors="replace"):
        m = ATT.search(line)
        if m:
            rows[(int(m.group(1)), m.group(2))] = (m.group(3) == "True", m.group(4) == "True")
    placed = sum(1 for g, p in rows.values() if p)
    carried = sum(1 for g, p in rows.values() if g and not p)
    nograsp = sum(1 for g, p in rows.values() if not g)
    return dict(n=len(rows), placed=placed, carried=carried, nograsp=nograsp,
                total_fail=carried + nograsp)


def fruit_stream(path):
    out = subprocess.run(
        ["grep", "-a", r"\[fruit\]", path], capture_output=True, text=True
    ).stdout.splitlines()
    return [ln for ln in out if "[trace]" not in ln]


def responses(path):
    return sum(
        1
        for ln in open(path, errors="replace")
        if "[slide]" in ln and "response=" in ln
    )


FALL = re.compile(r"lowest payload point (-[0-9]+) mm")


def falls(path):
    """The F6/A2 convention: falls = rows <= -1000 mm; partials = -1000 < v <= -100."""
    f = p = 0
    for line in open(path, errors="replace"):
        m = FALL.search(line)
        if m:
            v = int(m.group(1))
            if v <= -1000:
                f += 1
            elif v <= -100:
                p += 1
    return f, p


def main():
    print("| seed | arm | ok | no-grasp | carried | total fail | falls | partials | responses |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    tot = {"ctrl": [0, 0, 0], "gate": [0, 0, 0]}
    natt = 0
    for seed, prim, doub in BATTERY:
        if not os.path.exists(prim) or not os.path.exists(CONTROL[seed]):
            print(f"| {seed} | (pending) | | | | | | | |")
            continue
        c = census(CONTROL[seed])
        g = census(prim)
        cf, cp = falls(CONTROL[seed])
        gf, gp = falls(prim)
        tot["ctrl"][0] += c["placed"]; tot["ctrl"][1] += c["nograsp"]; tot["ctrl"][2] += c["carried"]
        tot["gate"][0] += g["placed"]; tot["gate"][1] += g["nograsp"]; tot["gate"][2] += g["carried"]
        natt += c["n"]
        print(f"| {seed} | control | {c['placed']} | {c['nograsp']} | {c['carried']} | {c['total_fail']} | {cf} | {cp} | - |")
        print(f"| {seed} | slide gate | {g['placed']} | {g['nograsp']} | {g['carried']} | {g['total_fail']} | {gf} | {gp} | {responses(prim)} |")
    print(f"| pooled | control | {tot['ctrl'][0]}/{natt} | {tot['ctrl'][1]} | {tot['ctrl'][2]} | "
          f"{tot['ctrl'][1]+tot['ctrl'][2]} | - | - | - |")
    print(f"| pooled | slide gate | {tot['gate'][0]}/{natt} | {tot['gate'][1]} | {tot['gate'][2]} | "
          f"{tot['gate'][1]+tot['gate'][2]} | - | - | - |")
    print()
    print("K3 (each double's [fruit] stream vs its primary, [trace] lines excluded):")
    for seed, prim, doub in BATTERY:
        if not os.path.exists(doub):
            print(f"  seed {seed}: double missing ({doub})")
            continue
        a, b = fruit_stream(prim), fruit_stream(doub)
        same = a == b
        print(f"  seed {seed}: {'IDENTICAL' if same else 'DIFFER'} "
              f"({len(a)} vs {len(b)} [fruit] lines)")
        if not same:
            for i, (x, y) in enumerate(zip(a, b)):
                if x != y:
                    print(f"    first diff line {i+1}:")
                    print(f"      prim: {x[:130]}")
                    print(f"      doub: {y[:130]}")
                    break
    print()
    print("The fired attempts (the arrest/survival read; Gap C):")
    for seed, prim, doub in BATTERY:
        if not os.path.exists(prim):
            continue
        fired = set()
        for line in open(prim, errors="replace"):
            m = re.search(r"\[slide\] (\w+) idx=(\d+) (\w+) response=\d+/\d+ trig@(\d+) rate=([0-9.]+)mm/s .*post=([0-9.]+)mm/s", line)
            if m:
                fired.add((m.group(1), m.group(2)))
        if not fired:
            print(f"  seed {seed}: no responses")
            continue
        print(f"  seed {seed}: {len(fired)} fired attempts ->")
        for line in open(prim, errors="replace"):
            m = re.search(r"\[slide\] (\w+) idx=(\d+) (\w+) summary ticks=(\d+) events=(\d+) rate_max=([0-9.]+)mm/s drift_max=([0-9.]+)mm", line)
            if m and (m.group(1), m.group(2)) in fired:
                print(f"    {m.group(1)} idx={m.group(2)} {m.group(3)}: "
                      f"rate_max={m.group(6)} drift_max={m.group(7)}mm events={m.group(5)}")


if __name__ == "__main__":
    main()
