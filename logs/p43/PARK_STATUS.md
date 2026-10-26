# P43 phase 1 — PARK_STATUS: what the arm park's evidence is, what it is not, and what a re-measurement has to hold

Written **offline** 2026-10-26 (no simulator, no `src/` edit, no commit). Tree
HEAD **`53e5ccf`**, `rl_env.py` **`50980bf5`**, `tasks.py` **`e2d0f12a`**,
`control.py` **`9384ff4f`** (the P41 `finger_damp02` profile), `scene.py`
`27e3d64a`; `configs/motion_reference.json` **`8a399626`**,
`configs/arm_parks.json` **`42ab4fb7`**.

**One sentence.** The park is a **measured interface lever on the direct
presentation** (right-arm carried-not-placed **25 → 0**, right placed **45 % →
94 %**, run-level **5/5**, exact pairs **8-0**), its win travels down the
**image** channel (P36 2x2: image p = 8.8e-15, proprio p = 0.687) — and **every
one of those numbers was measured with the pre-P41 grip (4.4 N) on a tree that
no longer exists**, so it must be re-measured before it can be a default.

---

## 1. The measured record

### 1.1 P35 phase 2 — the A/B (`logs/p35/C_RESULTS.md`, the record of record)

Batch `logs/p35/C_ab/`, 12:59-14:10 (71 min), one claim, **N = 5 runs x 15
episodes per arm**, seeds 77/101/202/303/404, policy seed 11, interleaved A,B,
the P33/W8-A scenario verbatim (`FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival
FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_TRIGGER_ACQ=1`,
camera 240x424). **A = the shipped env, B = `FRUIT_ARM_PARK=back`.**
Checkpoint **`moe_v13s` `61da390a`** on **both** arms.

