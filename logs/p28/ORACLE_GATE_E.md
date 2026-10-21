# P28 Gate E: the close-out and the rank-1 next, reviewed before the next spend (Tier-C, read-only)

**Scope.** Branch `p-supply` at `c189f18` (clean except `logs/`). Read: `logs/p28/CLOSE_OUT.md`,
`ORACLE_GATE_D.md`, `E_RESULTS.md`, `E_TRIGGER_OFF.md`, `NOHARM.md`, `SPEED_CHANNEL_DESIGN.md`,
`ORACLE_GATE_A.md`, `logs/p27/SPEED_ADAPT_AUDIT.md` + `SWEEP_RESULTS.md`, the P28 sections of
`.slim/deepwork/sorting-pipeline-v3.md`, `probe_A.log` / `probe_B.log` + their drivers,
`noharm_accept.log` / `noharm_policy.log`, `logs/p28i/*`, `logs/p13/IMPLEMENTATION.md` +
`logs/p14/A_RESULTS.md`, `logs/p29/counterfactual_speed.py`, and the code the claims sit on
(`rl_env.py`, `policy/finetune.py`, `policy/skills.py`, `dataset.py`, `scripts/111`, `114`,
`105`, the `logs/p28e/spd*` cells). **One offline re-run was made** (`scripts/105_motion_regression.py
logs/p28/noharm_accept.log --fingerprint configs/motion_reference.json`; parse-only, writes
nothing) and one stream compare (`[fruit]` lines vs `logs/p27/10_acc_012_flip.log`). No simulator
run; no file written except this one.

---

## 0. Verdict in nine lines

1. **The close-out's four load-bearing claims are correctly scoped** (the premise audit, "the
   channel is untested, not supported", the fire-timing diagnosis, the residue) — §1.1. It is
   honest where it matters and wrong in six details (§1.2), five of which are *under*-claims.
