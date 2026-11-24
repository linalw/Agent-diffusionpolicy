# P244 results: the "7 % x excursion" is instrument-suspect and is WITHDRAWN

**2026-11-25, `logs/p244/`.** A census of the gross catch-up excursions and an audit
of their provenance. **No `src/` change.** The claim P243 made ("the runaway class
is x, ~7 %") **does not survive this audit** and is withdrawn.

---

## 1. The excursions, all four of them

| phase | cell | value | components | attempt order |
|---|---|---|---|---|
| P241 | shipped + component row | **41.6 mm** | `x=+34.8 y=-19.6 z=+11.5` | **first** of s901 |
| P242 | `Z_FF=6.6` | **419.1 mm** | `x=+66.0 y=+50.5 z=+410.8` | **first** of s901 |
| P243 | axis exit | **97.2 mm** | `x=-96.9 y=+4.6 z=-7.0` | **first** of s901 |
| P244 | axis exit + catch trace | **1079.4 mm** | `x=-65.4 y=-56.3 z=+1075.9` | **first** of s901 |

**They are not one direction**: 42/97/419/1079 mm, dominated by `x` once and by `z`
three times, and the magnitudes span 25x. **And all four are the first catch of
their run** (the first episode of the process; the later five episodes of the same
runs are clean).

## 2. Why the claim is withdrawn: the control exists and it is clean

**P236-P240 ran the same cell 30 times with the same instrumentation minus the
component field, and produced zero excursions.** The field was added in **P241** and
its subtraction is computed **unconditionally, on every tick of the loop**
(`catch_residual_vec = tip - desired_tip`), i.e. exactly the kind of per-tick work
AGENTS section 2 says can move the branch.

So the honest reading is the one the record's own rule demands:

* **shipped (no field): 0 / 30**;
* **with the field: 4 / 42** (P241's own shipped-settings cell included).

That is **not** a demonstration of a cell property. It is consistent with a cell
property at ~10 %, and it is equally consistent with **the instrument perturbing
the first catch of a run** - and the data cannot separate them, because every cell
that shows the excursion also carries the field.

**P243's "3/42 = 7 %, the class is `x`" is therefore withdrawn.** The four
excursions are real (the numbers are in the logs), but their **provenance is
unproven**, and one of them was dominated by `z = +1076 mm`, not `x`.

## 3. Two instrument defects found on the way

1. **The catch trace is overwritten across runs.** The file is
   `catch_{seq:02d}_{arm}.json` with `_catch_trace_seq` per task and a shared
   `FRUIT_CATCH_TRACE_DIR`, so a second process in the same directory restarts the
   sequence and replaces the first run's files - 7 files survived 12 catches, and
   **the outlier's trace is not among them**. A per-run subdirectory fixes it.
2. **The component field is not gated.** It is computed even when the row is not
   printed, so "the row is a diagnostic" is not true of its cost. Gating it on
   `FRUIT_TRACK_DIAG` (and on the axis exit, which needs it) would restore a
   byte-identical shipped path and make the control possible.

**Neither is fixed in this phase**, deliberately: they are the next cell's first
step, and fixing them here without the measurement would be the same mistake P237
made.

## 4. What stands, and what does not

**Stands** (measured with the instrument, and the mechanism is arithmetic):

* the catch-up's exit is a **6.6 mm steady-state vertical error** (P241), the
  shipped loop therefore exits on its **200-tick budget** (P239), and the
  **axis-aware exit** recovers **1.44 s** on 11 of 12 attempts with the command
  untouched (P243). That result does not depend on the excursions: the excursions
  are 4 of 54 attempts and the other 50 all show the same 21-42 ticks.
* the cycle decomposition and the `place`/`ramp`/`grip`/`release` constants
  (P236/P237) are untouched by any of this.

**Does not stand**: "the excursions are an `x` class at 7 % of attempts". They are
4 events of unknown provenance, three of them `z`-dominated, all first-of-run, all
in cells that carry a per-tick subtraction the shipped cell does not have.

## 5. The next cell, named

`FRUIT_CATCH_COMP_DIAG=1` (default **0**) gating the component subtraction, plus a
**per-run** trace directory; then the shipped path is byte-identical and one cell
can answer, **shipped vs field-on**, whether the first catch of a run is perturbed
by the instrument. Until that runs, **no rate is quoted for the excursions**.

## 6. Pins

No `src/` change; `tasks.py` **`58460874`**, `rl_env.py` unchanged by this phase;
references **`61fb5202` / `61fb5202` / `18b101bf`** untouched; checkpoint
`p227_panda156`. Evidence `logs/p244/{run/, ct/}`.
