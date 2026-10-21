# P28 Gate D: the speed-channel arc, reviewed before any further spend (Tier-C, read-only)

**Scope.** Branch `p-supply` at `18a9a46`, clean tree (only `logs/` modified). Read:
`logs/p28/E_RESULTS.md`, `E_TRIGGER_OFF.md`, `SPEED_CHANNEL_DESIGN.md`,
`ORACLE_GATE_A.md`, `logs/p29/SHOWCASE_NOTES.md` + `counterfactual_speed.py`,
`logs/p27/SPEED_ADAPT_AUDIT.md` + `SWEEP_RESULTS.md`, `.slim/deepwork/sorting-pipeline-v3.md`
(P28 sections), and the six v3 logs, the six trigger-off logs, the driver logs, the
`logs/p28i/` verification set and the code the claims sit on. **No simulator run, no file
written except this one.** Every number below is re-derived from a named log or read from a
named line; nothing is quoted from the documents under review.

---

## 0. Verdict in seven lines

1. **The table in `E_RESULTS.md` is exact.** Every cell, class count and close-start median
   reproduces from the logs to the digit (§1.1). The *causal sentence* under it is not
   supported (§1.2–1.4).
2. **The channel never touched a decision.** In the battery that produced the headline,
   **90/90 fires were the scripted trigger and 0/90 were the model** (§1.2). The A/B could
   only move the pre-fire pose — the channel Gate A predicted to be ≈0.
3. **The "0.3–0.5 mm tighter at every speed" is sub-noise** (permutation p = 0.62/0.74/0.70)
   and the identical arm's own two passes move that median by **+0.8 mm** at 0.08 (§1.3).
   The means at 0.15 are identical to 2 dp (3.03 vs 3.03 mm).
4. **"0.15, outside the training speeds" is false** — 0.15 is in the training mix
   (17 episodes; the fine-tune logs `pins=[0.08,0.12,0.15]`). *All three* A/B cells are
   in-distribution, and the design's only extrapolation cell (0.10) was never run (§1.5).
5. **The +3 at 0.15 is one draw**: Fisher p = 0.231, paired 1 B-only / 0 A-only with
   9/15 class-excluded, and the per-leg grip read in the *same log* is adverse
   (lift legs clean 2/8 vs 5/10). **The B4 spend at 0.15 is not the right next step** (§2).
6. **The autonomy gap is real but is mis-diagnosed as "no actuator".** With the trigger off
   the model-side gate fires **13/90** times (not 2/60), the primitive *does* run
   ("closing anyway" at 22–81 mm), and one fire produced a **122 N** force spike. The gap is
   a **fire-timing** gap, not an absent fire path (§3) — that is a 20-minute probe, not a
   re-architecture, and the data question follows it, not before it.
7. **The shippable residue is real and independent of the channel**, but two no-harm runs
   are missing (no `accept.sh`/`accept_policy.sh` since 2026-10-19, before P28-B), `114` was
   never extended to 26-D, and the new verification stub is not a selfcheck leg (§4).

---

## 1. Q1 — is the E read honest, and what does the tighter close mean?

### 1.1 The table (re-derived, not quoted)

| speed | arm | ok | no-contact | carried | close \|y\| p50 | driver line | my parse |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.12 | A | 4/15 | 2 | 9 | 4.0 mm | `spd012_n1v3_driver.log:9,13` | 4.0 |
| 0.12 | B | 3/15 | 0 | 12 | 3.7 mm | `:11,14` | 3.7 |
| 0.08 | A | 7/15 | 0 | 8 | 4.1 mm | `spd008_n1v3_driver.log:9,13` | 4.1 |
| 0.08 | B | 7/15 | 2 | 6 | 3.6 mm | `:11,14` | 3.6 |
| 0.15 | A | 5/15 | 1 | 9 | 2.8 mm | `spd015_n1v3_driver.log:9,13` | 2.8 |
| 0.15 | B | 8/15 | 0 | 7 | 2.4 mm | `:11,14` | 2.4 |
| pooled | A | 16/45 | 3 | 26 | – | – | ✓ |
| pooled | B | 18/45 | 2 | 25 | – | – | ✓ |

