# P38 phase 2 — PRE-REGISTRATION AMENDMENT A1 (the Gate-1 conditions)

Written 2026-10-25 **before any code change and before any phase-2 run** (the
same tree the original registration was written on: HEAD `dd53d15`,
`rl_env.py` `aa54b022`, `policy/trigger.py` `d7ec85fc`, `tasks.py` `cdde6bd2`).
It amends `logs/p38/PREREG.md` where the Gate-1 review found a claim the
measurement could not carry, and it is binding on phase 2: where this file and
`PREREG.md` disagree, this file governs, and the amended clause is named
(`A1`..`A6`, `M1`..`M4`).

The original stays a record. Nothing in phase 1 (`P1_RESULTS.md`) changes.

---

## A1 (Gate-1 H1) — the "provable refusal" must not pretend the learned close is bound

**The defect.** `PREREG.md` §2 calls the lateral tick a *provable* refusal and
defines the terminal class as "no firable fruit". But the direct interface has
**two** fire paths and the lateral gate has never bound the second one:

```python
direct_fire(intercept=..., policy_close=..., gate_refuse=...)
    == bool(intercept or (policy_close and gate_refuse is None))   # rl_env.py:428
```

`gate_refuse` is the **opt-in** `FRUIT_POLICY_TRIGGER_X_MAX` reach-cliff guard
(R7-A) and is `None` whenever that knob is off — i.e. in every phase-2 run. So a
refused candidate can still be attempted by the learned close
(`finger < 0.030 and |jaw-fruit|xy < 0.06`), exactly the attempted-anyway class
R7-A closed for the *x-edge* guard (`logs/r6/B_RESULTS.md` §1: 3/3, 4/4, 3/3
attempted-anyway refusals flailed). `scripts/828_trigger_nofire_report.py`
already carries a separate `policy-close` no-fire class for this reason: it is
prior art, not a new observation.

**The choice (option (a) of the Gate-1 condition, with a measured closure).**
The class is named for the **trigger** and the early end is gated on a *joint*
closure that the run itself measures, not on an assumption about the future:

* **C1 the trigger refuses.** `should_fire` marks `info["lateral_refuse"] = dx`
  on a tick that passes *every other* gate (`dy <= reach_eff`, `dy >= -0.05`,
  `speed > 1e-3`, `t_arrive <= lead`, and the `assist` finger gate when armed)
  and fails only `|dx| > lateral`. The return stays `False`, so the fire
  decision is unchanged for every input (the shipped path is byte-identical;
  only `info` gains a key that is read when a refuse knob is on).
* **C2 the refusal is permanent for the candidate.** `x` is frozen once the
  fruit is on the belt (`P1_RESULTS.md` §2: the transport contributes
  **0.000 mm**; within an episode the band census's `along` spans a median
  0.096 m while `x` does not move), and the reference is the **station**
  (`FRAME=station`, captured at reset), so `dx` cannot change sign or cross the
  gate on a later tick. The env checks this rather than assuming it: the first
  refusal's `x` is compared with the `x` at the end tick and **the note**
  records the drift `|x_end - x_latch|`. (Gate-2 correction of this sentence's
  original wording: the `[refuse]` row carries only the counters - the drift is
  in the note.)
* **C3 the learned close never fired on this candidate.** The env already
  computes `policy_close` every tick while `not self._triggered`; it latches
  `policy_close_seen` on the first `True` (which fires the primitive anyway).
  The terminal therefore requires `policy_close_seen == False` **from the reset
  through the fruit passing the station** (`dy <= -0.05`, the trigger's own
  downstream gate).

**What the end means, and what it does not.** The END fires at the fruit's
**departure** (not at the latch tick, ~150-400 ticks later), with the note

```
no firable fruit: trigger refuses (candidate x=..., |dx|=... > lateral ...,
x >= ... admitted) and the learned close never fired (best |jaw-fruit|=... cm)
through dy=-0.05 m (the fruit passed the station)
```

