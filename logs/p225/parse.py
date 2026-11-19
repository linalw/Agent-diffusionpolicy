import re, sys, glob, statistics as st

def parse(path):
    rows=[]
    for l in open(path, errors='ignore'):
        m=re.search(r'\[rl\] episode (\d+): (\w+) d=([\d.]+)cm bin=(\d+) arm=(\w+) success=(\w+) grasped=(\w+) placed=(\w+) ticks=(\d+) decision=(\d+)', l)
        if m:
            rows.append(dict(ep=int(m.group(1)), fruit=m.group(2), d=float(m.group(3)),
                             arm=m.group(5), success=m.group(6)=='True',
                             grasped=m.group(7)=='True', placed=m.group(8)=='True',
                             ticks=int(m.group(9)), dec=int(m.group(10)),
                             notes=(re.search(r'notes=(\[[^]]*\])', l).group(1) if 'notes=' in l else '')))
    return rows

for path in sys.argv[1:]:
    r=parse(path)
    if not r: print(path, 'no rows'); continue
    ok=sum(x['success'] for x in r)
    print(f"{path}: {ok}/{len(r)} success, ticks p50={st.median(x['ticks'] for x in r):.0f} "
          f"mean={st.mean(x['ticks'] for x in r):.0f} min={min(x['ticks'] for x in r)} max={max(x['ticks'] for x in r)}")
    for x in r:
        print(f"  ep{x['ep']:2d} {x['fruit']:9s} {x['arm']:5s} s={int(x['success'])} g={int(x['grasped'])} p={int(x['placed'])} "
              f"t={x['ticks']:4d} ({x['ticks']/120:.1f}s) {x['notes'][:70]}")
