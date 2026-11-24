# P237 results: the close block is `seat + ramp`, and `seat` is a cross-layer attitude cost the primitive pays for the policy

**2026-11-24, `logs/p237/`.** Two sub-marks inside the `close` block (no-op unless
`FRUIT_CYCLE_REPORT=1`). P236's 2.77 s is now decomposed. **No behaviour change.**

---

## 1. The decomposition (8 attempts, both seeds, 0.08)

| attempt | descent | **seat** | **ramp** | grip | lift | place | release | total |
|---|---|---|---|---|---|---|---|---|
| s901 e0 | 4.85 | **0.67** | 1.10 | 1.58 | 1.25 | 3.48 | 2.27 | 15.70 |
| s901 e1 | 2.65 | **1.67** | 1.10 | 1.58 | 1.24 | 3.48 | 2.25 | 14.47 |
| s901 e2 | 1.69 | **1.67** | 1.10 | 1.58 | 1.25 | 3.47 | 2.27 | 13.53 |
| s902 e0 | 2.12 | **0.23** | 1.10 | 1.58 | 1.27 | 3.47 | 2.27 | 12.54 |
| s902 e1 | 1.46 | **1.67** | 1.10 | 1.59 | 1.19 | 3.48 | 2.16 | 13.14 |
| s902 e2 | 4.56 | **1.67** | 1.10 | 4.45 | 4.43 | - | - | 16.21 (failed) |
| smoke a | 2.28 | 1.67 | 1.10 | 1.58 | 1.24 | 3.47 | 2.25 | 14.08 |
| smoke b (failed) | 4.77 | 1.67 | 1.28* | 4.53 | 2.44 | - | - | 15.80 |

\* the failed attempt retried: `seat=1.67 attempt=0.00 attempt=1.28 close=1.10`, i.e.
**two ramps**, which is why P236 saw 2.77 = 1.67 + 1.10 and this one reads 1.67 +
1.28 + 1.10.

## 2. Two hard findings

**(a) `ramp` is a constant 1.10 s.** Six of six placed attempts, four different
fruits, both seeds: **1.10 s exactly**. That is the close ramp (`close_ramp` ticks
x `CONTROL_DT`), i.e. the profile, not the fruit.

**(b) `seat` is bimodal - 1.67 s on 4 of 6, 0.23/0.67 on the other 2.** `1.67 s =
200 ticks`, and the code's only loop that can run that long is the **attitude
servo** (`FRUIT_AXIS_SERVO`, default **180** iterations, one `ik_step` +
`_step_sim(1)` each) followed by the coherent track. So the reading is: **when the
approach leaves the wrist already near vertical the servo exits in ~28 ticks
(0.23 s); otherwise it runs to its cap (1.67 s)**.

**That is a cross-layer cost**: the policy's approach owns the arm's attitude, the
primitive owns the pads' squareness, and neither layer is charged for the 1.44 s
the primitive spends re-establishing the attitude the approach did not arrive
with. It is 4T's interface cost made visible - the same shape as P231's "partial
tracking is worse than none", one layer down.

## 3. What the cycle is made of now

At 0.08, a placed attempt is **~13.5 s**:

| | s | movable? |
|---|---|---|
| `place` (transit) | 3.48 | constant; P227r's cell moved it at 0.12, negative |
| `release` (incl. the 0.5 s settle + retreat) | 2.16-2.27 | the dwell is already trimmed (P227r) |
| `grip` (probe/validation) | 1.58 | P91: the mode mix, not the profile |
| `seat` (attitude + track) | **0.23 or 1.67** | **yes - and it is the approach's fault** |
| `descent` (includes the arrival wait) | 1.5-4.9 | no (P91: `lead/speed - margin`) |
| `lift` | 1.19-1.27 | measured negative to speed up (P89) |
| `ramp` (close profile) | 1.10 | it is the close's validation margin (P91: 60 -> 24 ticks cost first-probe success 14/20 -> 5/20) |
| `return` | 0.50 | - |

**The fixed part is ~10 s of ~13.5 (75 %)**, and the only block with a *bimodal*
distribution - i.e. the only one where the same cell is already 1.44 s faster on
some attempts - is `seat`.

## 4. The lever this names (not built)

**Make the approach arrive with the tool axis vertical.** If the policy's last
chunk left the wrist within `FRUIT_AXIS_TOL` of the top-down attitude, the servo
would exit in ~0.23 s on every attempt: **-1.44 s per attempt, ~11 % of the
cycle**, and it is a *success-neutral* saving (it removes work, not margin) if the
attitude is right.

Two ways, both measurable with this instrument: (i) a **training/conditioning**
change on the approach's last chunk (the demos carry the attitude; the policy's
emission is what drifts), or (ii) an **explicit wrist command** on the handover
(the primitive already holds `hold_quaternion`; commanding it earlier is a code
change with its own cell). **The cap alone (`FRUIT_AXIS_SERVO` 180 -> 60) is not
the lever**: it would truncate the servo while the attitude is still wrong, and
P64/P65 measured the attitude as load-bearing.

## 5. Pins

`tasks.py` **`74300602`** (the two marks), `rl_env.py` `TASKS_MD5` follow,
`scripts/selfcheck.sh` (leg `P236 direct cycle report` still passes - the marks are
inside its ownership path); references **`61fb5202` / `61fb5202` / `18b101bf`**
untouched; checkpoint `p227_panda156`. Evidence `logs/p237/{smoke/, seat/}`.

---

## 6. CORRECTION (P238, same day): the 1.67 s is the **catch-up**, not the attitude servo

§2(b) attributed the bimodal `seat` to the attitude servo's 180-iteration cap.
**That is falsified by measurement.** A `[seat] init` row (one TCP-pose read before
the servo, gated on `FRUIT_CYCLE_REPORT=1`) reads the wrist's error at the servo's
entry on six attempts:

```
init 1-cos = 0.0001 / 0.0000 / 0.0000 / 0.0000 / 0.0000 / 0.0000   -> 0.6 / 0.1 / 0.1 / 0.0 / 0.1 / 0.1 deg
```

against `FRUIT_AXIS_TOL = 0.01` (**8.1 deg**). **The servo exits on its first
check on every attempt** and costs ~1 tick.

`1.67 s = 200 ticks`, and the loop in that segment that has a 200-tick budget is
`FRUIT_DYNAMIC_CATCH_TICKS` (default **200**, `tasks.py:15395`, the loop at
`:15427`) - the primitive's **pursuit** of the fruit. So `seat` is bimodal for a
different reason: **the catch-up converges in ~26 ticks (0.22 s) when the fruit is
where the aim expected it, and runs its full 200-tick budget (1.67 s) when it is
not.**

The *shape* of §2(b)'s conclusion survives - the primitive pays **1.44 s** for a
gap the approach left - but the **object is the aim residual, not the attitude**,
and the lever is therefore "arrive closer", not "arrive more vertical". See
`logs/p238/`.