All 12 counts and all 6 medians reproduce exactly (`grasped=/placed=` parse over
`[rl] episode` lines; `close_start=` parse over `[acq]` lines, 15 rows per log in every
cell). **No arithmetic error, no cherry-picked cell.** The screen framing ("N=1×15, a
screen, not a verdict") is the right instinct. The problem is everything after it.

### 1.2 The fact the document never states: the model fired 0 of 90

`E_TRIGGER_OFF.md` re-scoped the phase to `FRUIT_POLICY_TRIGGER=arrival + ACQ` on the
grounds that "both fire paths exist". In the battery that produced the read they do not:

```
grep -c 'intercept trigger'  -> 15 15 15 15 15 15      (90 fires, scripted trigger)
grep -c 'closed on the fruit'->  0  0  0  0  0  0      (0 fires, learned gate)
```

(`policy_close` notes are appended only when `direct_fire()` returns true,
`rl_env.py:1636-1647`.) This is Gate A §2.1 arriving exactly as predicted: the trigger
fires ~1.5–2.1 s before the learned gate's 6 cm window and the primitive takes over. The
A/B therefore measures **the pre-fire arm trajectory only** — a pose-quality channel, which
Gate A §2.1 predicted to be ≈0 because pose is speed-invariant. Every mechanistic claim in
§2 of `E_RESULTS.md` has to be read against that: the model has no decision in the loop, so
"the channel changed the decisions that matter" is not testable from this data at all.

### 1.3 The close-start: a 0.3–0.5 mm wobble on a primitive-owned quantity

Three independent reasons the "the fine-tune learned to use the speed scalar" sentence does
not follow:

**(a) The quantity is the primitive's, not the model's.** `[acq] close_start=` is
`acq_info["start_offset"]` — the fingertip-to-fruit offset captured at the **first close
tick** of `grasp_carry_place` (`tasks.py:8115-8121`, printed at `8469-8478`), i.e. *after*
the primitive's premove/axis/hover/wait/catch-up. Gate A §2.1 flagged exactly this (E3 is
mis-specified) and the design's own F-B was supposed to be retired on it. `E_RESULTS.md`
uses it as *the* mechanism. The only policy-touched input to it is the pose the premove
starts from; the endpoint is the primitive's aim.

**(b) It is sub-noise.** Permutation test on the per-attempt medians, 20 k draws:

| cell | median B−A | p | mean B−A | p |
| --- | --- | --- | --- | --- |
| 0.12 | −0.30 mm | 0.74 | −0.35 mm | 0.39 |
| 0.08 | −0.50 mm | 0.62 | **+0.17 mm** | 0.92 |
| 0.15 | −0.40 mm | 0.70 | **+0.00 mm** | 1.00 |

**(c) The identical arm's own replication spread is as large.** Arm A is the same
checkpoint, same seed 77, same env as P27-C1; only the pass differs
(`logs/p27/2{0,2,3}_direct_*.log` vs the v3 A logs):

| speed | A p50 (P27) | A p50 (P28) | A/A delta | p |
| --- | --- | --- | --- | --- |
| 0.08 | 3.30 | 4.10 | **+0.80 mm** | 0.20 |
| 0.12 | 3.70 | 4.00 | +0.30 mm | 0.77 |
| 0.15 | 2.90 | 2.80 | −0.10 mm | 1.00 |

The claimed effect (−0.3…−0.5) is smaller than what re-running the blind arm moves the same
statistic at 0.08 without any channel. And a *constant* offset at all three speeds is the
least speed-specific pattern available: a model that had learned `v` would show something
that scales with `v`, or at minimum the 0.08 cell (trained, 1.5× slower) separating from
the 0.15 cell. It does not.

**What the tighter close most likely is.** A six-epoch fine-tune on 67 new episodes with a
zero-initialised column: the column's gradient is small but non-zero, so the shared trunk
moves slightly, and the pre-fire pose moves with it. That is the *placebo* effect Gate A
B6 named and this arc never ran (§2).

### 1.4 The per-leg read is in the logs and was not used — and it is adverse

`FRUIT_CARRY_DIAG=1` was on in all six cells, so every lift and place leg recorded the W8-B
frame-free metric. Re-derived (`[carry]` rows, escape = `loss_row != None`):

