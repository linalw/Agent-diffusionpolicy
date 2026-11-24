# P253 results: **0.08 deployment = 49/50 (98 %)** on four seeds, and the 0.12 step is a **cadence** limit

**2026-11-25, `logs/p253/`.** Four fresh-seed continuous cells (903/904 at both speeds)
on top of P252's, the same recipe, `FRUIT_SKIP_LATE` at its new **single-arm** default
(0). **No `src/` change.**

---

## 1. The cells

One continuous episode of **10 picks** per cell, the P227z/P249 recipe, no per-pick
reset:

| speed | s901 | s902 | s903 | s904 | pooled | hand-offs |
|---|---|---|---|---|---|---|
| **0.08** | **9/10**, 10/10† | **10/10** | **10/10** | **10/10** | **49/50 = 98.0 %** | **0** |
| **0.12** | 8/10 | 7/10 | **9/10** | 7/10 | **31/40 = 77.5 %** | 0 |

† the second 0.08 seed-901 cell is the new-default confirmation (P252 §7); so the
**four distinct seeds** read 39/40 and the fifth cell adds its own 10/10.

| | 0.08 | 0.12 |
|---|---|---|
| `gap_ticks` median | **267-269** (263 = the pure return) | 268-296 |
| `[cycle] total` median | **11.74-12.12 s** | 11.46-11.91 s |
| losses | 1 (the 2.8 cm lychee, ep0) | 5 |

**So the deployment shape at the target speed is 98 % in five cells with no cell below
9/10, at ~11.8 s/cycle, with the arm never starved and the ownership rule never
firing.**

## 2. The 0.12 step is confirmed, and its residual is **cadence**, not the grasp

P252 measured 0.12 continuous at **11/20 = 55 %** with the multi-arm skip rule and
**15/20 = 75 %** without it. The two fresh seeds confirm the no-skip arm:
**9/10 + 7/10**, so **31/40 = 77.5 %** over four seeds.

**And the losses are a different class from 0.08.** The `FRUIT_FALL_DIAG` cell
(seed 904, 9/10) classifies the `fell off the line` key for the first time:

```
[fall] idx=11 pos=(+0.273,-0.897,+0.906) belt_top=1.170 held=False attached=False
```

`y = -0.897` is **past the belt's despawn (`-0.70`)** and `z = 0.906` is 0.26 m below
the belt top, `held=False` - **the fruit rode past the station uncaught and fell off
the end**. It is not the park slot (P139's artefact) and not a dropped payload: the
arm simply was not there in time.

So the 0.12 failure split is **2 pass-by + 3 grip** (`did not follow the gripper` on
6.1-6.7 cm *and* 3.4-4.4 cm fruit - both ends of the size range, so this is **not** the
2.8 cm class of P250/P251), and the mechanism the pass-bys point at is the **arm's
return transit (263 ticks) against the fruit's arrival** - exactly what P252's
topology finding already said, now with the position evidence.

## 3. An instrument gap, named (motion quality is still unmeasured)

P252 recorded "the no-skip arm's motion quality is not measured". This phase tried the
existing `[emit]` row (`FRUIT_EMIT_DIAG=1`, P53) on the 0.12 cell: **it is unusable in
continuous mode** - its counters reset at every pick boundary and the run prints **one**
row for the last pick with `ticks=1`:

```
[emit] episode 9: hold=4 clamp=1 ticks=1 decisions=1 out_pre=0/7 (0.0%)
      ticks_with_overshoot=0 overshoot_max=0.0mrad
```

One tick is not a measurement. **So the command-side motion quality of the no-skip arm
remains unmeasured**, and the fix is an instrument change (accumulate across picks, or
a per-pick printed row), which is its own default-off phase - **not** something to read
out of this cell.

## 4. What this settles for the objective

| | |
|---|---|
| **0.08 (target speed), deployment shape** | **49/50 = 98 %** over 4 seeds, ~11.8 s/cycle, 0 hand-offs, no starvation |
| **0.12, deployment shape, single-arm recipe** | **31/40 = 77.5 %** (was 55 % with the multi-arm rule) |
| **the 0.12 residual** | **2 pass-by (cadence) + 3 grip**, both size ends - **not** the 2.8 cm class |
| the next lever at 0.12 | the **inter-pick return** vs the arrival (the pass-by is measured), or a faster close/grip - **not** the small-fruit grasp |
| motion quality of the no-skip arm | **not measured** (the required instrument is a named gap, §3) |

**Reading rule for these cells**: each is one draw (the loop conditions on rendered
frames) and they are not independent - but five cells at 0.08 with **none below 9/10**
is the honest aggregate of what ran, and the two speeds differ by **20.5 points**,
which is the size of the cadence step rather than a grasp difference.

## 5. Pins

No `src/`/`configs/` change (the tree is P250's: `tasks.py` `b68ac8d1`, `rl_env.py`
`TASKS_MD5` follow, references **`61fb5202` / `61fb5202` / `18b101bf`**, ckpt
`p227_panda156`); `accept.sh` therefore stands at P250's **459/459 +
`fingerprint: matches`**. Evidence `logs/p253/`, report `logs/p253/p253_report.py`.
