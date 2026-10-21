# P28 CLOSE-OUT: the speed-adaptation arc (2026-10-21)

## The owner's premise, audited

"I introduced the belt-speed encoder so the model adapts to different constant belt speeds; even if
faster fails, slower should hold or improve."
**Verdict: the build does not implement that intent, and the arc shows why.**
1. **The encoder is a schedule parameter, not a measurement** (`logs/p27/SPEED_ADAPT_AUDIT.md`):
   with the cleats off (the shipped default) `encoder_speed == cfg.belt_speed`; it threads the
   trigger's arrival math (`t_arrive = dy/v <= lead`), the catch lead, the selector floor, the
   descent deadline - a v x fixed-seconds form that cancels the speed out of the time budget.
2. **The policy never sees the speed** (the observations: 2x RGB-D + 25-D proprio + 8-D goal; the
   only speed-correlated scalar is the target's measured velocity at selection).
3. **The measured response is speed-FLAT** (`logs/p27/SWEEP_RESULTS.md`): the direct 6/6/2/5 of 15
   at 0.08/0.10/0.12/0.15 (no pairwise Fisher p < 0.215); the dominant failure (carried-not-placed)
   is a hand-frame escape of median 278 mm of which the belt feeds at most 24 mm at 0.12 (6-11 % at
   every speed); the scripted two-line reads 13/11/11/10 (the slow side weakly >=, physically).

## What the P28 arc built and measured

* **The channel** (P28-B, `logs/p28i/IMPLEMENTATION.md`): a 26th proprio scalar from
  `trigger.transport_speed()`, zero-initialised (the B0 identity on real windows: paired delta
  0.0000 rad), synthesised per episode from the shard manifests' `supply.belt_speed`; gated by
  `FRUIT_OBS_SPEED=0` (byte-inert default). The per-episode pin chain raises on missing/unpinned
  stores (no silent 0.12) and on conflicts; the two latent width bugs fixed.
* **The data**: the cross-speed collections ss008 (25 @0.08), ss012 (25 @0.12), ss015 (17 @0.15 -
  the 0.15's collection rate 23 % is itself evidence); the merged 67-episode multi-speed store.
* **The fine-tune** `spd_v1`: 6 epochs from `moe_v13s` with the `demos_v11` anchor; the
  counterfactual read shows the channel is not inert (0.12->0.08 max|delta| 2.4e-2).
* **The A/B (the trigger on)**: pooled 16/45 vs 18/45; the 0.15 +3 (Fisher p = 0.231, one draw);
  the 0.12 anchor -1; **the fire census: 90/90 fires were the scripted trigger, 0/90 the model**
  (`logs/p28/ORACLE_GATE_D.md`) - the A/B measured the pre-fire pose, so the channel is
  **untested, not supported**.
* **The autonomy gap**: with the trigger off, the model-side gate fires at its sensor edges
  (finger 0.0288/0.030, |jaw-fruit| 5.9/6.0 cm), the catch-ups hit the 200-tick cap with 110-247 mm
  residuals, and one fire produced a 122 N spike (`logs/p28/probe_*.log`). **It is a fire-TIMING
  gap, not an absent fire path** - the rank-1 next per the Gate D is the fire-tick-label data path
  (~1.5 h): the scripted primitive's own fire ticks as supervision for when to fire.

## The shippable residue (independent of the channel's outcome)

* `supply.belt_speed` in the collector manifest (and the run manifests);
* the per-episode pin chain (the shard -> manifest -> belt_speed; the raise-on-missing/conflict);
* the two latent-width bug fixes (correction.py's config slicing; the data.py/finetune.py pins);
* the no-belt value = the configured speed (not 0.0); the channel decoupled from the trigger knob.
**Behind `FRUIT_OBS_SPEED=0`**: the 26-D observation, `spd_v1`, the (0.12, 0.05) normaliser pair.

## The honest bottom line

The owner's "model adapts to belt speed" needs two things the build lacks: **a real speed
measurement** (or at least an explicit channel the model can use) and **a model-side actuator on
the fire path**. The P28 arc delivered the channel and the data; the fire census shows the
actuator is the binding term. The next ranking (the Gate D): the fire-tick-label data path first,
then the alternatives (the D3-proper, the two-line span work, the 0.15 belt screen - the last
owner-gated and now measured negative on the current tree).