It is a statement about the trigger and about the observed close **up to that
tick**; it is not a claim that the policy could never chase the fruit
downstream afterwards. That residual is registered (§A1.1), is measured by the
control arm on the same band, and the class is still a **failure**
(`success=False`, in the rate denominator).

**Falsifiers, rewritten (supersede `PREREG.md` §5 Fb/Fc).**

* **Fb′ (the admission arithmetic, M1 arm C)**: an **`intercept trigger`** fire
  on a candidate whose `lateral refuse:` note exists *for that candidate* →
  the phase fails (the re-selection adopted a below-floor fruit, or `dx` moved).
* **Fc′ (the admission arithmetic, M2 arm A)**: an **`intercept trigger`** fire
  in an episode that also carries the `lateral refuse:` note → re-derive
  `P1_RESULTS.md` §3 and stop.
* A **`policy closed on the fruit`** fire in either probe is **not** a
  falsifier: it is the second path, it is counted (`M1_policy_close`,
  `M2_policy_close`) and reported. If it happens in M1 it *bounds the
  closure*: the report then says "the trigger refuses on N/15 and the learned
  close fires on K/15", and the END's population is the N-K episodes.

**A's M1 prediction, amended.** A (diag only) ends at the horizon; its terminal
is `timeout: no grasp within 1500 ticks` **or** `policy closed on the fruit`,
whichever the band produces. The diag note is predicted on **every episode
whose delivered x is below the floor** (15/15 only if the band is fully
below — see A2).

## A2 (Gate-1 H2) — the bands must be on the belt, and "forced" is measured

**The defect.** `PREREG.md` M1 uses `FRUIT_SUPPLY_X_MIN=0.10`, but the belt slab
is x = 0.11-0.57 (`belt_size[0] = 0.46`, `belt_center[0] = 0.34`), so a draw at
0.10 lands off the edge and falls. Worse, the *delivered* x is
`spawn + offset(instance)` with offsets measured at **-35.9..+69.2 mm**
(`P1_RESULTS.md` §2), so a spawn band is not a delivered band: the spawn
arithmetic ("100 % below 0.173", "28 % refused") is not the delivered one.

**The fix.** M1/M2 run `FRUIT_SUPPLY_X_MIN=0.13` (M1 `X_MAX=0.17`, M2
`X_MAX=0.36`), and the **delivered** distribution is verified before the batch:

1. one `scripts/171_supply_probe.py` run per band (free cadence, SEED=5): the
   `[supply] lateral x:` min/max envelope, the belt bounds it prints, the
   on-belt density and the fell-off/stacked counters;
2. one `logs/p38/probe_drift.py` run at the **M1** band (SEED=5): its
   `[drift] delivery edge` row gives `n<0.173` and the min/max at the delivery
   edge, and at a forced band its out-of-band list names **every** transit
   (delivered x, spawn x, class).

**Registered rule (fixed before the probe runs).**

* **M1 is "forced"** iff the probe's delivered **max < 0.170** (the right
  arm's 0.1730 floor with 3 mm slack) and the delivered **min > 0.115** (the
  belt edge 0.11 + 5 mm). If the delivered max >= 0.170 the M1 upper bound
  drops to **0.16** and the probe is repeated once; if it still leaks, M1's
  endpoint is restated as *the episodes that carry the diag note* (P1 read on
  that population, its incidence reported), and that restatement is recorded
  as a deviation.
* **M2's refused fraction** is `P(delivered x < 0.1730)` **from the probe**
  (and, for the left arm, `< 0.1800`), not `(0.173-0.10)/0.26 = 28 %`; the
  PREREG's "~4 of 15 per run" becomes the measured fraction. The spawn-bound
  arithmetic predicts ~19 % at 0.13-0.36 before the settle offsets.
* A refused-fraction shortfall is **not** a falsifier: P2 is read on the
  refused episodes that exist (`>= 10 of 12` becomes `>= 10 of (the refused
  episodes)`; below 10 the endpoint is *reported as underpowered*, unchanged).

## A2b — the forced/mixed instrument is the *gate*, not a supply band (measured)

Written after the A2 probes and **before** any M1/M2 episode; it supersedes
A2's spawn-band form and M1/M2's scenario, and it is the A2 rule's own
consequence.

