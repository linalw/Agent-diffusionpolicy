# P218 pre-registration - the size-conditioned scripted skill

P216 showed the learned policy never approaches a 3.1-3.4 cm fruit (`fired=0`, 0.65-1.18 m
behind); P217 showed the shipped scripted catch places **5/6** lychees on the same hand and
pool at 9.65-10.61 N. The cheapest success lever is therefore a **skill route**: small
fruit -> the scripted `task.run` skill, large fruit -> the learned policy.

**Knob.** `FRUIT_SMALL_HANDOVER=1` (default off), `..._DIA=0.040`; direct + ablate none
only. In `act`, a sample at/below the diameter cut calls `_run_scripted()` (the same
`task.run` as `--ablate scripted`) and the episode finalizes; larger fruit run the
learned policy. This is a **hybrid**, stated as such: the learned model owns the large
fruit and the scripted skill owns the small class.

**Cell.** Lychee-only supply, seed 808, 6 episodes. The control is P215's 60 N learned
cell (1/6); the scripted control is P217 (5/6). Endpoints: placed count, the `[rl]
episode` notes, and the scripted attempt's own force/lift. Falsifiers: F1 the handover does
not fire (a small fruit still runs the policy); F2 the count is below 4/6 (the direct
env's `task.run` does not reproduce the scripted control); F3 the per-attempt span is
more than 30 % above the scripted control's 15.3 s.

A pass earns the mixed-pool cell and a seed-303 repeat. The default stays off; a hybrid is
not a learned small-fruit policy.