| cell | lift clean/legs | lift escape median | place escape median |
| --- | --- | --- | --- |
| 0.08 A | 0/8 | 302 mm | 636 mm |
| 0.08 B | 1/10 | 274 mm | 465 mm |
| 0.12 A | 3/12 | 261 mm | 513 mm |
| 0.12 B | 2/12 | 270 mm | 473 mm |
| 0.15 A | **5/10** | 309 mm | **416 mm** |
| 0.15 B | **2/8** | 287 mm | **1286 mm** |

`force@onset` medians 4.72–5.62 N (the W8-B 4.90 N reference), onset rows late (46–161) with
the known early no-contact class (rows 1–6). So the grip mechanism is exactly the same
loaded slide at every speed and in both arms — and **at 0.15, the cell that supplied the +3,
the per-leg read is worse for B on both the lift-clean rate (2/8 vs 5/10) and the place
escape (1286 vs 416 mm)**. n is small and the legs are not paired, but the direction matters:
the +3 rate has no grip-mechanism support, and the one per-leg read that could have supported
it points the other way. This is the design's own E4 endpoint, available for free, unread.

### 1.5 "Outside the training speeds" is wrong, and it removes the arc's premise test

`train_spd_v1.log:8-10` prints `rollouts pins {'values': [0.08, 0.12, 0.15], 'manifests':
[ss008, ss012, ss015]}`; `ss_multi` is 67 episodes = 25 @0.08 + 25 @0.12 + 17 @0.15
(`merge.log`). `spd_v1` therefore **trained on all three tested speeds**. `E_RESULTS.md:25`
("0.15, outside the training speeds") is factually wrong, and it is load-bearing: it is the
sentence that supports "the premise's shape ('faster may fail, slower holds') is why the
channel matters where the distribution ends". As run, **no cell is extrapolation**; the
design's only out-of-distribution point, B at 0.10 (P27 has A there at 6/15, ~7 min), was
never collected. The premise's shape is untested by this A/B, not supported by it.

Worse, the 0.15 arm's training data is a survivor sample: `ss015` collected **17/75 = 23 %**
(`collect_ss015.log` final line) against `ss008` **25/46 = 54 %** and `ss012` **25/37 = 68 %**.
So the 0.15 demonstrations are the easiest quartile of a scenario in which the *scripted
expert itself* only succeeds 23 % of the time — which corroborates P27's "the fast side is
negative" (acceptance 5/9; two-line patch 34/60) and is a direct reason not to spend the
battery there.

### 1.6 Q1 answer, in one paragraph

The *read* is honest as a table and dishonest as a mechanism. What the channel changed is
acquirable only through the pre-fire pose, and the statistic used to prove otherwise is the
primitive's own post-catch-up residual, moving less than the blind arm's own replication
noise. The outcome is 16/45 vs 18/45 with every per-cell contrast inside noise (Fisher
p = 0.231 on the best cell). **The correct sentence is: "a 26-D input changed the model's
output by ≤2.4e-2 rad on a synthetic batch (§1.7) and changed nothing measurable in the
simulator, where the model never fires."**

### 1.7 The one surviving channel datum, sized properly

`logs/p29/counterfactual_speed.py` reads max|Δ| 2.42e-2 / mean 1.68e-3 (0.08 vs 0.12) and
1.81e-2 / 1.25e-3 (0.15) against the B0's 0.0. Against the model's own median action error
on its stores (0.133 rad, `logs/p28i/41_b0_119.txt`) that is **≤18 % at the max and ~1 % at
the mean** — "non-inert", not "learned a mapping". It is also a *synthetic random* batch
(random images, random goals, 32 samples); the honest in-distribution version is one minute
of work because `119_rl_fidelity.py` already samples 24 real windows — vary the 26th value on
those windows and report the delta. Do that before quoting the number again.

---

## 2. Q2 — is the B4 spend (0.15 at N=5×15, ~62–76 min) the right next step? **No.**

### 2.1 The numbers that decide it

**(a) The cells are 9× weaker than the document says.** `E_RESULTS.md:30` says "the MDE
~15 pt" at "N=1×15". Exact Fisher, one-sided α = 0.05, power 0.80, p₀ = 0.27–0.47:

| N per arm | MDE |
| --- | --- |
| **15 (this pass)** | **46–50 pt** |
| 45 (the invalid cross-speed pool) | ~25 pt |
| **75 (the proposed battery)** | **21–22 pt** |

15 pt is the *N=5×15* number (Gate A §2.2) and even that is optimistic by ~40 % against the
exact computation. At 1×15 the +3 (8/15 vs 5/15) is **p = 0.231, 95 % CI −15…+55 pt** — the
cell is consistent with a large loss and a large gain.

**(b) The pairing is dead, so the sign test cannot rescue it.** The class-matched pairing
excluded **9/15, 9/15 and 11/15** attempts in the three cells (driver `paired:` lines). The
usable pairs were 6, 6 and 4, with discordant counts 2, 1, 1. Even at N=5×15 the paired test
would be run on ~30 pairs (not 75); reaching p ≤ 0.05 there needs ~21–0 wins. The design's
F-A primary criterion (discordant pairs at p ≤ 0.05) is **unreachable for any modest effect**
and should be retired, not powered.

**(c) The B4 non-inferiority margin is itself ~1 SE.** At 75/arm and p ≈ 0.35 the SE of the
difference is ~5.8 episodes; a 6–7/75 margin is ~1 SE, so F-C fails about **one run in three
under true non-inferiority** (Gate A §2.2's own arithmetic). The battery's anchor gate is a
coin flip, not a gate.

**(d) The battery's MDE (21 pt) exceeds anything the design predicts** ("a few-point
precision gain"). A null is therefore guaranteed by power, not by the channel. Power at
75/arm: 30 % for +10 pt, 53 % for +15 pt, 81 % for +22 pt.

**(e) The prior on 0.15 is the worst in the set.** P27: the scripted two-line curve 0.15 10/20
vs 0.12 11/20 (−1); the acceptance 0.15 5/9 vs 0.12 9/10 (−4); the two-line patch 34/60 vs
45/60. And the scripted expert's collection rate at 0.15 is 23 % (§1.5). Spending the one
decisive battery on the cell where the scenario is hardest and the training data is a
survivor sample is spending backwards.

**(f) Nothing in the pass can be attributed to the channel anyway.** The placebo (constant
0.12 channel, same recipe/seed) and the second *training* seed — both Gate A B6, both ~12 min
offline — were never run. `ls checkpoints/` has no placebo artifact. Without them, a PASS at
0.15 means "six more epochs on 67 episodes did something", which the W7-C (3-0 → 0-2) and R9
(25/75 → 18/75) precedents say is a data effect.

### 2.2 The spend ladder I would sign off on instead (~45 min, then decide)

| # | step | wall | read |
| --- | --- | --- | --- |
| 1 | the per-leg re-read of the six v3 logs (`[carry]` + `[acq]`) | **0** (already on disk; §1.4) | the mechanism, with the W8-B non-overlapping metric |
| 2 | the counterfactual on **real windows** (reuse `119`'s 24-window sample; vary dim 25) | 1 min | an in-distribution channel effect size |
| 3 | **placebo fine-tune** (26th column constant 0.12 for every store, same seed) | 12 min | does the recipe alone move the anchor? |
| 4 | **second training seed** | 12 min | the training-draw spread the W7-C/W8-A flip-flop was made of |
| 5 | **the fire-timing probe** (§3.1) | 20 min | whether the model can *be* the actuator at all |
| 6 | the two-speed battery, **anchor first**, 0.15 attached as a secondary | 2.3 h | only if 1–5 leave the anchor open |

If the owner wants a single number documented at N=5, make it the **0.12 anchor** — it is
the pre-registered kill (F-C), it is the shipped speed, and a FAIL there closes the lane
regardless of 0.15. E_RESULTS proposes the opposite order; that inverts the plan it quotes.

---

## 3. Q3 — the autonomy gap: the smallest credible path to a model-side actuator

### 3.1 The measurement is different from the description (and better)

`E_TRIGGER_OFF.md` says "the learned close gate fires on almost no attempt (2/60)" and "the
model's own close is NOT a viable fire path". Re-derived from the six trigger-off logs:

* the gate fired **13/90** times (A 9/45, B 4/45) — 6× the quoted census, so "almost never"
  is an artefact of P27's four logs, not a property of the interface;
* **every one of the 13 fired at the gate's edge** — `finger` 0.0198–0.0269 against the
  0.030 bound, `|jaw−fruit|xy` 5.8–5.9 cm against the 0.06 bound (`rl_env.py:1528`;
  `spd012_n1/B_1.log` notes). The model closes its fingers while the fruit is still 6 cm
  away — it is a *hover-close*, not a reach-and-close;
* **the primitive does run.** `[task] openarm fingertips … mm from the fruit; closing anyway`
  in 12 attempts across the six cells (gaps 22–81 mm: 22, 23, 23, 27, 30, 44, 49, 57, 61, 77,
  79, 81), followed by real `[carry] grasp_lift` legs. So the failure is not "no actuator" —
  it is "the fire is 5–8 cm and ~2 s too late for an acquisition that costs
  `premove+axis+hover+wait ≈ 2.0 s`" (`[acq] setup` line in the v3 logs);
* **one fire cost 122 N** (`spd012_n1/B_1.log:402`, `force@onset=121.96N`, contacts=2) against
  the 4–5 N of a normal grasp. n=1, but it is a hazard datum that belongs in the record
  before anyone makes the model's close the fire path by default.

The trigger-off cells were also run **without `FRUIT_ACQ_DIAG`**, so there are no `[acq]`
rows for those 90 attempts; the mechanism above had to be read off the close-anyway lines
and the carry rows. That is the cheapest fix in the whole arc.

### 3.2 Is it a data question or an interface question? Both, and the order is interface → data

* **Interface (20 min).** The fire decision exists and is consumed (`direct_fire`,
  `rl_env.py:306-338`), but the fire has no *lead*: the trigger's advantage is not the trigger,
  it is `t_arrive <= lead` — a decision taken ~2 s before contact (`trigger.py:335-338`). Any
  model-side fire path needs the same horizon. That is a measurable proposition, not a design
  essay: re-run the two 0.12 cells with `TRIGGER=off FRUIT_ACQ_DIAG=1 FRUIT_CARRY_DIAG=1`
  (~20 min) and read the fire gap, the close-anyway gap and the contact. If the model fires at
  0.17–0.21 m (the ACQ lead's own geometry) the path is viable; if it only fires at ≤6 cm it is
  a *policy* gap and stage 2 below is the only route.
* **Data (the demos never let the policy fire).** With `TRIGGER=off` the label for "when to
  fire" is never recorded: every demonstration starts at the grasp pose with the trigger
  owning the handover (`rl_env.py:1045-1054`; Gate A §2.1 item 2). The smallest data path is
  **a fire-tick label**: collect a 25-episode store with the trigger *computing* but not
  firing, recording its tick as the expert label (the trigger already returns it,
  `trigger.py:335`), then supervise a scalar fire head or an offset on the finger gate. Cost:
  ~25 min collection + ~12 min fine-tune + a 1×15 A/B (~15 min) ≈ **1–1.5 h**, and it needs
  its own pre-registration because it is a new interface, not a P28 appendix.

**Out of scope note, stated plainly:** "make the policy the actuator" is not a speed-channel
question, and finishing it does not make the speed channel worth having — §1.4 shows the
target class is belt- and channel-invariant. The autonomous-fire path is worth doing for its
own reason (it is the only route to a policy that can act on *any* observation, including a
new speed), and it should be staffed as such.

### 3.3 Ranking against the alternatives

| rank | item | cost | why this rank |
| --- | --- | --- | --- |
| **1** | the fire-timing probe + the per-leg re-read (§3.1, §2.2 step 1) | **20 min** | It converts the arc's headline finding from "no actuator" (wrong) to "a fire with no lead" (measured), and it is the *only* read that can make the channel testable. Cheapest decision in the phase. |
| **2** | the fire-tick label (§3.2) | ~1.5 h | The only credible model-side actuator. It is a data/interface design with its own gate; it does not need the speed channel to be worth it. |
| 3 | **D3-proper** (station + self-centring feeder + boundary-respecting descent) | owner-gated, days | It attacks the classes that actually decide the rate (acquisition/crowding), which no channel can. But R8-A's bounded proxy failed 1/20, the descent boundary is a *tasks.py* item with its own pre-registration, and the owner has to want the scenario change. |
| 4 | **the two-line span work** | sessions | Orthogonal by construction (throughput, not autonomy). R3/P1c already measured that the cadence is flat across the density ladder and P3 closed the place leg by geometry (max safe shift ~30 mm = 0.2 s = 1.3 % of the span). Nothing here touches the policy. |
| **5** | **the belt screen at 0.15** | 1–2 h + a scenario change | Last as *science*: P27 already read the ladder flat and the acceptance negative, and this pass's 0.15 cell adds nothing decisive. Worth doing only as a *product* answer ("is 0.15 shippable?"), and the existing records (2×2 isolation 9/10 · 7/10 · 5/9 · 3/9; the collector's 23 %) already answer it. |

---

## 4. Q4 — the shippable residue

### 4.1 Ships now, independent of the channel's verdict

| # | item | evidence it is sound |
| --- | --- | --- |
| 1 | **`supply.belt_speed` in the collector shard manifest** (`9cbcfa2`) | live: `datasets/ss008/manifest.json` → 0.08, `ss012` → 0.12, `ss015` → 0.15 |
| 2 | **the per-episode pin chain** (`data.py:_resolve_speed`) with **no silent default** | `logs/p28i/42_pin_probe.txt`: `demos_v12_015` **raises** without a 0.15 pin; `ss008` with a 0.12 pin **raises** on the conflict; a merged store resolves per episode (`[0.08, 0.15]`, `00_check_speed_channel.log`). This closes the P27 provenance gap on its own |
| 3 | **the two latent-bug fixes**: `correction.py` slices from the checkpoint's config; `CorrectionController` widths from the payload | default-off code today; both are silent-shift bugs under any width change. `00_check_speed_channel.log` pins both |
| 4 | **`_MANIFEST_SOURCES` + `policy/data.py`/`finetune.py` pins; `belt_speed`/`speed_channel` in the run manifest** | every run manifest changes from here on — that is the point; the `[fruit]`-line compares are unaffected, and I found no manifest hash in the acceptance path |
| 5 | **`belt_speed_scalar`'s no-belt semantics** (report the configured speed; raise if neither) | replaces the `0.0` sentinel, which under (0.12, 0.05) is z = −2.40 and *means* "belt stopped" — the one value that could make a healthy run read as a policy failure with no error anywhere |

### 4.2 Must stay behind `FRUIT_OBS_SPEED=0`

* the 26-D observation and `checkpoints/spd_v1` — the interface of record is the 25-D
  `moe_v12` canary and nothing in this pass changed its standing;
* the fixed `(0.12, 0.05)` normaliser pair as a *shipped* constant. It is an artifact tied to
  the scenario, and the shipped default has moved 0.12 → 0.15 → 0.12 inside two days
  (`5268a8c`, `c35775a`). If the default ever moves again, the pair, the collector's
  `"0.12"` fallback (`40_collect_demos.py:214`) and `assets.py` must move in one commit or
  the manifest becomes a lie (design §6 item 6);
* the channel's **value semantics**: `encoder_speed` is a setpoint echo, so during any belt
  stop it still reads the configured speed (Gate A correction 3). The channel is honest only
  on a never-stop line; enabling it on the indexed path would feed the model a stationary
  fruit labelled as moving.

### 4.3 Gaps before the residue can be called shipped

1. **No no-harm run on the current tree.** `logs/accept.log` is 2026-10-19 03:25 and
   `logs/accept_policy.log` 2026-10-19 11:26 — both **pre-P28-B** (`d2b7847`, today). The
   scripted acceptance does not touch `rl_env`, so it is likely unaffected; the **hybrid**
   one does (`rl_env` + `60_eval_policy`), and it has not been run since the observation
   assembly changed. Gate A §5 item 7's no-harm (≥ the policy floor with `moe_v12` 25-D and
   "the 26-D checkpoint can run the interface of record") is **unverified**. ~30 min.
2. **`114` is still the 25-D guard.** `scripts/114_rl_obs_diff.py:99` still prints
   `same (25-D)`, and it hard-codes `demos_v7`/`moe_v7` (`:33-35`). Commit `78eed95`'s
   "114 exit 0" is true and means only that the 25-D path is unchanged. The two-builder
   agreement for 26-D is **asserted, not measured** (Gate A B4 stands). The shared
   `belt_speed_scalar` makes drift unlikely; the guard is still absent.
3. **`logs/p28i/check_speed_channel.py` is not a `selfcheck.sh` leg.** 67 passing checks that
   run only when someone remembers — and it is the only automated proof of the pin chain,
   the B0 identity and the 25-D inertness. One line in `scripts/selfcheck.sh` (it is pure
   logic, ~1 s).
4. **`p28e/spd*_n1/` were not moved to `_stale/`.** `E_RESULTS.md:39` says "moved under
   `_stale/` where superseded"; `_stale/` holds only the aborted v1 driver log and `v1_012`.
   The six trigger-off cells are still in place (that is fine — they are the evidence), the
   sentence is not.

---

## 5. Q5 — over- and under-claims in `E_RESULTS.md`

| # | claim (line) | verdict |
| --- | --- | --- |
| 1 | "the speed-aware arm closes 0.3–0.5 mm tighter at every speed … the fine-tune learned to use the speed scalar" (:23-25) | **over** — p = 0.62/0.74/0.70; the blind arm's own replication moves the same median +0.8 mm at 0.08; the means at 0.15 are identical (3.03 vs 3.03); the quantity is the primitive's post-catch-up residual (Gate A §2.1/E3) |
| 2 | "the fast end (0.15, outside the training speeds)" (:25) | **wrong** — 0.15 is in the rollouts (17 eps; `train_spd_v1.log:9` pins `[0.08,0.12,0.15]`). All three cells are in-distribution; the only extrapolation cell (0.10) was never run |
| 3 | "the MDE ~15 pt" at N=1×15 (:30) | **over** — 15 pt is the N=5×15 figure (and optimistic); the exact 1×15 MDE is 46–50 pt |
| 4 | "pooled A 16/45 vs B 18/45" (:20-21) | **over** — a cross-speed pool is a cross-attractor pool (AGENTS §2); report it as a count, never as a rate |
| 5 | "the carried class still dominates every cell … untouched by the speed" (:27-28) | **true but incomplete** — B introduces a *new composite* failure reason at 0.08 (`fruit did not follow the gripper`, 2 attempts; `113` prints `NEW failure reasons in B`). That is pre-registered adoption-gate item 4 and must be named (the underlying class is not new; the composite is) |
| 6 | the re-scope's premise "both fire paths present" (`E_TRIGGER_OFF.md:15-17`) | **false in the battery** — 90/90 trigger, 0/90 model. This is the document's biggest omission |
| 7 | "the model's learned close is NOT a viable fire path" (`E_TRIGGER_OFF.md:10-13`) | **directionally right, mechanism wrong** — 13/90 fires (not 2/60), the primitive runs ("closing anyway" at 22–81 mm), and one fire cost 122 N. The gap is fire *timing*, not the absence of a fire path |
| 8 | the counterfactual "the channel is NOT inert → the A/B is warranted" (`SHOWCASE_NOTES.md:10`) | **over** — 2.4e-2 max is ≤18 % of the model's own 0.133 rad error and ~1 % at the mean, on a synthetic random batch. "Non-inert" ✓; "warranted" does not follow |
| 9 | the per-leg mechanism (E4) | **missing** — already recorded in all six cells; and at 0.15 it is *adverse* to the +3 (§1.4). Publish the class table with the rate |
| 10 | the anchor's order (E_RESULTS proposes 0.15 first) | **inverted vs the plan it quotes** — B4/B5 and `run_ab_speed.sh`'s own comment put 0.12 first; the anchor is the kill, the fast end is secondary |
| 11 | "a screen, not a verdict" (:30) | **correct and well-chosen** — keep it; it is the document's best sentence |
| 12 | provenance `logs/p28e/spd*_n1/ (moved under _stale/ where superseded)` (:38-39) | **minor** — only the aborted v1 driver log is under `_stale/` |

---

## 6. Blocking items

**D1 — the mechanism sentence must be withdrawn before the record is used.** `E_RESULTS.md`
§2's "the channel is used" is the only positive claim in the arc and it rests on a
primitive-owned statistic that is inside the blind arm's own noise (§1.3). Either publish it
as a null ("non-inert offline, no measurable simulator effect, the model never fired") or
re-derive a mechanism that the model actually owns. Fix: replace §2's mechanism paragraph;
add the 90/90 fire-path census; add the per-leg table.

**D2 — do not spend the 0.15 battery.** MDE 21–22 pt at 75/arm, power 0.30 for the predicted
effect, F-C is a 1-SE margin, the 0.15 cell is the worst-prior cell with 23 % survivor
training data, and the attribution arms (placebo, second seed) are unrun (§2). If a battery
is authorized anyway, run the **anchor first** and pre-register that the battery is a
disaster screen, not a proof.

**D3 — run the placebo and the second training seed (24 min, offline) before any further
simulator spend.** Gate A B6, still open. Without them, no A/B in this lane is attributable.

**D4 — re-scope the autonomy finding to what was measured.** "13/90 fires, every one at the
gate's edge (5.8–5.9 cm of 6.0, finger 0.020–0.027 of 0.030), the primitive runs and closes
on air from 22–81 mm, one 122 N spike" is a *fire-timing* gap with a *hazard* datum. That
finding is smaller, truer, and points at a 20-minute probe instead of a re-architecture.
Fix: amend `E_TRIGGER_OFF.md` (or supersede it in the record) and add `FRUIT_ACQ_DIAG=1` to
any trigger-off cell from here on.

**D5 — the residue needs its no-harm run before it is called shipped.** No `accept.sh` /
`accept_policy.sh` since 2026-10-19 (pre-P28-B) (§4.3). Also: `114` for 26-D, and the
`check_speed_channel` stub as a selfcheck leg. All three are offline/cheap.

**Non-blocking, one line each:**

* `ss015`'s 17/75 collection rate should be recorded next to any 0.15 number as a survivor
  sample, exactly as the p2b store's imbalance was;
* `spd_v1` itself is worth keeping on disk as the *frozen* candidate if the placebo is ever
  run (same recipe, constant channel) — it is the only trained 26-D artifact;
* `112_rl_ab.sh` exits 1 on a negative verdict, and `run_ab_speed3.sh` prints `exit=1` for
  every cell: a reader cannot tell a negative read from a crashed session. Say so in the
  driver, or capture the report's exit separately;
* the trigger-off cells ran with `FRUIT_OBS_SPEED=1` for **both** arms (`run_ab_speed.sh:5`),
  so A there is the widened 26-D net with a zero column, not a 25-D net. B0 makes that
  byte-equivalent; the label "A = moe_v13s 25-D" is still imprecise;
* the design's §5.2 env block still carries `FRUIT_DYNAMIC_PICK=1`, a no-op on the direct
  path (Gate A non-blocking item), and `AB_EXTRA_ENV`'s six duplicated keys are still
  silently discarded (`112_rl_ab.sh:71`).

---

## 7. What this review did **not** check

* Anything in the simulator. Every number here is a parse of an existing log or a read of
  the code at `18a9a46`.
* The USD articulation's dims 16–21 (the design and Gate A both leave it open).
* Whether `spd_v1` runs through `60_eval_policy` / `accept_policy.sh` — it has never been
  tried, which is the point of D5.
* The `[acq]` rows of the trigger-off cells: they were not printed (`FRUIT_ACQ_DIAG` unset),
  so §3.1's "the primitive runs" is inferred from the close-anyway lines and the `[carry]`
  legs, not from the acquisition trace.
* R3/P1c's span arithmetic (quoted from AGENTS §2 / `logs/r3`, `logs/p1c`, not re-derived).

---

**Status of this document.** Review only; nothing was run, nothing else was written. The
recommended next three actions, in order: **withdraw the mechanism sentence (D1)**,
**run the five offline/probe reads (~45 min: per-leg re-read, real-window counterfactual,
placebo, second seed, fire-timing probe)**, then decide on the anchor battery with the
numbers in §2 rather than the +3 in §1.