The two bands A2 registered were probed (SEED=5, free cadence,
`logs/p38/z1_supply_m1.log` / `z1_supply_m2.log`, plus the M1 band's delivered
census `logs/p38/z2_drift_m1.log`):

| band | probe lateral x (min / p50 / max) | delivered x at the station edge | reading |
| --- | --- | --- | --- |
| **0.13-0.17 (M1)** | +0.080 / +0.150 / **+0.529** | min +0.117, p50 +0.152, **max +0.191**, `n<0.173` **57/65** | **not forced** (12 % above the 0.173 floor) **and not a band**: the free-cadence envelope runs 3 cm past the belt's low edge (0.110) and 18 cm past the band's high edge — the depenetration kicks of 16 fruit squeezed into a 4 cm lane |
| 0.13-0.36 (M2) | +0.120 / +0.229 / +0.391 | - | on-belt, but it shifts the delivered p50 to 0.229 against the shipped 0.264 and needs its own floor arithmetic |

The A2 escape hatch ("narrow the upper bound to 0.16 and repeat") **cannot
work**: the delivered x is `spawn + offset` and the +35 mm kiwi instance puts a
0.16 spawn at 0.195, so no on-belt band wide enough to avoid crowding is
forced. A2's second clause therefore applies, and this amendment fixes *which*
population M1/M2 measure:

* **M1 = the shipped supply + `FRUIT_POLICY_TRIGGER_LATERAL=0`.** Every
  would-fire tick fails only the lateral gate (`|dx| > 0` for any fruit not
  exactly on the station line), so the refusal is **100 % by construction**, on
  the shipped delivered-x distribution, with no scene change and no crowding.
* **M2 = the shipped supply + `FRUIT_POLICY_TRIGGER_LATERAL=0.06`.** The
  refused set is `x < station_x - 0.06` — the **P2b-era gate** (the documented
  refused-outer-band configuration of `P1_RESULTS.md` §3's 3195-episode row),
  i.e. ~35-50 % of the shipped delivered band (`|dx|` p50 ≈ 6 cm there), and
  the refused fraction is read from the notes. The registered "~28 %" is not
  reproduced; the *power* is, and on the conservative side (more refused
  episodes than registered).

**Why this is a *better* instrument for the registered question, not a
work-around.** With a below-floor band (`|dx| > 0.16`) the learned close is
*geometrically impossible* (it needs `|jaw-fruit|xy < 0.06`), so the H1 defect
could never have shown up in the registered M1: the closure would have held
trivially. On the shipped band the close is a live path, and the M1-B smoke
already measured it: of 4 episodes, 3 ended with the named class (ticks
380/510/553, `best |jaw-fruit|` 7.5-9.5 cm) and **1/4 fired through the learned
close at 5.8 cm and placed** (`logs/p38/z3_smoke_m1b.log`). That is A1's C3
term doing its job: the END declines to name an episode whose second path
fired.

**What changes in the predictions** (`PREREG.md` §3 M1/M2, A4):

* M1 arm A: the diag note on **15/15** and a terminal of `timeout` **or**
  `policy closed on the fruit` (measured ratio reported; the smoke reads ~1/4
  closed). M1 arm B: the named class on the complement, median ticks <= 600
  (the smoke: 380-553). M1 arm C: **0 adopted / 4 scans**, then the same class
  (`|dx| <= 0` admits nothing) — the registered boundedness read is unchanged.
* M2: the refused fraction is **read from the notes** (`fruit x=` in each
  `lateral refuse:` note), not from spawn arithmetic; A's refused episodes are
  predicted to end in `timeout` (a fruit >= 6 cm off the station line cannot
  reach the learned close's `< 6 cm` window unless the jaw chases it), C's
  refused episodes are predicted to convert through the re-selection.
* The `Ff` guard, the 4-scan bound, `RESEED_MAX`, the 1500-tick horizon, the
  reward and every scripted path are **unchanged**.

**Registered deviations to report**: the M1/M2 bands of `PREREG.md` §3 are not
run; the `FRUIT_SUPPLY_X_*` overrides are not used by phase 2 at all; and M2's
refused fraction is a measured ~28 % rather than a construction. The A2 supply
table stands as the evidence for all three.

---

## A2d — P2's operationalisation: "fires" cannot separate the arms (measured)

The M2-A smoke at the amended gate (`LATERAL=0.06`, 8 episodes,
`logs/p38/z7_smoke_m2a6.log`) read **4/8 refused** (the predicted 35-50 %) and
the refused episodes' terminals were **2 `policy closed` (both chased and lost
the grip) + 2 `fruit fell off the line`** — **0 timeouts**. Two consequences,
registered before the M2 batch:

1. **P2's literal form is void.** "The refused episodes that fire: A 0 of its
   refused" is false by construction: `direct_fire`'s learned path fires on a
   refused candidate whenever the policy drives the jaw within 6 cm (measured
   at |dx| = 7.5 and 7.6 cm). "Fires" therefore cannot separate A from C.
2. **The class the lever targets in the shipped scenario is not the timeout**;
   it is "the refused episode burns on a chase" (close → grip loss) or "the
   fruit rides off the line". The END cannot name those either (a close is
   excluded by C3, and a fell-off finalises with its own note) — so the END's
   incidence on the shipped gate stays the rare no-fire class, as designed.

