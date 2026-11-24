# P257 results: the cell is **arm-bound** - 0.12 buys no throughput and costs 13.6 points

**2026-11-25, `logs/p257/`.** The release-candidate check: two **20-pick** continuous
cells on a fresh seed (905), then the pooled table over every continuous cell this
engagement has run. **No `src/` change.**

---

## 1. The cells

| speed | placed | `gap_ticks` | `[cycle] total` |
|---|---|---|---|
| 0.08 | **20/20** | 270 | 11.91 s |
| 0.12 | **20/20** | 270 | 11.94 s |

Both clean, and **the two speeds have the same cadence** (270 ticks, 11.9 s) - which is
the point of §2.

## 2. Pooled over every continuous cell (the recipe as shipped)

| speed | cells | seeds | placed | cycle (median) | gap | **s/pick** | **picks/min** |
|---|---|---|---|---|---|---|---|
| **0.08** | 6 | 901-905 | **69/70 = 98.6 %** | 11.84 s | 2.25 s | **14.08** | **4.26** |
| **0.12** | 5 | 901-905 | **51/60 = 85.0 %** | 11.89 s | 2.74 s | **14.63** | **4.10** |

(`s/pick` = cycle + gap/120, arithmetic from the two measured numbers, not a separate
measurement. Cells are one draw each; the pooled count is what ran, not a rate
certificate.)

## 3. The finding: **the belt speed buys nothing on this cell**

**Raising the belt 0.08 -> 0.12 costs 13.6 points of success and 3.8 % of throughput.**
The mechanism is structural, not a tuning miss:

* the attempt is **11.8-11.9 s at both speeds** - it is the arm's own work (`place`
  3.48, `release` 2.2, `grip` 1.58, `ramp` 1.10, `lift` 1.2) and the fruit's arrival
  wait, which the belt only shortens when the arm is *already* waiting;
* the return is **2.25-2.74 s at both speeds** - it is the arm's transit, not the line;
* so the **line speed is not in the throughput equation** for this cell, while it *is*
  in the loss equation (P253: the 0.12 losses are pass-bys and grip, the 0.08 losses are
  one instance in 70 picks).

**That redirects the improvement path**: on this cell the throughput lever is the
**arm's cycle**, not the conveyor. A faster line helps only a cell whose attempt is
arrival-bound - which this one is not (P91 measured the same on the two-line: the
`descent` block is `lead/speed - margin` and a faster leg just waits longer).

## 4. What this sets as the delivered spec

| | |
|---|---|
| **0.08 m/s, continuous, mixed pool** | **69/70 = 98.6 %**, **4.26 picks/min**, ~14.1 s/pick |
| **0.08 m/s, hardest single species (lychee)** | **20/20 = 100 %** (P255) |
| 0.12 m/s, continuous | 51/60 = 85.0 %, 4.10 picks/min |
| the speed axis | **closed as a throughput lever**; it is a loss lever only |
| the remaining throughput lever | the arm's **11.8 s cycle** (`place` 3.48 + `release` 2.2 + `grip` 1.58 + `ramp` 1.10 + `lift` 1.2 + return), each block already measured - three profile cells negative (P88/P89/P235/P254) |

## 5. Pins

No `src/`/`configs/` change (the tree is P256's: `rl_env.py` with the default-off
instance/blend instruments, `tasks.py` `b68ac8d1`, references **`61fb5202` /
`61fb5202` / `18b101bf`**, ckpt `p227_panda156`); `accept.sh` stands at P256's
**459/459 + `fingerprint: matches`**. Evidence `logs/p257/`.
