# P239 results: the catch-up exits on its budget, not on convergence - the tolerance sits below the following error

**2026-11-24, `logs/p239/`.** Measurement only (existing diags:
`FRUIT_CYCLE_REPORT=1` + `FRUIT_TRACK_DIAG=1`). No `src/` change.

---

## 1. The pairing

6 attempts at 0.08 m/s, both seeds. The appended diagnostic row is
`[catch] idx= arm= ticks= residual= lead=250ms`, printed by the pursuit loop
(`tasks.py:15569`), and `seat` is that loop's cost in the block report (P237/P238).

| catch `ticks` | residual at exit | `seat` |
|---|---|---|
| **27** | **5.7 mm** | **0.22 s** |
| 98 | 5.8 mm | 0.81 s |
| **200** | **6.6 mm** | **1.67 s** |
| **200** | **6.7 mm** | **1.67 s** |
| **200** | 6.6 mm | 1.67 s |
| **200** | 6.7 mm | 1.67 s |

`seat` is the pursuit's tick count to the hundredth (`200 x 8.33 ms = 1.667 s`),
so P238's identification is **confirmed**: the block is the catch-up.

## 2. The finding: the loop never meets its own exit condition

`FRUIT_DYNAMIC_CATCH_TOL` is **6 mm**. Five of six attempts end at **6.6-6.7 mm** -
i.e. **the pursuit converges to a steady-state error just above the tolerance and
runs the full 200-tick budget**, stopping 0.6-0.7 mm from where it would have
exited. The two fast attempts (27 and 98 ticks) are the ones whose error happened
to cross 5.7-5.8 mm.

**That is a following error against a moving target, not an unreachable goal**:
6.6 mm at 0.08 m/s is **82 ms of lag**, and the tolerance (6 mm) is *below* it. So
at this speed the loop's exit condition is essentially **unsatisfiable**, and it
exits on `FRUIT_DYNAMIC_CATCH_TICKS` (200) instead.

Two consequences, and the second is the important one:

1. **The 1.44 s is a fixed tax paid for a 0.6 mm miss.** The attempt doesn't fail -
   it spends the budget and then closes anyway.
2. **`6 mm` is not a convergence criterion here, it is a threshold the controller
   cannot meet at 0.08** - which also means P48's "8/8 no-grasp above 6 mm" was
   measuring a *class boundary* while the loop was mostly running at 6.6-6.7 mm
   anyway. The tolerance and the achievable error are the same number, and that is
   why the block's cost is bimodal rather than graded.

## 3. The levers this names (not built)

* **(a) Reduce the following error** - a lead/feed-forward on the pursuit (it
  already closes on `fruit + v x 0.25 s`; P233 showed the *trigger's* speed source
  was a 2x error under a wave, and the same class of error would show up here).
  This is the principled one: it makes the exit condition satisfiable and the
  1.44 s disappears without loosening anything.
* **(b) Raise the tolerance above the achievable error** - `6 -> 8 mm` would exit
  in ~30 ticks, **-1.4 s**, but P48 measured 6 mm as the class boundary, so this
  is a *catch-quality* trade and would need its own cell and a powered count.
* **(c) The budget** - lowering `FRUIT_DYNAMIC_CATCH_TICKS` just truncates a
  pursuit that is 0.6 mm from its goal; it trades time for the same miss.

**(a) is the one that costs nothing in quality**, and it is measurable with the row
this phase used: the endpoint is `residual` (should fall) and `seat` (should fall
to ~30 ticks), with the placed count as the guard.

## 4. What this does to the cycle picture

The 0.08 cycle is **~13.5 s**, and the `seat` block is the only bimodal one. It is
now fully explained: **the pursuit runs to its 200-tick budget whenever its
following error stays above 6 mm**, which is most attempts at this speed. The
**1.44 s is therefore not "the approach's fault" in the sense of a miss** - the
catch is fine - it is **a tolerance that is slightly tighter than the controller's
steady-state lag**.

## 5. Pins

No `src/` change; `tasks.py` **`e72b2c7c`**, `rl_env.py` unchanged by this phase;
references **`61fb5202` / `61fb5202` / `18b101bf`** untouched; checkpoint
`p227_panda156`. Evidence `logs/p239/catch/`.
