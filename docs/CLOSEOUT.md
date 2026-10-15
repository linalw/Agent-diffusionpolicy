# CLOSEOUT - the sorting-pipeline-v3 project (R11-C, 2026-10-15)

The one-page close-out of the R0-R11 campaign: the shipped state, the full
measured boundary (every lever family and its verdict), the closed owner
decisions, the named remaining items, and the pointers. Written on branch
`r11-loadpath` (the **R11-B/C** commit): `main`/`origin/main` = `fd2e39e`, tag
**`v0.15`**; this branch is local, not pushed - the R11-C mandate's merge/tag
lands it (`R11 PLAN`, `.slim/deepwork/sorting-pipeline-v3.md`).

## 1. The shipped state (all defaults, this tree)

| piece | default | state |
| --- | --- | --- |
| **Single-arm scripted line** (OpenArm, never-stop dynamic catch, v9/V1 scattered supply) | `FRUIT_DYNAMIC_PICK` unset (catch on the fly) | **9/10 x5 bit-identical, 15.2 s/attempt, 3.55 placed/min**; acceptance 9/10 + motion gate PASS + `fingerprint: matches`; `FRUIT_SUPPLY_SCATTER=0` reproduces the pre-v9 fixed line line-identically (`logs/v1/`) |
| **Bimanual** (`FRUIT_BIARM=1`, shared-station pipeline) | opt-in | 9/10, 15.0 s/attempt, 3.59 placed/min vs single 3.42 = **1.05x** - below the bar, not flipped (`logs/g/`) |
| **Two-line** (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`) | opt-in; **park-gate lever on** (W7-A, `FRUIT_BIARM_PARK_EARLY` default 1 in two-line sessions) | patch: **12/20, 3.63 placed/min** window (timing-only +10 % vs W6-B; residual x1.22 cross-branch); dense W3/W4: 7/10, 9.1 s/attempt, 4.60 placed/min (own reference `configs/motion_reference_twoline.json`); clearance is a **per-config report** (R5) |
| **Policy** | `moe_v12` (hybrid pinned canary = the gate of record; `FRUIT_POLICY_TRIGGER_LATERAL=0.16`) | the direct causal loop is the mechanism interface under the **N=5 protocol**; the hybrid handoff is inert by construction (R5 decision) |
| Measurement rules | - | outcome is quantized (compare per-leg metrics + attractor, never cross-config rates); diagnostics default off; Tier A solo; `scripts/selfcheck.sh` / `accept.sh` / `accept_policy.sh` / `demo_2min.sh` |

## 2. The measured boundary (every lever family + verdict)

| family | verdict | the number / mechanism |
| --- | --- | --- |
| Squeeze side (force/depth/relief) | **closed by measurement** | drives force-saturated 4.1-4.5 N; `FRUIT_CARRY_RELIEF` to 0.5 mm interference leaves the force unchanged (R6-B) |
| Shape/geometry (grip plane / cradle-scoop / raised station) | **closed** - all FAIL | R8-A: escapes persist, the (b) halving redistributes into the worse band; scope bats the payload; platform obstructs the supply - bounded grip-geometry space measured closed, no R8-B (`logs/r8/A_RESULTS.md`) |
| Reaction-side guards (slip guard + re-seat) | **not adopted** | W8-B p = 0.1094; R6-B retuned p = 0.3125; the one-sided contact signal buys 0-2 ticks - no reaction window (`logs/w8/B_RESULTS.md`, `logs/r6/B_RESULTS.md`) |
| Recollections (BC) - `moe_v13p` | **not adopted** | W8-A N=5: 21/75 vs 22/75, paired 0-2, **p = 1.0000** - the N=3 3-0 was noise |
| RL/DAgger (AWR-clipped RWR-2) | **negative, published** | R9: A 25/75 = 33 % vs B 18/75 = 24 %, paired carried 5-4, **p = 0.500**; the carry window is branch-invariant, the handover degraded (`logs/r9/RESULTS.md`) |
| Reach-anywhere catch | **not adopted** (owner exception named) | R10-A/A.1: coverage +62 %, span -8 %, but carry 5/20 and success 40 % vs 72 %; R11-A: the candidate replays arm B **685/685 bit-identical** yet the shipped acceptance collapses 9/10 -> 4/10; R11-A.1 floored variant 4/9 (all left) - the default stays 0/0 (`logs/r11/A_RESULTS.md`, `A1_RESULTS.md`) |
| Speed/throughput (L2 lead / L3 hot-arm / L4 / belt) | **no lever adopted; the park-gate lever is the one win** | R3: adaptive lead bit-identical (the 1.5 s floor *is* the setup), tight probe worse (8/20), hot-arm fires 4/18 flat-to-worse, L4 not run; **W6-C/W7-A parked gate**: interval 22.20 -> 16.53 s, left gate-blocked idle 25.2 -> 0.2 s, window 2.70 -> 3.63 placed/min (timing-only +10 %; cross-branch) |
| Pre-onset load path (`FRUIT_CLOSE_LOAD_RATE` / `_CONTACT_LEAD` / `_PLUCK_DWELL`) | **not adopted** (R11-B, this close-out) | the M screen's strongest candidate (freeze row 18.0 -> 55.5, face speed 188.7 -> 39.9 mm/s) reads **12/20 = 60 % vs the control 13/18 = 72 %** on stage P (cnp 3 = 5-2 exactly at the bar; never-grasped 0 -> 5); stage N stopped incomplete (A run 1 = 6/15); the payload is held to 0.5 mm through the pre-onset window - **the pre-onset load path is not the discriminator; the escape is a mid-lift one-sided loaded slide** (`logs/r11/B_RESULTS.md`) |
| Interface (policy-gate bypass / ACQ / trigger) | **R7-A closed, not shipped; ACQ not shipped** | the x-edge refusal binds both fire paths (0 out-of-band fires / 0 bypasses on the forced band); `FRUIT_POLICY_TRIGGER_ACQ` stays default off (a measurement interface); trigger lateral 0.16 shipped (W4) |
| Instrumentation (carry metric) | **delivered** | `clean_slip` separates clean (0.02-1.43 mm) from escapes (17.9-957 mm), no overlap; the legacy `[motion] carry slip_max` must not be quoted for the OpenArm hand (frame-contaminated) |

## 3. Owner decisions closed

* **R5 (2026-10-13)**: two-line flip **no** (1.25x bar unchanged); clearance =
per-config report (no gate; no arm-arm contact possible); C-semantics
two-line-only; ACQ **not shipped**; **hybrid pinned canary = the gate of
record** (direct loop = mechanism interface).
* **W7-A (owner, 2026-10-12)**: the park-gate lever is the two-line default.
* **R7-C/R8-A**: the D screen go -> **all three candidates FAIL**, no R8-B;
fallback (direction B) pre-registered; **R9**: executed, negative, no
adoption.
* **R11-A/A.1**: the reach adoption attempted; its own gate's
acceptance-floor item failed twice (4/10, 4/9); default unchanged; the
**owner exception on the documented numbers** is the only shipping path.
* **R11-B/C (this close-out)**: the load-path lane executed; stage-P not
positive; stage-N stopped incomplete; **not adopted**; the phase's mechanism
conclusion and the unconfirmed C1 candidate are recorded.

## 4. Named remaining items (no blocked rows)

1. **The reach performance, via the owner exception** - the documented
   numbers with one line + the acceptance + the reference re-record
   (`logs/r11/A1_RESULTS.md`; no default change otherwise).
2. **The C1 direct confirmation** (optional): the N=5 direct A/B re-run for
   `FRUIT_CLOSE_LOAD_RATE=0.04` (~4 h Tier A solo; one A run exists at 6/15) -
   the stage-P trade makes it a weak candidate (`logs/r11/B_RESULTS.md` sec. 9).
3. **The sim-to-real contact screen** (WS-7.1's first bounded step): the
   offline image ablation + the seeded contact-parameter screen (finger
   drive force limit, pad mu, contact stiffness/damping, fruit friction,
   belt mu), then a calibrated/randomized pass; the real-cell target does not
   exist, so the ceiling is a hardened sim.
4. **The primitive/aim redesign**: the R11-A.1 post-catch hold class and the
   aim-vs-choice sub-lever discriminators (`logs/r11/A1_RESULTS.md`); the
   station/feeder/descent rework **D3-proper** stays owner-gated
   (`logs/r8/A_RESULTS.md`).

## 5. Pointers

`README.md` (entry) - `项目总结报告.md` (Chinese report) - `决策与交付.md`
(route trade-offs) - `实现方案总结.md` - `WORKLOG.md` (append-only evidence;
"R11-A"/"R11-A.1"/**"R11-B"/"R11-B.1"**) - `docs/ROADMAP.md` (the plan +
register) - `docs/OPS.md` + `scripts/191_ops_selfcheck.sh` (ops) -
`logs/r11/B_RESULTS.md` (**the R11-B verdict**) - `logs/r11/A_RESULTS.md` /
`A1_RESULTS.md` (the reach adoption) - `logs/w8/B_RESULTS.md`,
`logs/w6/BASELINE.md`, `logs/r5/RESULTS.md`, `logs/r9/RESULTS.md`,
`logs/r6/B_RESULTS.md`, `logs/r8/A_RESULTS.md` (the lever-family evidence).

*One page, dense by design; every number carries its log pointer in the
documents above.*