2. **The probe strengthens the diagnosis and also narrows it:** 3/15 in `moe_v13s`, **0/15 in
   `spd_v1`** — the 26-D arm produced no fire at all, which the close-out does not say (§1.2 #4).
3. **The 122 N datum is mis-sourced and understated.** It is not in `probe_*.log`; the probe's own
   worst is **179.92 N** (`probe_A.log:428`), with a second at 26.70 N and one *clean* 5.14 N
   grasp. The close-out cites the probe for a number from `logs/p28e/spd012_n1/B_1.log:402`
   and omits both the worse spike and the success (§1.2 #2).
4. **"The policy never sees the speed" is false as written.** `goal[4]` (the measured `vy` at
   selection) tracks the belt at the median in all three stores (−0.080 / −0.117 / −0.150 m/s);
   its per-episode sd (0.027–0.065) is the order of the level spacing. The honest sentence is
   "no explicit speed input; one noisy witness, ~1.1 σ of the normaliser at 0.08 vs 0.12" —
   which is what Gate A §1 already said (§1.2 #1).
5. **The rank-1 next as designed is an imitation of the trigger, and its ceiling is the
   trigger.** The labels it proposes are the scripted fire ticks, so the best possible head
   reproduces a two-line rule the env already evaluates exactly (`t_arrive = dy/v <= lead`,
   `trigger.py:335`). Worse, **no training can move the fire today**: the "learned" gate is
   `finger < 0.030 and distance < 0.06` (`rl_env.py:1528`), an env-side distance bound, so the
   pads must be within 6 cm or the model's finger command cannot fire anything (§2.1).
6. **Two label sources already exist on disk, so the 25-min collection in the estimate is
   avoidable** — but one of them cannot supply the label's frame (§2.2): in **67/67** episodes
   the recorder has a **1.5–1.7 s gap immediately before the first close**, and the derived fire
   tick falls inside it. The r9 rollout store (56 episodes) ends *at* the fire and does have it.
7. **A cheaper decisive probe exists and it is not training**: an offline fire-tick residual audit
   plus one lead-residual arm (~50 min total, no new head, no model change) can kill the idea
   before the fine-tune. Cost of the design as written is **~4–5 h**, not 1.5 h (§2.5).
8. **The alternatives rank: residue completion first, D3-proper second (owner-gated), the two-line
   span third, the canary battery last, the 0.15 belt screen closed** (§3).
9. **The no-harm protocol is satisfied *for the P28-B diff* — and the close-out does not cite its
   own best evidence**: the acceptance's **381/381 `[fruit]` lines are byte-identical** to
   `logs/p27/10_acc_012_flip.log`. But `accept.sh`'s gate is not satisfied on the shipped tree
   (105: 7/10 < the 0.75 floor, `fingerprint: DIFFERS`, reference dated 2026-10-08), which
   predates P28-B and must be recorded before "verified" is used unqualified (§4).

---

## 1. Q1 — the close-out's honesty

### 1.1 The four claims that carry the document: all sound

| claim (`CLOSE_OUT.md`) | verdict | the evidence |
| --- | --- | --- |
| "the encoder is a schedule parameter, not a measurement … `encoder_speed == cfg.belt_speed`" (:8-11) | **correct** | P27-A §1.1; the acceptance still self-reports `encoder=-0.120 m/s nominal (command -0.120, no cleats to measure travel)` (`logs/p28/noharm_accept.log:722`) |
| "the measured response is speed-FLAT … no pairwise Fisher p < 0.215" (:14-17) | **correct** | `SWEEP_RESULTS.md` §2, the 6/6/2/5 ladder |
| "the fire census: 90/90 fires were the scripted trigger, 0/90 the model … the channel is untested, not supported" (:31-33) | **correct and the document's best paragraph** | Gate D §1.2; the re-scope's premise was false in the battery |
| "the shippable residue" (:42-46) | **correct**, one item missing | Gate D §4.1 items 1-5; the missing one is `_MANIFEST_SOURCES`'s consequence — every run manifest changes from here on, gate or no gate |

### 1.2 The details that are wrong — one over-claim, one mis-sourcing, four under-claims

**#1 (over-claim). "The policy never sees the speed" (:12-13).** Measured: the goal's `vy`
(`goal[4]`, frozen at selection) is a real speed witness.

| store | belt | `goal[4]` median | per-episode sd | range |
| --- | --- | --- | --- | --- |
| `ss008` | 0.08 | −0.080 m/s | 0.036 | −0.161 … −0.024 |
| `ss012` | 0.12 | −0.117 | 0.065 | −0.286 … −0.046 |
| `ss015` | 0.15 | −0.150 | 0.027 | −0.170 … −0.080 |

The level spacing (0.03–0.04 m/s) equals the within-level sd, and the normaliser
(`goal_mean[vy] = −0.05705`, `std = 0.03659`) puts 0.08 and 0.12 **1.09 σ** apart — P27's own
number. The close-out's parenthesis ("the only speed-correlated scalar is the target's measured
velocity at selection") states the counter-evidence to its own headline. The sentence to keep:
**the policy has no explicit speed input; the channel de-noises a cue that already exists**
(Gate A §1: "a precision fix for a cue that exists — not new information").

**#2 (mis-sourced, and understated). "one fire produced a 122 N spike (`logs/p28/probe_*.log`)" (:34-37).**

```
grep -o 'F=[0-9.]*N' logs/p28/probe_A.log | sort | uniq -c
      1 F=179.92N      1 F=26.70N      1 F=5.14N        # no 122 N anywhere in either probe
```

The probe's three model fires (`probe_A.log:402, 413, 428`) read **26.70 N, 5.14 N, 179.92 N**.
The 122 N is Gate D's datum from `logs/p28e/spd012_n1/B_1.log:402`. Three corrections: the
provenance is wrong; the probe's worst is **1.5× worse** than the number quoted; and the probe
also contains the **counter-example** — fire 2 closed on the fruit at 5.9 mm residual, 5.14 N,
`success=True` (`probe_A.log:413, 425`). A hazard datum and a viability datum, both mis-stated in
the same sentence.

**#3 (under-claim). The same paragraph omits the 26-D arm entirely (:34-38).** Probe counts,
re-derived: `moe_v13s` **3/15** fires (finger 0.0281 / 0.0131 / 0.0288; |jaw−fruit| 5.9 / 6.0 /
5.9 cm), `spd_v1` **0/15** (no `[acq]` row, no `closing anyway` line; 14 × "fruit fell off the
line" + 1 × timeout). So the fire-timing gap is *entirely* the 25-D model's; the speed-aware
model never commanded a close inside the 6 cm window in 15 attempts. n is small (Fisher p ≈ 0.11)
and it is one seed, but it is the opposite direction from "the channel helps" and it belongs in
the paragraph that diagnoses the autonomy gap.

**#4 (under-claim). The "two constraints" of the diagnosis are right but stated as one.** The
probe's fires show a *2-of-3* pattern, not a uniform one: two fires at the gate's edge with
catch-ups at the 200-tick cap (residuals **110.4 mm**, **246.9 mm**) and one fire at
finger = 0.0131 (not the edge) with a 31-tick catch-up and a **5.9 mm** residual. The close-out's
"fires at its sensor edges (…0.0288/0.030, 5.9/6.0 cm)" describes the two failures. "The catch-ups
hit the 200-tick cap with 110-247 mm residuals" is true of the failures and false of the third.

**#5 (omission of a Gate-D blocking item). D3 (the placebo fine-tune + the second training seed,
24 min, offline) was never run and the close-out does not say so.** `ls checkpoints/` has no
placebo; `train_spd_v1.log` is a single seed; the counterfactual is still the *synthetic random*
batch (`logs/p29/counterfactual_speed.py:18-26`), which Gate D explicitly said must not be quoted
again before the real-window re-read. The close-out re-quotes it (:28-29) with the "not inert"
framing — technically true, materially misleading in the same way Gate D §1.7 sized it
("≤18 % at the max and ~1 % at the mean"). The real-window version (119's 24 windows) was never
built.

**#6 (inherited documentation defect, not the close-out's).** `E_RESULTS.md` was "corrected" by
*prepending* a correction; the body still says "the fast end (0.15, **outside the training
speeds**)" and "within the ~15 pt MDE at N=1x15" (:32-33) three lines under the paragraph that
declares both false (46–50 pt, Gate D §2.1a). And `E_RESULTS.md:39`'s "moved under `_stale/`"
remains false: `logs/p28e/_stale/` holds only `spd012_n1_driver.log` and `v1_012`. The close-out
does not repeat either claim, so it is clean — but it cites a file that contradicts itself.

### 1.3 Q1 answer

**Yes, the close-out is honest where it decides things, and it under-sells more than it
over-sells.** The premise verdict, the "untested, not supported" verdict, and the fire-timing
diagnosis are each exactly what the logs support, and the one number that a reader would carry
away ("122 N") is the *least* accurate line in the document — in the reader's favour, because the
real worst case is 179.92 N. The under-claims are the ones to fix in the record: (i) the probe's
clean 5.9 mm fire shows the path *works* once; (ii) the 26-D arm fired 0/15; (iii) the no-harm has
a byte-identity proof the document never mentions (§4.1); (iv) the 122 N's provenance; (v) D3's
non-disposition.

---

## 2. Q2 — the rank-1 next (the fire-tick-label data path): designed, and its ceiling

### 2.1 The structural fact the design must start from: the fire is not a model output

```python
# rl_env.py:1528
policy_close = bool(finger < 0.030 and distance < 0.06)
```

`finger` is the model's commanded finger (`action[7]`); `distance` is the env's jaw-to-fruit
measurement. So "the model fires" means "the model's finger command dropped below 0.03 *while the
env agrees the fruit is within 6 cm*". Consequences:

* **the model cannot fire early by closing early.** The gate is a *conjunction*, so the later
  condition dominates: at 0.24 m (a ~2 s lead at 0.12) `distance < 0.06` is false, no fire
  happens on that tick, the pads close on air, and the fire still occurs — when the fruit later
  crosses 6 cm. So the *distance bound*, not the finger, sets the fire tick;
* therefore **any amount of fire-tick supervision through the finger channel alone is a measured
  no-op by construction.** The design needs an interface change (a widened/parameterised gate, or
  a new fire input to `direct_fire`, `rl_env.py:321-338`) *before* the labels can do anything;
* and the primitive re-aims after a fire: the two failed fires opened from `sep@onset` 48.7/77.5 mm
  with `contacts@onset=0` (the clean one started with 2 contacts), i.e. `grasp_carry_place` owns
  the hand from the fire tick on. So moving the fire *earlier* is not obviously unsafe — the risk
  is only the lead being wrong.

This one paragraph is missing from the Gate-D sketch and from the close-out's "~1.5 h"; it is the
single reason the estimate is wrong.

### 2.2 Where the labels come from — two sources exist, one is unusable at the label

**(a) The demo stores (`ss008/ss012/ss015`, `demos_v11/v12`).** The fire tick is derivable but the
frame is not there. Measured over all 67 episodes:

| store | episodes | max per-frame fruit-y jump (median) | in seconds of belt travel | fraction with a gap > 0.05 m | gap before the first close | fruit y at the last pre-gap frame |
| --- | --- | --- | --- | --- | --- | --- |
| `ss008` | 25 | 0.137 m | **1.71 s** | 100 % | 100 % | +0.135 m |
| `ss012` | 25 | 0.190 m | **1.58 s** | 100 % | 100 % | +0.188 m |
| `ss015` | 17 | 0.229 m | **1.53 s** | 100 % | 100 % | +0.229 m |

The recorder samples `_record()` calls (`dataset.py:126-136`), and the primitive's
premove/axis/hover/wait loops are not sampled, so **every episode has one 1.5–1.7 s hole ending at
the close**, and the trigger's fire tick (0.9 s lead = 0.072–0.135 m, or 1.5–2.1 s with the ACQ
lead) falls inside it. The label can be *placed in time* (fruit y + v) but there is **no frame at
it and no frame between it and the close** — i.e. no positive example, and no negative example in
the last 0.6–0.8 s before it. A per-frame BCE head trained on this store has no class boundary to
learn. (`ss012` ep0 is the worked example: frames 0–54 hold with the fruit moving 0.12 m/s and
the arm still; frame 60 is already the close, with the fruit 0.208 m further on.)

Also decisive for what the label *means*: `scripts/114_rl_obs_diff.py` §3 records that the
recorder starts when the scripted pick reaches its wait loop, "the arm is already at the
calibrated grasp pose". So the demo's state at the fire is *always* the calibrated pose; the label
teaches "fire when the fruit is 0.13–0.23 m upstream", which is the trigger's rule and nothing
else.

**(b) The rollout store `datasets/rl_rollouts/r9_awr` (56 episodes, 25–92 frames).** The rollout
recorder (`rl_env.py:1954-2008`) records the policy phase and stops when the primitive takes over,
so **the last frame of every episode is the fire state**, in the model's own distribution. The
fruit's last-frame y is +0.19 … +0.31 m — the ACQ lead's geometry. Better still, the fire's
geometry is a recorded per-episode field in `index.json`, verbatim:

```
"intercept trigger (dy=29.7cm, dx=-8.9cm, t_arrive=2.48s, speed=0.120m/s/encoder,
                    frame=station, finger=0.0263, lead=2.48s/reach=0.35)"
```

So the label (the tick), the trigger's own inputs at that tick (`dy`, `t_arrive`, the ACQ `lead`
= 2.48 s, the encoder speed), and the model's finger state are all on disk for 56 episodes. 56
labelled positives with their geometry, free, on the R9 direct interface at 0.12
(shard `direct_none_seed505`).

**(c) A new collection is therefore *not* needed for labels.** It would be needed only if the
label had to carry a *correction* to the trigger's tick (§2.4).

**How the training consumes them — three forms, in cost order:**

| form | what it is | can it move the fire? | cost |
| --- | --- | --- | --- |
| `111 --close-weight/--close-lead` | window upweighting around the *demo's close* (`finetune.py:276-297`) | **no** — the close is the primitive's, 1.5–1.7 s after the fire; a weight cannot relabel a later ramp, and the frames between are the gap | 12 min, no code |
| the P13 event heads (`e078f43`: phase + TtT, aux loss 0.20/0.02 into the shared `condition.proprio`, heads **read-only at inference**) | the stored code is the closest thing that exists | **no, not as built** — the heads are not consulted (`logs/p13/IMPLEMENTATION.md` §2, "the heads are read-only … at inference the heads are simply not run"); and its TtT MAE 0.18 × the 4.0 s horizon = **0.72 s**, against a 0.9 s lead | re-land + the P13 decider (≥4–5 canary runs/side, `logs/p14/A_RESULTS.md`) ≈ 2 h+ |
| a scalar fire head + an env consumer | `direct_fire(..., model_fire=p)` with a per-tick head fed by an 8-step proprio history; plus a parameterised gate width | **yes** | 1.5–2 h of code (the runtime history the P13 note names as unbuilt, `IMPLEMENTATION.md` §2 item (ii)) + 12 min train |

The cheapest *legitimate* form is a fourth one, which reuses everything: **relabel the finger
ramp** in the existing store to the derived fire tick (a data transform), widen the gate by a
default-off env knob (`FRUIT_POLICY_CLOSE_GATE_DIST`, default 0.06), fine-tune, and read the
**fire census**. No new module, no new head, no P13 shadow, and the mechanism endpoint is a count,
not a rate. **Both halves are required and neither is sufficient**: widening the gate alone leaves
the fire at 6 cm (the finger is still late), and relabelling alone leaves it at 0.25 m closed (the
gate blocks). A pre-registration that names only one of them is a null by construction.

### 2.3 The verification, and what N is honest

The census ("which path fired") is a deterministic per-episode read and is resolvable at N=1×15.
The *rate* at 1×15 is not: MDE 46–50 pt (Gate D §2.1a). And the cell wall is worse than the
Gate-D estimate: the trigger-on cells took **15.6–21.4 min** each for 15 episodes
(`logs/p28/95_driver_ab3.log`: 18.5 / 21.4 / 15.6), the trigger-off probe **8.9–9.0 min** each
(`probe_A/B_driver.log`) — a firing model lands on the slow side. So: **the mechanism at 1×15, any
rate claim at ≥3×15 per arm (~2 h)**. Pre-register both, and pre-register that the census is the
primary endpoint — the only one with power at this N.

### 2.4 The falsifier — and why the label's *source* is the design's real flaw

The labels are the trigger's own decisions. A head trained on them has the trigger as its
ceiling: the best possible outcome is "the model reproduces a rule the env computes exactly"
(`t_arrive = max(dy,0)/speed <= lead`, `trigger.py:335-338`). Under `TRIGGER=off` that would
*restore the shipped behaviour*, not exceed it. So:

* **F1 (the clone test, offline, decisive):** derive the trigger's tick for every episode of the
  67-episode store and the 56 rollouts; if the observed fire tick agrees within ±2 control ticks
  in ≥90 % of episodes and the residual does not correlate with the arm's station distance, then
  the label carries no information beyond the goal and a head is a clone. **Kill before the
  fine-tune.**
* **F2 (the headroom test):** the only quantity a model-side fire could add is *its own* setup
  time — the W7-B A/B measured 0.60–0.93 s on successes vs 1.36–7.68 s on the no-contact
  failures, and the probe's `[acq]` rows read setup totals **2.08 / 5.05 / 5.41 s**. If the
  analytic ACQ lead (`lead + 0.60 + |jaw−station|/0.20`, cap 4.5) already predicts those to
  within the catch-up's tolerance, there is no room. **This is the decisive pre-training probe.**
* **F3 (post-training):** the fire moved earlier (census) but the primitive's `res=` did not fall
  → the lead is not the binding term; stop.
* **F4 (structural, must be in the pre-registration):** with the gate left at 6 cm, no training
  can move the fire (§2.1). If the knob is not in the design, the A/B is a null by construction.

### 2.5 Cost, corrected — and the cheaper probe I would run first

| step | the Gate-D estimate | this review's estimate |
| --- | --- | --- |
| collection | 25 min | **0** — `r9_awr` supplies 56 fire-labelled episodes *with the fire's geometry* in `index.json`; the demo stores need only a derivation |
| label derivation | — | 30–45 min (the demo gap makes it analytic; the rollouts are recorded) |
| the interface (gate width / a fire input) | not counted | 1–2 h |
| fine-tune | 12 min | 12 min |
| A/B | "1×15, ~15 min" | **~2 h** at 3×15 (15.6–21.4 min/cell) |
| the P13 canary decider, if the event heads are re-landed | not counted | 2 h+, and it cannot adjudicate anyway (P14-A) |
| **total** | **~1.5 h** | **~4–5 h** |

**The cheaper decisive probe (≈50 min, no training):**

1. **The fire-tick residual audit (offline, ~30 min).** For the 56 rollouts the observed fire's
   `dy`/`t_arrive`/`lead` are in `index.json`; for the 67 demo episodes derive the observed fire
   tick (the gap start) and compute the analytic trigger tick from `goal[1]`, `goal[4]` and
   `fruit_position`. Report the residual distribution and its correlation with `|jaw−station|`
   (the rollouts' `dx` and `lead` give the proxy). It also reports the label-in-gap fraction
   (expected 100 % on the demos) — the data-path falsifier.
2. **The lead-residual arm (simulator, ~20 min, two 0.12 cells).** Run the *trigger-on* line with
   the ACQ lead's 0.20 m/s assumption replaced by the measured setup from the probe's `[acq]`
   rows. Endpoint: the primitive's catch-up residual, per episode. This is the **best achievable
   fire tick**, so it is the head's ceiling: if the oracle lead does not beat the shipped lead,
   no head can.

If both come back at "the analytic rule is already the best lead", the fire-tick-label path is
dead for ~50 min instead of ~5 h — and the finding is still the arc's headline ("the gap is the
setup model, not the firing").

---

## 3. Q3 — the alternatives, ranked (with reasons)

| rank | item | cost | why here |
| --- | --- | --- | --- |
| **1** | **the shippable residue's completion**: `114`'s 26-D path (it is hard-coded to `demos_v7`/`moe_v7`, `scripts/114_rl_obs_diff.py:33-35`, and still prints `same (25-D)`, `:99`) + `logs/p28i/check_speed_channel.py` as a `selfcheck.sh` leg (`grep` finds no reference) | ~1–2 h, offline | It closes two Gate-D items, and it is the only automated proof of the pin chain, the B0 identity and the 25-D inertness — currently a script someone must remember. It also removes the one place where the two observation builders' agreement is *asserted* rather than measured. No simulator, no risk, and it makes the rest of the P28-B work defensible. **Cheapest item with a real risk reduction.** |
| **2** | **D3-proper** (station + self-centring feeder + boundary-respecting descent) | owner-gated, days | The only item that attacks the classes that decide the rate (acquisition/crowding; the W8-B carried class is 6–12 of 15 in every cell). R8-A's bounded proxy failed 1/20, and the descent's 40–90 mm boundary shortfall is a `tasks.py` item with its own pre-registration — so it needs the owner *and* a spec before any run. Highest expected value, highest gate. |
| **3** | **the two-line span work** | sessions | Orthogonal by construction (throughput on an opt-in line). P1c closed the density (single-arm starvation 0/20 → 14/20 empty slots) and P3 closed the place (max safe shift ~30 mm = 0.2 s = 1.3 % of the span against a 4 % bar), and the admitted residual is the descent's boundary shortfall. No policy or autonomy content — it competes with #2 for the same `tasks.py` real estate but pays less. |
| **4** | **the hybrid canary's ≥5-run no-harm** | ~1 h/side | **Last as a gate, not because it is expensive but because it has no power.** The P14-A record: the canary spans 20–80 % across 10 runs at one scenario, and a pooled 5-vs-5 separated at p = 0.0159 between trees whose forward was *byte-identical*. Five per side buys the right to say "no large degradation", nothing more. The lower-variance substitutes (the acceptance stream identity + the 25-D B0 identity) already answer the P28-B question. |
| **5** | **the belt 0.15** | 1–2 h + a scenario change | **Closed by measurement, and it should stay closed.** P27's 2x2 isolation (9/10 · 7/10 · 5/9 · 3/9), the two-line patch 34/60 vs 45/60, and this arc's own collector evidence — the *scripted expert* succeeded on 17/75 = **23 %** at 0.15, so any 0.15 store is a survivor sample of a harder scenario. There is no decision left that more data would change; quoting it as a "screen" would spend the one battery on the worst-prior cell. |

**Where the rank-1 (the fire-tick label) sits:** between #1 and #2 if it is re-scoped to the
50-min analytic probe of §2.5; *below* #2 and #3 if it is the 4–5 h design as written, because its
ceiling is the trigger's own behaviour and the rate it could move is the 16–18/45 interface, not
the carried class (6–12 of 15) that actually decides the rate.

---

## 4. Q4 — the no-harm protocol: satisfied for the diff, with one item to record

### 4.1 The acceptance: the evidence is stronger than the document

`NOHARM.md` reports the count ("7/10 … the same 7/10 the Gate-5's P25 acceptance read") and calls
the tree unchanged by inference. The direct proof is available and unmentioned:

```
$ grep '\[fruit\]' logs/p28/noharm_accept.log      -> 381 lines
$ grep '\[fruit\]' logs/p27/10_acc_012_flip.log    -> 381 lines
$ diff                                             -> 0 lines
```

**381/381, byte-identical**, including every `[motion]` leg row. That is the same standard the
W7-A/W8-B no-harms were held to, and it means: the P28-B code changes nothing on the scripted
line, and the 7/10 is **the same branch** (not a new draw). This should be the sentence of record;
"7/10 = 7/10" is the weaker version of the same claim.

### 4.2 But `accept.sh`'s gate does not pass on this tree — and that predates P28-B

The no-harm ran `scripts/20_pick_place.py` directly (`run_noharm.sh:4-5`), i.e. only the first
half of `accept.sh`. Running the gate by hand on the same log:

```
success: 7/10 = 70% (floor 75% - dynamic line, measured baseline 9/10)
fingerprint: DIFFERS from configs/motion_reference.json - this run landed in a different attractor
  leg 6: this=[89, 0.108] reference=[88, 0.109]
FAIL: 2 problem(s)  - success 7/10 below 75%  - fingerprint differs
```

The motion budgets themselves **pass** (worst descent `|v|max` 0.116 vs 0.161; lurch 0.017 vs
0.291; one carry cone 1.21x reported-not-gated). Two facts follow:

1. the success floor failure is the **P25 B1c flip's** measured cost in the P27 2×2 isolation
   (0.12: 9/10 no-flip → 7/10 flip) — accepted by the owner's mechanism+throughput bar, and not a
   P28-B regression (the P26 three-seed battery, 7/7/6 vs 9/7/4, reads a wash, so the attribution
   is the isolation's, not the battery's);
2. `configs/motion_reference.json` is dated **2026-10-08** (`98105ae`), i.e. pre-P25, so the
   *shipped default cannot pass the repo's own standing gate* — on the flip branch the fingerprint
   must differ. That is a pre-existing tree defect the P28 no-harm surfaced and did not name.
   Before "verified" is used unqualified, one of: re-record the reference from this run (5 min,
   deliberate, with the attractor move recorded), or state in `NOHARM.md` that the scripted no-harm
   is a **stream identity** to the P27 flip record and that `accept.sh` cannot pass by design on
   the P25-flip branch.

### 4.3 The canary: one sample of an instrument that cannot adjudicate — correctly recorded

5/10 is dead centre of the 20–80 % band (`logs/p14/A_RESULTS.md:26-34`), and the same file's
5-vs-5 pool separated at p = 0.0159 *between forward-bit-identical trees*. So:

* a single 5/10 **cannot** adjudicate the tree, and `NOHARM.md` says exactly that — the caveat is
  correct and sufficient;
* a ≥5-run battery is **not required** for the P28-B change, because the change is behind
  `FRUIT_OBS_SPEED=0` and the 25-D forward is byte-identical on real windows
  (`logs/p28i/41_b0_119.txt:14-16`: paired delta median +0.0000 rad, 24/24 ties, max
  0.000e+00). The identity, not the canary, is the gate for a default-off observation change;
* what *is* missing from the policy path is the other half of Gate A §5 item 7: **`spd_v1` has
  never been run through `60_eval_policy` / `accept_policy.sh`** (`grep` over all P28 logs finds no
  evaluator run of the 26-D checkpoint). If the channel is ever enabled, the "the 26-D
  checkpoint can run the interface of record" item is unverified. ~15 min, and it belongs with the
  residue completion (#1 in §3), not with the no-harm.

### 4.4 Q4 answer

**Nothing further is required to call the P28-B *diff* no-harm** — the 381/381 stream identity on
the scripted line and the 24/24-tie 25-D identity on the policy side are both stronger than the
canary, and the canary's 5/10 is recorded with the right caveat. **Two things are required before
the *tree* is called verified**, and neither is a P28 regression: (i) record the reference/
fingerprint state against the P25-flip branch (§4.2); (ii) run the 26-D checkpoint through the
hybrid evaluator at least once, or state that the channel is untested on the interface of record
(§4.3). A ≥5-run canary battery is *not* on that list: it would cost ~5 h and still could not
separate the trees.

---

## 5. Blocking items

**E1 — the rank-1's interface precondition.** The fire cannot move while the gate is
`finger < 0.030 and distance < 0.06` (`rl_env.py:1528`). Any pre-registration for the label path
must name the gate width (or the fire input to `direct_fire`) as a variable, and the pre-registration
must state that the label's source is the trigger — so its ceiling is the trigger. §2.1, §2.4 F4.

**E2 — do not quote "~1.5 h" for the label path.** Label derivation + the interface + a
mechanism-bearing A/B is 4–5 h at the measured cell walls (15.6–21.4 min/15), and the 25-min
collection the estimate assumes is avoidable (`r9_awr`). Run the 50-min residual audit first
(§2.5); it can kill the idea before the fine-tune.

**E3 — the record must carry the probe's three numbers, not two.** 179.92 N (not 122 N, and not
sourced to the probe), 26.70 N, and the clean 5.14 N / 5.9 mm / `success=True` fire. Plus
`spd_v1` 0/15.

**E4 — the acceptance's stream identity and the stale reference.** Add the 381/381 identity to
`NOHARM.md`; record the fingerprint state (§4.2); do not call `accept.sh` passed.

**E5 — the Gate-D items still open, and unmentioned in the close-out.** D3 (placebo + second
training seed, 24 min, offline); the counterfactual on real windows (§1.2 #5); `114`'s 26-D and
the stub as a selfcheck leg (§3 #1); `E_RESULTS.md`'s two surviving false sentences and its
`_stale/` sentence (§1.2 #6).

**Non-blocking, one line each:**

* `E_RESULTS.md`'s correction was prepended, not applied — either edit the body or mark the file
  superseded, because the body is what a reader on a phone reads;
* `CLOSE_OUT.md`'s "the policy never sees the speed" should become "no explicit speed input; one
  noisy witness at `goal[4]`, ~1.1 σ at 0.08 vs 0.12" (§1.2 #1);
* the close-out's residue list should carry the `_MANIFEST_SOURCES` consequence (every run
  manifest changes from here on) because a manifest-hashing gate would break on an unrelated run;
* the probe is a `FRUIT_ACQ_DIAG`-on run but the *trigger-off A/B cells* (`logs/p28e/spd*_n1`)
  still have no `[acq]` rows — the Gate-D "cheapest fix in the arc" is still unfixed for the
  original 90 attempts, and those are the population the 13/90 census came from;
* `run_ab_speed3.sh`'s `exit=1` for every cell is unfixed (`112` exits 1 on a negative verdict) —
  a reader still cannot tell a negative read from a crashed session;
* `probe_A/B` ran `FRUIT_OBS_SPEED=1` for both arms, so "A = moe_v13s 25-D" is the widened net;
  B0 makes it equivalent, but the label is imprecise.

---

## 6. What this review did not check

* Anything in the simulator. Every number is a parse of an on-disk log, one offline re-run of
  `105` (read-only), or a read of the code at `c189f18`.
* Whether the physics behind the probe's 179.92 N contact damaged anything (a force spike on a
  kinematic pad and a soft body — no state is retained by the store).
* The `[acq]` setup-time model beyond the three probe rows: the ACQ formula's coefficient
  (`0.20 m/s`) was not re-derived, only quoted from Gate D / W7-B.
* The r9_awr store's provenance: its `merge_manifest.json` records the four input shards
  (`direct_none_seed5/6/7/909`, 56 episodes, 18 successes) and no checkpoint/env pins; I read the
  56 episodes' shapes and the `index.json` trigger notes, not the R9 pre-registration's env block.
* The P13 event-head diff beyond `logs/p13/IMPLEMENTATION.md` + the two commits: I did not read
  the reverted code line by line, only its documented behaviour (read-only heads, TtT MAE).

---

**Status of this document.** Review only. The three actions I would take, in order:
**(1)** re-run the scripted no-harm's gate by hand and record the stream identity + the reference
state (10 min, offline, E4); **(2)** the residue completion — `114` 26-D + the stub as a selfcheck
leg + the 26-D checkpoint through `60_eval_policy` (~1.5 h, offline + one evaluator run, E5/#1);
**(3)** the 50-min fire-tick residual audit before any label-path spend (E1/E2). The rank-1 next
should not start as designed.
