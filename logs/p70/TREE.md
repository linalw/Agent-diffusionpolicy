# P70 — the tree state during the batch (a concurrent lane adopted the result)

`logs/` is gitignored, so this note is the record of what the working tree looked
like while P70's cells ran. **P70 did not flip any default**; a *concurrent*
**P71** lane read `logs/p70/RESULTS.md` while it was being written and started
the adoption (the `FRUIT_OUTPUT_RAILS` default and the low direct lift) in the
same worktree. That is why the pins in `RESULTS.md` §7 must be read with this
file.

## The timeline (from the logs' own prints)

| time | event | evidence |
|---|---|---|
| 08:42:14 – 08:56:36 | **cells C → A → B** | `logs/p70/{C,A,B}.log`, `cells_driver.log` |
| 08:57:41 – 09:07:14 | **D0** (direct control, rails `both` + low lift) | `direct/D0.log` prints `[grasp] lift_dz: ... | default dz=+0.0800` and every place leg reads `@rail` |
| 08:58 – 09:07 | **P71 edits land**: `LIFT_DZ_DIRECT_DEFAULT` `+0.08` → `-0.08`, `output_rails` default `both` → `none`, `scripts/236_p66_lift_selftest.py` follows | `git diff src/fruit_sorting/{rl_env,assets}.py` |
| 09:07:34 – 09:16:31 | **D1** (direct treatment, rails `none` + low lift) | `direct/D1.log` prints `default dz=-0.0800` and every place leg reads `@obelt` |

## What that does and does not change for the cells

* **The scripted cells are unaffected**: they ran before the edits, on the tree
  whose `output_rails` default was still `both`. Cell C re-runs only with
  `FRUIT_OUTPUT_RAILS=both` **explicit** now (`run_cells.sh` sets it).
* **Both direct arms ran the geometry they were meant to**: `FRUIT_LIFT_DZ=-0.08`
  was explicit in both, and the rails were `both` in D0 (the then-default, proved
  from inside by `@rail`) and `none` in D1 (explicit, proved by `@obelt`). What
  differs between the two logs is the printed *default* text, which neither arm
  reads.
* **D0 and D1 therefore straddle a source change that is inert for their own
  arms** — but they are **not** a same-source pair, which is one more reason the
  D0-vs-D1 count (6/15 vs 10/15) is quoted as two draws of a non-reproducible
  loop and never as an effect.

## File states

| file | as measured (P70 batch) | after P71's edits |
|---|---|---|
| `src/fruit_sorting/tasks.py` | `7c00e555` (P70's `_payload_clearance` change is the whole diff) | unchanged |
| `src/fruit_sorting/assets.py` | `9e9804cd` (P70's knob + `OUTPUT_RAIL_INSET` + `output_rail_proud`; rails default `both`) | `e9fd7410` (P71: rails default `none`) |
| `src/fruit_sorting/conveyor.py` | `fb2c58c6` (P70: the shared inset constant) | unchanged |
| `src/fruit_sorting/rl_env.py` | `5886691a` (P70: `TASKS_MD5` follow only) | `cb686f5e` (P71: `LIFT_DZ_DIRECT_DEFAULT = -0.08` + docstring) |
| `scripts/236_p66_lift_selftest.py` | `e3d3bc31`-era, pinned the P4 default `+0.08` | P71 re-pinned it to `-0.08` |

`scripts/238_p70_belt_top_selftest.py` is **default-agnostic on purpose**: it
names `FRUIT_OUTPUT_RAILS=both` explicitly for the "shipped rail geometry" arm, so
it pins P70's arithmetic whichever way P71 leaves the default (`selfcheck.sh` PASS
with both).
