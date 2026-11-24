# P231 results: "the lift travels with the belt" fails - the lift is longer than the hand's travel

**2026-11-24, `logs/p231/`.** A/B at 0.24 m/s + a no-harm cell at 0.12. **The lever
is default off and is not adopted.** Pre-registration: `logs/p231/PREREG.md`.

---

## 1. The cells

| cell | `v` | `ext` | `LIFT_TRACK_BELT` | placed | `grasp_lift` legs (`ticks` / `clean_slip_max`) |
|---|---|---|---|---|---|
| A (control) | 0.24 | 0.10 | off | **1/3** | 191 / **0.0 mm** - 482 / **1141.3** - 307 / **1275.3** |
| B (treatment) | 0.24 | 0.10 | **on** | **1/3** | 191 / **0.0 mm** - 278 / **2038.5** - 176 / **1724.3** |
| C (no-harm, shipped speed) | 0.12 | 0 | **on** | **2/2** | 100 / **0.1 mm** - 90 / **0.0 mm** |

All three carry `FRUIT_CARRY_DIAG=1` so both arms read the same instrument.

## 2. The verdict: P1 and P2 fail, P3 passes

* **P1 (the endpoint) FALSIFIED.** `clean_slip_max` on the lift does **not** fall;
  on the two failing legs it **rises** (1141 -> 2039, 1275 -> 1724 mm).
* **P2 (the count) not met**: **1/3 in both arms**.
* **P3 (inertness at 0.12) PASSES**: 2/2 placed, `clean_slip` 0.0-0.1 mm. The
  lever does not damage the shipped speed.
* **The successful leg is byte-identical** (191 ticks, 0.0 mm in A and B): when
  the grip works the offset changes nothing measurable, so the lever only
  touched the failures - and made them worse.

## 3. Why: the belt travels far more than the hand can follow

The `[lift-track]` rows name the arithmetic:

```
[lift-track] v=-0.240 m/s over 191 ticks -> dy=-120.0 mm (capped)
[lift-track] v=-0.240 m/s over 278 ticks -> dy=-120.0 mm (capped)
```

| `v` | lift `ticks` | time | belt travel during the lift | capped at 120 mm -> drag left |
|---|---|---|---|---|
| 0.12 | 100 | 0.83 s | **100 mm** | 0 |
| 0.12 | 90 | 0.75 s | 90 mm | 0 |
| 0.24 | 191 | 1.59 s | **382 mm** | **262 mm** |
| 0.24 | 278 | 2.32 s | **556 mm** | **436 mm** |
| 0.24 | 482 | 4.02 s | **964 mm** | **844 mm** |

**The lift is 1.6-4.0 s long at 0.24, so matching the belt would need 382-964 mm of
y travel from the pick pose** - the cell's usable y band is a few hundred
millimetres (the station reach maps put the top-down catch inside roughly
`y = -0.10 .. +0.15 m`, `logs/r10/reach_intercept_*.json`, `logs/p123/probe.txt` for
the inboard lane). The 0.12 lift needs only 90-100 mm, which is why the same lever
is clean there.

So the lever is **physically infeasible at 0.24 with this lift duration**, and the
120 mm bound does not "fix" it - it turns a 382-964 mm drag into a 262-844 mm
drag while the arm is being commanded somewhere it cannot go. **The partial
tracking is worse than none**, which is what the larger `clean_slip` says.

## 4. What this closes and what it leaves

**Closed**: "make the relative velocity zero by moving with the belt" as a
software lever on this cell. It would need a **lift short enough that
`v x t_lift` fits the hand's travel** (at 0.12, 0.1 m does; at 0.24 it needs
0.38 m), and the record has already measured the lift's speed cap as negative
(P89: `FRUIT_SPEED_LIFT` raised the interval at both seeds) - so the two levers
fight each other.

**Left standing, and now the only ones on this axis**:
1. **a shorter grip-establishment** (a faster lift) - measured negative at P89,
   and P231 shows why a faster lift is also what would make belt-tracking fit;
2. **a hand or axis that travels with the belt** (hardware: a linear track, a
   longer y reach, or a pick station downstream of a diverter) - P229 already
   priced the station/runway family and P119 closed the belt-speed change;
3. **accept ~0.18 m/s** for this arm and cell, which is where the objective's
   "保证成功率" band already sits (0.06-0.18: 11 / 10 / 11 / 11 of 12).

## 5. What this means for the objective

The objective's ordering is **success first, speed second**. The measured state
is: **0.08-0.18 m/s is a reliable band (91-92 %)**, 0.20 is marginal (58 %), and
0.22+ fails because the payload cannot be held while the belt drags it faster than
the hand can follow. **The remaining lever for "分拣速度" is therefore the cycle
time at the reliable speeds, not the belt speed** - the place block is ~4.0 s of a
~14.5 s attempt, and the release ~1.0 s after P227r's trim.

## 6. Pins

`tasks.py` **`c16c8291`** (the knob, the offset, the bound), `rl_env.py`
`TASKS_MD5` follow, `scripts/selfcheck.sh` (leg `P231 lift track`); references
**`61fb5202` / `61fb5202` / `18b101bf`** untouched; checkpoint `p227_panda156`
used as-is. Evidence `logs/p231/{PREREG.md, A_ctrl/, B_treat/, C_012/}`.