**P2 (amended, three parts).**

* **P2a-i - the lever's correctness (the gate).** *When the selector returns a
  candidate at a refused episode's scan*, C must adopt it (>= 80 % of the
  non-empty scans) and the adopted episode must then fire on the new candidate
  (>= 80 % of the adoptions). This separates the harness's behaviour from the
  supply's availability, and it is the mechanism P38 owns.
* **P2a-ii - the supply limit (reported, not gated).** The adoption incidence
  among refused episodes. The lane is **starved at the station ~46 % of the
  ticks** on the shipped scatter supply (`starvation right: no candidate
  4807/10800 = 44.51 %` … `right_line` 62.28 %, longest empty runs 6.2-18.9 s,
  `logs/p38/z1_supply_m1.log`), so a same-lane re-selection has no candidate to
  offer about half the time **by the supply's own design**, not by the lever's.
  The measured incidence is reported with that number beside it and the scan
  budget's own split (`empty` vs `off-lateral`); the supply lever is P38b.
* **P2b - the outcome (reported, not gated).** Placed among the refused
  episodes, C vs A: the exact one-sided Fisher p, the counts and the refused
  episodes' terminal distribution (close-chase / fell-off / timeout /
  no_firable). At ~12-25 refused episodes the outcome effect cannot be
  separated from noise; gating it would be the P37 lesson (a mechanical rule
  with no power).
* **Fe** keeps its role on the *converted* population: if C's converted
  episodes are carried-not-placed more often than A's overall carried rate,
  the lever trades a no-fire for a grip failure.

**The scan retry (registered with the amendment).** One scan per 60 ticks
(0.5 s), up to the 4-scan budget, i.e. a 1.5 s window inside the ~2.5 s the
fruit takes from the refusal latch to the station. Measured: the same-instant
form returned `None` in 3/3 refusals (`z6_smoke_m2c6.log`) and the 4×0.5 s
form in 8/8 scans of 2 refusals (`z8_smoke_m2c_retry.log`, `scans=4 empty=4`),
so the retry does not rescue a starved lane - the budget and the bound are
unchanged and the *measurement* is what the batch reports.

---

## A3 (Gate-1 H3) — M3/P6 gate on the run level, not on a 1-sd point rule

**The defect.** The un-parked right arm's base rate is ~45 % (P35's control:
23/51) and the M3 batch realises ~47 right-arm episodes per arm; the sd of the
difference is then `sqrt(2*0.45*0.55/47) ≈ 0.103`, so a `-0.10` point rule
false-fails about **1 in 6** batches under the null. The same applies to P6's
`+5 %` cycle bar.

**The fix (both endpoints, same shape).** The gate is a **run-level unanimity**
rule over the 5 seed pairs, with the pooled number reported as a descriptive:

