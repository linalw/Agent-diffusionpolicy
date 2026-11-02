"""P99 step 0: can the slot timeline be read off the shipped records?

The two-line worker prints, per slot:
  [biarm] <arm>: station acquired at t=..s     (slot start -> selection)
  [biarm] <arm>: no eligible fruit; ...        (a starved poll)
  [biarm] result <arm> index=.. ... sim=Xs     (the attempt's span)
  [cycle] attempt N: ... total=Ys               (the same span, per block)
and nothing carries an absolute attempt-END time unless
`FRUIT_BIARM_PARK_TRACE=1` is on (`park wait start t=`). This probe asks
whether `acq_(N+1) - acq_N - total_N` is a stable remainder, i.e. whether the
gap between two slot starts is (attempt span + park + feed [+ starved polls]).
If it is, the offline records already carry the wait split down to that
remainder and only the park/selection/starvation split needs one instrumented
cell.
"""
import re
import sys

ACQ = re.compile(r"\[biarm\] (\w+): station acquired at t=([0-9.]+)s")
STARVE = re.compile(r"\[biarm\] (\w+): no eligible fruit")
TARGET = re.compile(r"\[task\] target (\w+) \(grade (\w), ([0-9.]+) cm\) with (\w+) arm")
CYCLE = re.compile(r"\[cycle\] attempt (\d+): (.+?) total=([0-9.]+)s")
RESULT = re.compile(
    r"\[biarm\] result (\w+) index=(\d+) (\w+) grasped=(\w+) placed=(\w+) "
    r"lift=([+-][0-9.]+) force=([0-9.]+) sim=([0-9.]+)s"
)


def parse(path):
    slots = {"left": [], "right": []}
    pending = {"left": None, "right": None}
    cycles = []
    results = []
    for line in open(path, errors="replace"):
        if not line.startswith("[fruit]"):
            continue
        m = ACQ.search(line)
        if m:
            arm, t = m.group(1), float(m.group(2))
            pending[arm] = {"t_acq": t, "starved": False, "target": None, "span": None}
            slots[arm].append(pending[arm])
            continue
        m = STARVE.search(line)
        if m:
            arm = m.group(1)
            if pending[arm] is not None:
                pending[arm]["starved"] = True
            continue
        m = TARGET.search(line)
        if m:
            arm = m.group(4)
            if pending[arm] is not None:
                pending[arm]["target"] = (m.group(1), m.group(2), float(m.group(3)))
            continue
        m = CYCLE.search(line)
        if m:
            cycles.append((int(m.group(1)), m.group(2), float(m.group(3))))
            continue
        m = RESULT.search(line)
        if m:
            results.append(
                dict(
                    arm=m.group(1), index=int(m.group(2)), category=m.group(3),
                    grasped=m.group(4) == "True", placed=m.group(5) == "True",
                    lift=float(m.group(6)), force=float(m.group(7)),
                    span=float(m.group(8)),
                )
            )
    # attach each result's span to the attempt slot of the same arm, in order
    for arm in ("left", "right"):
        rs = [r for r in results if r["arm"] == arm]
        at = [s for s in slots[arm] if not s["starved"]]
        if len(rs) != len(at):
            print(f"  ! {arm}: {len(rs)} results vs {len(at)} attempt slots")
        for slot, res in zip(at, rs):
            slot["span"] = res["span"]
            slot["res"] = res
    return slots, cycles, results


def main(path):
    slots, cycles, results = parse(path)
    print(f"== {path}")
    print(f"   attempts={len(cycles)} results={len(results)} "
          f"placed={sum(r['placed'] for r in results)}")
    for arm in ("left", "right"):
        s = slots[arm]
        att = [x for x in s if not x["starved"]]
        print(f"   {arm}: slots={len(s)} attempts={len(att)} "
              f"starved={len(s) - len(att)}")
        gaps = []
        for a, b in zip(att, att[1:]):
            if a["span"] is None:
                continue
            gaps.append(b["t_acq"] - a["t_acq"] - a["span"])
        if gaps:
            gaps.sort()
            n = len(gaps)
            print(f"     acq->acq minus span: n={n} min={gaps[0]:.2f} "
                  f"p50={gaps[n // 2]:.2f} max={gaps[-1]:.2f} "
                  f"mean={sum(gaps) / n:.2f}")
    return 0


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)