| endpoint | A (shipped) | B (park) |
| --- | --- | --- |
| **right** (the lever's population) | 23/51 = **45 %**, carried **25**, no-grasp 3 | 47/50 = **94 %**, carried **0**, no-grasp 3 |
| right composite (carried + no-grasp) | 28 | **3** |
| pooled | 24/75 = **32 %** | 49/75 = **65 %** |
| **left** (the no-op guard: the left has no park vector) | 1/24 = 4 %, carried 23 | 2/25 = 8 %, carried 23 |
| median cycle | 1 867 ticks | 1 802 ticks (-3.5 %, **different outcome mixes** — a report) |
| standardised right | 52.3 % class / 45.2 % size | **94.9 % class / 94.1 % size** |
| run level | — | **B > A in 5/5 runs**, one-sided sign p = 0.031 |
| exact-instance pairs | — | 22 usable, **8 B-only / 0 A-only** (p = 0.0039); carried-class **7-0** (bar ≥ 5 / ≤ 1, **met**) |
| new failure reasons | — | **none** |

**The instrument check (the gate of record).** M1 (the pose held vs the pose the
reset *achieved*): **50/50**, median 0.004 rad. M2a (the arm term at the band's
worst call, `max_frac < 0.10`): **50/50** (control **0/51**). The band census:
fully-hidden target calls **856/1257 = 68.1 % → 0/1236 = 0 %**, any inactive-arm
pixel inside the fruit's projected-disc bbox **100 % → 0 %**. M2b
(episode-relative `rel >= 0.85`) is a **recorded report at 36/50 = 72 %**, not a
gate, and its misses are the running-max normalisation and 22-47 px raster
drift, **not** an occluder.

**Two recorded caveats that a re-measurement must not lose:**

* the **achieved-vs-commanded** pose residual for `back` is **0.088 rad** (the
  shipped `ready` reset is 0.037 from *its* command) — a `teleport_joints`
  settle property. P35's `PREREG.md` §5 literal block ("> 0.02 rad") is
  **failed** by it and would fail the shipped `ready` too, so the adoption gate
  must be written against the **achieved** pose (M1-held-applied), never the
  command;
* the exact-instance pairing is **conditioned on a post-treatment variable**
  (which slots happen to present the same fruit): 22 of 75 slots pair. The
  **design-valid leg is the run level (5/5) plus the standardised counts**.

### 1.2 P37 phase 2 — the recollection (`logs/p37/B_ab/B_report.txt`)

A different question (does a checkpoint fine-tuned on park-collected rollouts
*preserve* the win), same protocol shape: N = 5 x 15 per arm, seeds
77/101/202/303/404, policy seed 11, **both arms parked**, A = `moe_v13s`
`61da390a`, B = `p37_park` `3fa45c96`; 00:07:05 → 01:19:41 (**72.6 min**), 10
sessions.

| endpoint | A (`moe_v13s`) | B (`p37_park`) |
| --- | --- | --- |
| **right placed** (primary) | **43/44 = 0.977** | **47/49 = 0.959** (delta **-0.018**, margin -0.10 → PASS) |
| right carried | **0** | **0** |
| left (no-op) | 1/31 | 1/26 |
| S2 standardised | 0.977 | 0.961 species / 0.956 diameter |
| S4 cycle | 1 840 ticks | 1 826 (-0.8 %) |
| S3 new reasons | — | **FAIL**: 1 `timeout: no grasp within 1500 ticks` (kiwi at **x = +0.159**, below the trigger's 0.16 admission floor ⇒ x ≥ 0.173) |
| H2 manipulation | 44/44 | 49/49 (**100 % on every term**) |

**Read:** the park's win is **preserved** and a park-trained checkpoint **adds
nothing** — the base already sits at ~0.98 of its ceiling with the park on. The
S3 fail is a **scenario tail** (~1 %/episode, P38: 2/3103 = 0.06 % on the shipped
gate), not a candidate behaviour, and **widening the gate is not the fix**
(reach residual 8.3 mm at x = 0.16).

### 1.3 The mediator — P36's 2x2 (`logs/p36/A_RESULTS.md`)

4 cells x 3 runs x 15 = **180 episodes**, one claim, 5 146 s (85.8 min), cell
order randomised, checkpoint `moe_v13s` `61da390a`, all four diagnostics on.

| cell | the inactive arm / the obs | right ok / carried / no-grasp | carried rate |
| --- | --- | --- | --- |
| 1 control | `ready` / live `ready` | 7 / **18** / 2 (27) | **0.667** |
| 2 the lever | `back` / live `back` | 29 / **0** / 1 (30) | **0.000** |
| 3 image-only probe | `back` / written `ready` | 26 / **0** / 2 (28) | **0.000** |
| 4 proprio-only probe | `ready` / written `back` | 13 / **17** / 0 (30) | 0.567 |

**image** main effect: `{2,3}` **0/58** vs `{1,4}` **35/57**, **p = 8.8e-15**.
**proprio**: `{2,4}` 17/60 vs `{1,3}` 18/55, **p = 0.687** (effect -0.050).
Interaction +0.100, permutation p = 0.581 — the pre-registered **descriptor
only** ("adds nothing measurable under the ceiling").

**Honest scope of the mediator claim:** the image *channel* carries it; **which
image statistic** is **not separated** (the fruit's **sightline** — the P35
occlusion census — is the leading but unseparated candidate, because the probe
moves the parked silhouette as well as the fruit's pixels). And the proprio null
is **weak evidence**: cell 4 writes a `j2 = -0.978 rad` value that is outside
both reference stores' observed ranges, **and** the effect (-0.050) is smaller
than the batch's own **left-arm no-op** proprio contrast **(-0.119)**, with a
cell spread of 0.156. So: "no proprio contribution is measurable at this n", not
"the proprio is proven irrelevant".

### 1.4 The scope, in code (`rl_env.py:973-1009`, applied at `:1753`)

```python
# --- P35 phase 1: the inactive arm's park, default off --------------- #
self._arm_park = os.environ.get("FRUIT_ARM_PARK", "").strip()
if self._arm_park and self._arm_park != "ready":
    if presentation != "direct":
        raise ValueError("FRUIT_ARM_PARK is only defined for presentation='direct' ...")
```

* **direct presentation only, and the shipped canary has no code path for it.**
  `SortingRLEnv.__init__` raises unless `presentation == "direct"`
  (`rl_env.py:987`), and the shipped hybrid canary
  (`scripts/60_eval_policy.py`) does **not** construct `SortingRLEnv` at all —
  it runs the harness's own handoff loop and imports only `PolicyRunner` /
  `PickAndPlaceTask` / `GraspPrimitive`. So `FRUIT_ARM_PARK` is read by
  `110_rl_rollout`/`112_rl_ab.sh` and by nothing else: **"make the park the
  default" means the direct environment's default** (the measurement interface),
  not a shipped product change.
* **inactive arm only**, and only the **left** arm has vectors
  (`configs/arm_parks.json`: `back` and `side_deep`, both left-only; the right
  arm's `back` "does not hold (0.17 rad) and puts the fingertip in the belt
  footprint"). So the lever's population is the **right-arm episodes**, and the
  left-arm episodes are the built-in **no-op negative control**.
* Unset or `=ready` is byte-inert: no file read, one dict lookup per arm.
* A park-on rollout is **recordable** (P37 collected 90 episodes under it) and
  the manifest records `arm_park` (`rl_env.py:1490`), so a post-park store is
  identifiable. (The *spoof* knobs are refused for recording; the park is not.)

---

## 2. The caveat that decides the phase

**Every number in §1 was measured at a delivered pinch of 4.38-4.42 N.** The
tree now ships **`finger_damp02` (k = 1e5 N/m, c = 2000 Ns/m, c/k = 0.02)** and
delivers **9.75-9.9 N — 2.2x** — at **1.00-1.01x wall** (`logs/p41/P3_RESULTS.md`,
`logs/p41/P2_RESULTS.md` §2). The P41/P42 force record — the class persisting at
2.2x and 6x force, at every face, every depth, with the seat centred to 1.4-4.6 mm
(`logs/p42/SIM_LIMIT.md`) — is a **scripted-scope** measurement: the direct
interface has **never** been run under the 9.9 N profile. So the **prediction**
is that the park's win survives (the mechanism is the image, and the class it
converts is the loaded slide W8-B measured on the direct interface too), but a
prediction is not a measurement, and the direct interface's **pre-park** baseline
(P36 cell 1: carried **0.667**) is a 4.4 N number that nobody has re-read.

Why it can move: the park's measured magnitude is a contrast between two arms
whose *carried* rate is the endpoint. If 9.8 N halves the pre-park carried rate
(say 0.667 → 0.35-0.5), the park's **headroom shrinks** and its absolute win
changes even though the mechanism (the image) is unaffected. A re-measurement
must therefore re-read **both arms**, not just the park's.

### 2.1 What the re-measurement must hold fixed

| axis | value | why |
| --- | --- | --- |
| **checkpoint** | **`moe_v13s` `61da390a`** (both arms) | the entire park corpus (P35/P36/P37) is on it; changing it re-opens the checkpoint axis and makes the result incomparable to any park number. The shipped canary's default `moe_v12` (`3a9ccfc0`) is **not** the right control here: the canary (`60_eval_policy.py`) does not construct `SortingRLEnv` and so has **no park code path at all**, which makes a `moe_v12` park arm a configuration that cannot be deployed anywhere. |
| **scenario** | the P35/P36/P37 block verbatim (patch sheet, balanced A:B:C, trigger arrival + lead 0.9 + `ACQ=1`, `FRUIT_DYNAMIC_PICK=1`, camera 240x424) | a different supply is a different scenario (`AGENTS.md` §2), and the park numbers are per-scenario |
| **arms** | **A = shipped (no park), B = `FRUIT_ARM_PARK=back`** | **the contrast is the park**, which is P35's design, not P37's. P37's "both arms parked" belongs to *its* variable (the checkpoint) and would be the wrong contrast here. |
| **protocol shape** | N = **5 runs x 15 episodes per arm**, seeds **77/101/202/303/404**, policy seed **11**, interleaved, **one claim** | the WS-4.2 convention and the P37 batch shape; the direct loop is **not** reproducible (rendered frames), so a single run is one sample |
| **diagnostics** | `FRUIT_ACQ_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_PARK_DIAG=1` on **both** arms | instrumentation is part of the measurement (`AGENTS.md` §3b) and the P35 manipulation check is built from those rows |
| **the check** | P35's M1-held/applied (vs the **achieved** pose) + M2a + the band census, per arm, **before** any outcome read | without it the outcome is not attributable to the sightline |
| **references** | `configs/motion_reference*.json` and every scripted default **unchanged** | the park is direct-only; the scripted lines must replay byte-identically (no-harm) |

### 2.2 The wall, measured rather than assumed

| quantity | measured | source |
| --- | --- | --- |
| per-episode direct wall | **27.7 s** mean (396-437 s per 15-episode run) | `logs/p37/B_ab/*.log` `run wall end … duration=` (10 runs) |
| per-episode direct wall (preceding batch) | **27.2 s** (408.1 s per run) | `logs/p35/C_ab/*.log` (10 runs) |
| a full N = 5x15 two-arm batch | **71-73 min** of episode wall (P35 71 min, P37 72.6 min) | those batches' own clocks |
| this phase's batch | **150 episodes x 27.7 s ≈ 69 min + 10 app startups** | derived |

So the honest figure is **~1.2-1.4 h of machine time for the batch**, and the
**2-3 h envelope** covers the batch, the scripted no-harm acceptance
(`accept.sh`, ~5 min + the gate), `selfcheck.sh`, and **one re-run** if a
session wedges (P35 and P37 recorded none; a contact-grind wedge is a known
failure of this interface, so one re-run is budgeted). **Do not quote 3 h as the
measured cost** — it is the budget.

---

## 3. The decision rule (what makes it a default, and what leaves it opt-in)

**Scope of the word "default".** The park can only be the **direct env's**
default. Flipping it **re-baselines the direct interface**: every quoted direct
number (P33, W7-C, W8-A, R9, P35, P36, P37, P38) becomes a **pre-park** number
and a new direct run is not comparable to them without saying so. That cost is
part of the decision, not a footnote.

**Adopt (default on for `presentation="direct"`, `FRUIT_ARM_PARK=ready` restores
the shipped pose) iff *all* of:**

1. **the check passes** — M1-held and M1-applied **100 %** per arm against the
   **achieved** pose, M2a **100 %**, and the band census reads **0 fully-hidden
   calls** in the park arm (the P35 instrument, unchanged);
2. **the class contrast is evaluable and significant** — the exact two-sided
   Fisher **p ≤ 0.05** on the pooled right-arm carried 2x2, **with the observed
   contrast reported**. At n ≈ 50/arm that implies a contrast of **≈ 0.20-0.22**
   (computed: from A = 0.66 the last significant cell is B = 0.40, i.e.
   −0.26; from A = 0.44, B = 0.20 → p = 0.018), so **a minimum-effect sentence
   is not needed — the n itself is the floor**;
3. **the baseline decides the branch** — **P0: A's right-arm carried rate**. If it
   is **≥ 0.40**, the class contrast is evaluable (branch **A**). Below 0.40 a
   halving is no longer detectable at this n (A = 0.40, B = 0.20 → p = 0.049 is
   the last resolvable point), so the class contrast is demoted to a **report**
   and the decision takes branch **B** below;
4. **right-arm placed is non-inferior** — **delta ≥ −0.10** (the P37 margin; at
   n ≈ 50 even exact equality has a ~−0.10 one-sided 95 % lower bound, so a
   tighter margin is not resolvable) **and** the standardised (species +
   diameter tertile) deltas agree in sign;
5. **the pooled placed rate gains** — **≥ +0.10 absolute** (P35 read +0.33);
6. **no new failure reason** in either arm (`113`'s number normalisation), and
   the left-arm guard does not regress by more than **0.05**;
7. **the cycle is not worse by more than 5 %** (P37's S4 bar);
8. **the run level agrees** — B ≥ A in **≥ 4/5** runs on the primary.

**Branch B (the class endpoint not evaluable, i.e. A < 0.40):** adopt only on
**check ∧ placed-non-inferiority ∧ pooled ≥ +0.10 ∧ run-level ∧ no-new-reason**,
with the carried contrast in the favourable direction, and **label the adoption
"no class-level evidence at this n; the pooled/placed read carries it."** This is
the weaker branch and the document must say so.

**Stay opt-in iff any of:** the class contrast is not significant (in branch A),
or placed regresses beyond the margin, or the pooled gain is below +0.10, or a
new reason appears, or the check fails (then the outcome is not attributable and
no claim is made), or the run level disagrees with the pooled read.

**Either way, record:** the pre-P41 park corpus is a 4.4 N corpus; the shipped
grip is 9.9 N; and a default flip breaks direct-baseline comparability. If the
win **does not** reproduce, the park stays a **documented opt-in** — it is still
the right configuration to *measure* the right arm in (the P35 mechanism is
image-borne and the occlusion census is a fact), but it may not be quoted as a
rate lever on this tree.

**What would make a `moe_v12` (or any shipped-canary) arm worth it:** nothing in
this phase — the canary (`60_eval_policy.py`) does not construct `SortingRLEnv`,
so `FRUIT_ARM_PARK` has no code path there and the park's deployment question is
confined to the direct interface. A `moe_v12` **direct** arm is a **separate**
question (does the park win transfer to the shipped checkpoint's weights?) and is
**not** registered here; if it is ever wanted it is one extra 36 min arm at
N = 5 x 15.

---

## 4. What this document refuses

* **No re-opening of the grip/seat class** (`logs/p42/SIM_LIMIT.md` stands). The
  park is not a grip lever; it is an occlusion/interface lever, and its endpoint
  is the carried class only because that is how this interface fails.
* **No "the park is the mechanism" claim.** The channel is measured (image); the
  statistic inside the image is not, and the control's invisible-fruit successes
  (9 of its 23 right-arm successes read `px = 0` at every band call) argue
  against a simple perception bottleneck.
* **No shipped-default change from this document.** Phase 3 owns the flip, and
  only after the numbers above.