* **P4 (amended)**: the batch **fails** iff **all five** per-seed-pair
  right-arm placed deltas are **negative** *and* the pooled delta is
  `<= -0.10`. Under the null the sign part alone is `p = 1/32 = 0.031`, so the
  false-fail is <= ~3 % instead of ~17 %. The pooled delta, the per-pair
  table, the per-arm n and a 95 % interval are reported; `-0.15` is the
  **severity** threshold quoted beside it; `> -0.10` alone is reported as
  "no consistent harm signal".
* **P6 (amended)**: fails iff **all five** per-run fired-only median-cycle
  deltas exceed **+5 %**; the pooled median is the descriptive.
* The control is **same-batch by construction**: A and C run interleaved in one
  claim with the same seed per pair (the P37 shape). A fresh control is not
  needed because no shipped default moves.

## A4 — M1/M2 amendments

* **M1 arm C prediction (amended).** 0 adopted candidates, **4 candidate
  scans** (the scan bound), then the END; the `RESEED_MAX` budget is
  **unreachable** in M1 because the budget counts *adoptions* and there are
  none — the binding bound is the 4-scan loop. Ticks for B and C are
  `(dy0 + 0.05)/0.12 * 120` from the reset (the END is at the fruit's
  departure), i.e. **~300-500 ticks** for the shipped ~0.40 m selection floor,
  **not** the 1500 of A. Registered bar: median **<= 600** ticks for B and C.
  (The original "<= 500" assumed the latch tick was the end tick; with
  `ACQ=1` the latch is *earlier* than 0.30 m — the effective lead reaches
  `0.9 + 0.6 + d/0.2 <= 4.5 s`, so the fire window opens at `dy = lead*speed
  <= 0.54 m` — and the end is set by the departure, not the latch.)
* **M2 pairing (amended).** A and C are different branches, so the paired
  episode index does **not** guarantee the same fruit. The per-episode
  `(arm, category)` agreement is checked **first**: if any pair disagrees the
  McNemar pairing is **dropped** and P2 is read **unpaired** (one-sided Fisher
  exact on the refused-episode conversion table), with the paired table kept
  as a descriptive. Registered before the batch.
* **M2 conversion population.** "Refused episode" = an episode that carries a
  `lateral refuse:` note (A) or one where the C branch's first candidate was
  refused (C), counted from the note, not from the delivered-x arithmetic.

## A5 — M3 amendments (the note level, symmetrically)

* **P5 (amended)**: compare the failure-reason sets at the **note level**: each
  episode's notes list is split into items (`ast.literal_eval` on the printed
  `notes=[...]`), the attribution notes (`lateral refuse:`, `reseed:`,
  `no firable fruit:`) are removed and replaced by the single class key
  `lateral-refuse` when an episode carries any of them; a key present in
  **only one** arm (either direction, not just C) fails P5. The original text
  compared only "new in C", which cannot see a reason the lever *removed*.
