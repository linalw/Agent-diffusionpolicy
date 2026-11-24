# P249 results: the axis-aware exit ships as the **direct lane's** default (scoped, inert on the scripted line)

**2026-11-25, `logs/p249/`.** P248 passed the powered cell (40/40 vs 38/40,
catch-up 200 -> 21 ticks, cycle -1.42 s). This phase hands it to the direct
presentation **without** touching the scripted acceptance, the hybrid canary or the
two-line session.

---

## 1. Why scoped, not global

`FRUIT_CATCH_TOL_AXIS` is read at **task construction**, so a global default moves
every path - the scripted acceptance, the two-line session (P87's release clock
ships there), the collector and the canary - and the record's price for that is the
two-line gate plus **both** motion references re-recorded plus every store
re-baselined. The `_dynamic_profile` pattern (P87/P88/P89) avoids all of it: the
knob resolves **on for `presentation == "direct"`** and `scope-off` everywhere else,
an explicit `0`/`1` wins, and anything else raises.

## 2. A defect was found and fixed before the flip worked

The first attempt applied the flag **before `self.task` existed** (the apply sat
next to `self.spawner.belt = ...`, the task is constructed ~500 lines later), so
`getattr(self, "task", None)` was `None`, the guard swallowed it, and the lever was
**silently inert** - the direct cell read `catch ticks 200 200 200 200 200`,
`seat=1.67s` five times, and **not one** `[rl] catch tol axis:` row. That is
**P97's defect class** (a predicate read before its object exists) reappearing in a
new place.

The fix moves the apply to directly after `PickAndPlaceTask(...)`, and the selfcheck
leg now pins the **order** (`src.index('self.task = PickAndPlaceTask(') <
src.index('self.task.catch_tol_axis = ...')`), so the guard cannot swallow it again.

## 3. The direct cell after the fix

`v=0.08`, seed 901, 5 episodes, `FRUIT_CYCLE_REPORT=1 FRUIT_TRACK_DIAG=1`:

```
[rl] catch tol axis: on (default) presentation=direct
[catch] idx=3  ticks=200 residual=44.4mm (x=+35.9 y=-22.8 z=+12.6)
[catch] idx=10 ticks=21  residual=8.7mm
[catch] idx=7  ticks=80  residual=10.2mm
[catch] idx=2  ticks=21  residual=8.8mm
[catch] idx=11 ticks=21  residual=8.5mm

seat:        1.67 / 0.17 / 0.66 / 0.17 / 0.17 s
cycle total: 16.68 / 12.31 / 12.37 / 11.93 / 12.03 s
placed:      4/5 - and the one loss is **episode 0**, the 200-tick 44.4 mm row
```

**The one failure is the class P246 bounded**: the first attempt of the run, on the
shipped command, at 44.4 mm - i.e. `residual > 50 mm`? No: 44.4 mm, close to but
inside P248's 50 mm reporting bar, and it is the acquisition-shaped excursion (x
dominated) rather than the 1 m runaway. It is the same position as every excursion
of P241-P248 and it costs the episode. **No new class.**

## 4. No-harm, measured (the scripted and two-line paths)

The shipped acceptance is the **two-line** cell, so `accept.sh` is simultaneously
the two-line gate and the scripted no-harm proof:

| check | result |
|---|---|
| `scripts/accept.sh` | **7/10 = 70 %**, 9.5 s/attempt |
| fingerprint | **`matches configs/motion_reference.json`** |
| `[fruit]` stream | **459 vs 459, 0 differing lines** against `logs/p227/accept_final.log` |
| `[rl] catch tol axis:` rows in the scripted log | **0** (the row is gated on `scope-off`) |

So the flip is **resolution-only on the direct lane** and the scripted/two-line
paths are byte-identical. **No reference was re-recorded and none is owed.**

## 5. What this delivers for the objective

| | before | after |
|---|---|---|
| cycle (direct lane, 0.08) | ~13.55 s (`seat` 1.67) | **~12.13 s** (`seat` 0.17) |
| catch-up | 200 ticks on 35 of 40 | **21 ticks on 40 of 40** |
| placed (P248's 40/arm) | 38/40 | **40/40** |

That is the **-10.5 %** cycle at no measured quality cost, now **shipped for the
lane the objective uses**, with the record's no-harm gates green.

## 6. Pins

`tasks.py` **`0f580754`** (the attribute is caller-owned; the exit reads it),
`rl_env.py` (the resolver table, the apply **after** construction, the row gated on
`scope-off`), `scripts/selfcheck.sh` (the `P249 catch tol scope` leg, including the
ordering pin); references **`61fb5202` / `61fb5202` / `18b101bf`** untouched;
checkpoint `p227_panda156`. Evidence `logs/p249/flip/`.
