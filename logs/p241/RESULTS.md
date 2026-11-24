# P241 results: the 1.44 s tax is a 6.6 mm vertical droop - feed-forwarding it collapses the catch-up to 22 ticks

**2026-11-24/25, `logs/p241/`.** One default-off knob (`FRUIT_CATCH_Z_FF`, mm) plus
the residual-components field that found it. **Not adopted: one runaway in six.**

---

## 1. The measurement that located it

The `[catch]` row now prints the residual's **components**. At 0.08 m/s, shipped:

```
ticks=200 residual=6.6mm (x=-0.1 y=+0.5 z=-6.6)
ticks=200 residual=6.7mm (x=-0.2 y=+0.3 z=-6.7)
ticks= 26 residual=5.8mm (x=+0.6 y=-3.8 z=-4.4)
```

**`y` is already tracked (0.3-0.5 mm). The floor is `z` = -6.6 mm**: the pad point
sits 6.6 mm **below** the commanded standoff, 0.6 mm outside the 6 mm tolerance, so
the loop exits on its 200-tick budget instead of on convergence. That retires
P240's question (the belt-direction lead could not move it because it was never the
belt direction).

## 2. The lever and its effect

`FRUIT_CATCH_Z_FF=6.6` raises the catch-up's **command** by the measured droop
(the residual's reference stays where it was).

| | control (P239/P240) | **FF 6.6** |
|---|---|---|
| residual | 6.6-6.7 mm (`z=-6.6`) | **5.4-5.8 mm (`z=-2.2..-2.8`)** |
| `catch ticks` | 200 x3/x3 | **22, 22, 22, 22, 29** (+ one 200) |
| `seat` | **1.67 s** | **0.17 / 0.18 / 0.23 s** (+ one 1.67) |
| placed | 6/6 | **5/6** |

**P1 PASSES** (the z component moves by exactly the offset, the norm crosses the
tolerance, the loop exits in 22 ticks). **P3 PASSES**: `seat` 1.67 -> 0.17 s, i.e.
the cycle loses **~1.50 s** of its ~13.3 s (**-11 %**), and every successful attempt
shows it - not a branch.

## 3. The one failure, and why the phase does not adopt

**One of six attempts ran away**: `ticks=200 residual=113.2 mm (x=+44.2 y=+3.8
z=+104.2)` - the pad point ended **104 mm above** the commanded one, on the first
attempt of seed 901, at the full budget. That is not the shipped failure mode
(a miss is 6-7 mm; this is a flight), and **no attempt in P236-P240 (~24 attempts of
the same cell) shows it**. So it appeared *with* the offset.

Two readings, and this phase cannot separate them at n = 6:

* the offset pushes the command into a region where this arm's vertical solve
  diverges on some approaches (a **runaway**), i.e. the lever has a real cost;
* or it is the pre-existing rare flail (P47/P48's class), and 5/6 vs 6/6 is a draw.

**P2 therefore neither passes nor fails**: the placements are 5/6 against 6/6 with a
**new mechanism** in the failure, which is not a harm the phase can attribute.

## 4. What is established, and what the next cell must do

**Established**: the 1.44 s is a **6.6 mm steady-state vertical error**, and it is
recoverable with a 6.6 mm command offset - **a mechanism-level answer** to the
question P236-P240 spent four phases narrowing. The `[catch]` components row is the
instrument that made it decidable.

**The next cell** (registered, not run): `FRUIT_CATCH_Z_FF=6.6` on **2 seeds x 6
episodes** with the control on the same batch, endpoint = the **runaway rate**
(`residual > 50 mm`) and the placed count. If the runaways recur at ~1/6 the lever
is a trade (1.5 s for a 17 % flight risk) and is closed; if they do not, it is a
candidate default that owes the two-line gate, both references and a store
re-baseline.

**Also named**: the 6.6 mm is a *steady-state* error, so the alternative to a
command offset is a **real** fix - an integral term or a gravity feed-forward on the
vertical axis - which would not bias the command into the region the runaway
appeared in. That is the principled version of this lever and it is not built.

## 5. Pins

`tasks.py` **`e3795cf4`** (the components field and the knob), `rl_env.py`
`TASKS_MD5` follow; references **`61fb5202` / `61fb5202` / `18b101bf`** untouched;
checkpoint `p227_panda156`. Evidence `logs/p241/{PREREG.md, comp/, ff/}`.