* **Exposure (M4/P4 arithmetic, corrected)**: the M3 scenario is the patch
  band, whose direct delivered-x exposure is **0.31 %** below 0.173 and
  **0.77 %** below 0.180 (`P1_RESULTS.md` §1[2], n = 653), **not** the pooled
  0.06 % (`§3`'s shipped-interface census). Over 150 episodes that is
  **0.5-1.2 expected events**, so P4/P5/P6 remain **safety checks with the
  exposure reported**, never power tests. Consequence for the reading: an M3
  batch with 0 refusals measures *no exposure*, not "the lever is inert".

## A6 — M4 and the minors

* **M4 (amended)**: the scripted no-harm is `accept.sh` twice (knobs unset,
  then all four set: `DIAG=1 END=1 RESEED=1 MAX=2`) plus `selfcheck.sh`. The
  requirement is byte-identity of the **`[fruit]` stream** and
  `fingerprint: matches`; the knobs are direct-only so the scripted path
  should never read them — that is what the compare proves.
* **"Attribute every never-fired episode" → "attribute every *refused*
  episode"**: the never-fired population also contains `fruit fell off the
  line` (P1 §3: one of the two low-x episodes) and the opt-in guard's high-x
  refusals; the lever names the lateral class only.
* **The budget is 135 episodes**, not 90: M1 = 3 arms x 15 = 45, M2 = 2 arms x
  3 runs x 15 = 90. M3 = 10 runs x 15 = 150 as registered.
* **The "10x" wording**: P1 §3 says the P37 batch's 1/150 is "a 10x
  over-representation"; `1/150 = 0.67 %` against `0.06 %/episode` is **~11x**,
  and it is batch clustering, not a rate. Quote "~11x, clustering".
* **Check ordering (registered)**: `lateral_refuse` is marked **after** the
  `dy`/`speed`/`t_arrive`/`assist` gates and **before** `x_edge_refusal`. If
  both would refuse (only possible with `X_MAX` set, never in phase 2) the
  `x_refuse` key is also set and the x-edge note keeps precedence, unchanged.
* **Prior art**: `scripts/828_trigger_nofire_report.py` (the `policy-close`
  class) and `scripts/811_trigger_test.py` (the `direct_fire` truth table) are
  extended, not duplicated; `811` pins the new lateral-refusal truth table and
  the END predicate offline.

---

## The amended knob table (the implementation contract)

| knob | default | read at | behaviour |
| --- | --- | --- | --- |
| `FRUIT_POLICY_REFUSE_DIAG` | `0` | first C1 tick per candidate | one note (`lateral refuse: ...`), **run-neutral**, ON in every phase-2 arm |
| `FRUIT_POLICY_REFUSE_END` | `0` | C1 latched **and** `policy_close_seen == False` **and** `dy <= -0.05` | end with `no firable fruit: ...` + `outcome="no_firable"`; else the horizon note is unchanged |
| `FRUIT_POLICY_RESEED` | `0` | first C1 tick per candidate, `not self._triggered` | up to 4 `select_target(..., lane=self._bin_index, exclude=seen)` scans; adopt the first candidate with `|x - station_x| <= lateral`; implies the diag; bounded by `..._MAX` adoptions |
| `FRUIT_POLICY_RESEED_MAX` | `2` | with `RESEED` | adoptions per episode (`0` = off); M1 cannot reach it (0 adoptions) |

All four are validated `presentation == "direct"` (a ValueError otherwise, the
`FRUIT_ARM_PARK` / `FRUIT_PROPRIO_SPOOF` convention) and off they are one
`False` branch and no reads: the shipped scripted/policy paths are
byte-inert (M4 proves it).

## The amended decision rule

Unchanged from `PREREG.md` §6 except that P4/P5/P6 are the A3/A5 forms and the
falsifiers are Fb′/Fc′. `adopt-recommended` still means "phase 3 may flip it on
with the owner's sign-off"; phase 2 changes **no** shipped default.

## What would make this amendment wrong (named in advance)

1. **The END masks a close.** If A's M1 shows a policy close *after* the tick
   where B/C's END would have fired (i.e. after the fruit passed the station),
   then C3 is not a closure and the END changes the outcome. Measured by
   `M1_policy_close` on A; if A shows any close that latched later than the
   fruit's departure, the END is void and B collapses into A's horizon form.
   (Gate-2 readout: the close tick's own `dy` is now printed by the `DIAG`
   (`[refuse] close: tick=... dy=...`) and measured on the forced band in
   `P2_RESULTS.md` §3c - **this falsifier FIRED**: 1 of 3 closes latched at
   `dy = -0.074 m`, after the departure. The consequence registered here is
   taken: C3 is not a total closure, the class must be read as "no close before
   the departure", and a flip needs a re-registered definition or a
   post-departure grace window. The shipped-band readout is still owed.)
2. **The delivered band leaks.** A probe delivered max >= 0.170 at both the
   0.17 and the 0.16 upper bound → M1's population is the diag-note episodes,
   not "15/15".
3. **The re-selection has no candidate.** If the M2 scans return `None` in
   most episodes (the lane is starved or everything is below the catch floor),
   P2 reads "the supply has no alternative", which is the PREREG §9.1 risk
   materialising — reported, not spun.
