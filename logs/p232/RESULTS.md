# P232 results: the lane holds 91.7 % under a ±50 % belt-speed wave - and the trigger is blind to it

**2026-11-24, `logs/p232/`.** The objective's first disturbance rung: a real
conveyor's speed is not constant. **No adoption; one instrument fix in
`rl_env.advance`.**

---

## 1. The cells

`FRUIT_BELT_SPEED=0.08`, `FRUIT_BELT_WAVE_AMP=0.04` m/s at
`FRUIT_BELT_WAVE_HZ=0.5` - the surface speed sweeps **0.04-0.12 m/s** -
`FRUIT_EVAL_LATENCY=auto`, seeds 901/902 x 6 episodes.

| cell | wave applies to | placed | `dy` at fire | `t_arrive` |
|---|---|---|---|---|
| baseline (P230, constant 0.08) | - | **11/12** | 0.136 m | 1.71 s |
| W1: wave on the **primitive** only | contact/carry | **11/12** | 0.147 m | 1.84 s |
| W2: wave on **both** paths (fixed) | approach + primitive | **11/12** | 0.154 m | 1.93 s |

`t_arrive` means the fire happens slightly further out under the wave - the
trigger's own arithmetic, see section 3.

## 2. Two instrument defects, both found by running it

1. **The wave only reached the primitive.** P135 ticked it inside the task's
   `_step_sim`; the env advances the physics on **its own** path
   (`SimulationManager.step`), so an armed wave disturbed the contact phase and
   **not the approach** - exactly the phase where a varying speed matters.
   Fixed by ticking it in `advance` too, gated on the task's own flag (`False`
   unless `FRUIT_BELT_WAVE_AMP > 0`, so every shipped path is unchanged).
2. **That fix then killed two runs at startup** (`0/0`, no episode rows):
   `advance(30)` also runs in `__init__`'s scene prime, **before `self.task`
   exists**. Guarded with `getattr(self, "task", None)`.

Combined with P230's two (`self._say`, `self._step`), the pattern is now
explicit: **on this tree an instrument fails at construction or edge sites, and
only a run - ideally with a cell that is known to work - finds it.** Both of
P232's runs that died would have looked like "the cell cannot do 0.08 under a
wave".

## 3. The finding: the trigger is blind to the wave

Every fire row in **all three** cells prints `speed=0.080m/s/encoder`, and the
cell's own `[stats]` line calls that value *nominal*. That is P141's measurement
again: `Conveyor.encoder_speed` is a **setpoint echo** (it is only computed
inside `step()` while the cleats exist, and the cleats are off), while the belt
that actually moves is the `PhysxSurfaceVelocityAPI` value `surface_speed`
returns.

So on a varying line the trigger computes

```
t_arrive = dy / 0.080        # but the fruit is moving at 0.04 .. 0.12
```

an error of up to **2x** in the one number the handover is scheduled on. **The
cell still reads 91.7 %**, and the reason is the layer below it: the primitive's
hover/descent use `_belt_speed_estimate()` (the *surface* speed, P141), and the
hover wait absorbs the mismatch. That is the 4T architecture's bet paying off -
and it is also a named latent defect: **the compensation is a wait, and a wait
spends the lead.**

## 4. Pre-registered verdicts

* **P1 (manipulation) PARTIAL.** The wave is armed and reaches both paths (code
  path + the fixed instrument + `spawner.belt` is set by the env), but the
  *log* cannot show it in the trigger row, because the trigger reads the stale
  encoder. The honest evidence is the mechanism (the fire distance moved,
  0.136 -> 0.154 m) plus the code path; a future cell should print the **surface**
  speed at the fire - that is the one-line instrument this phase discovered it
  needs.
* **P2 (the band) PASSES**: 11/12 >= 9/12, at both seeds (5/6 and 6/6).
* **P3 (the mechanism if it fell) does not apply**: the one failure in W2 is
  `fruit left the pick station during the close` - the P41 station class, not the
  acquisition class.
* **P4 (the falsifier) does not fire**: the lane is disturbance-robust at the
  objective's starting speed.

## 5. What this gives the objective

* **Robustness rung 1 is measured and passes**: ±50 % speed variation at 0.08
  costs **zero** placements (11/12 across three cells, with the failure class
  changing but the count not).
* **The next disturbance rung** (named, not run): a wider amplitude or a faster
  wave, where the hover's absorption runs out; and the **surface-speed row** at
  the fire, which is the instrument that would make the trigger's blindness
  measurable rather than inferred.
* **A real deployment caveat**: a line whose speed varies must feed the trigger
  the *measured* speed. The tree's `surface_speed` already exists (P141); this
  phase shows the trigger does not use it.

## 6. Pins

`rl_env.py` (the wave tick in `advance`, guarded), `scripts/selfcheck.sh` (leg
`P232 belt wave`: both tick paths, guarded, inert unless armed, and
`advance`'s stepping rule unchanged); `tasks.py` **`c16c8291`** unchanged;
references **`61fb5202` / `61fb5202` / `18b101bf`** untouched; checkpoint
`p227_panda156` used as-is. Evidence
`logs/p232/{PREREG.md, wave08/, wave08c/}`.
