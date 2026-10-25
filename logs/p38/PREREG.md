# P38 phase 2 — PRE-REGISTRATION: the harness's refusal attribution + bounded re-selection

Written 2026-10-25 **before** any code change and before any phase-2 run.
Phase 1's measurement record is `P1_RESULTS.md` (same directory); the lane is
`.slim/deepwork/p38-drift-tail.md`.

> **AMENDED by `PREREG_A1.md`** (same directory, 2026-10-25, still before any
> code change or run): the Gate-1 conditions H1/H2/H3 plus the M1-M4 items.
> Where the two disagree, `PREREG_A1.md` governs — the "provable refusal"
> (§2), Fb/Fc (§5), the M1/M2 bands and predictions (§3), P4/P6 (§4), P5's
> symmetric note-level form, the episode budget (§8: 135, not 90) and the
> exposure arithmetic (§7).

Tree pins at registration (HEAD `dd53d15`, unchanged by phase 1): `rl_env.py`
`aa54b022`, `policy/trigger.py` `d7ec85fc`, `tasks.py` `cdde6bd2`,
`fruits.py` `6f65e423`, `conveyor.py` `b0d95a08`, `assets.py` `61baf52b`,
`configs/motion_reference.json` `25ade92b`, `configs/waypoints.json` (see
`logs/p38/MD5.txt`).

## 1. The question

Phase 1 measured the S3 class (a direct episode that ends
`timeout: no grasp within 1500 ticks` with no `[acq]` row) at **2 / 3103 =
0.06 %** on the shipped interface, and showed the class is the trigger's
**lateral** admission (right arm `x >= 0.1730`, left `x >= 0.1800`) meeting the
delivered-x tail, with the harness holding the candidate fixed for the whole
episode and refusing it **silently** (`trigger.py` `should_fire`:
`if abs(dx) > settings.lateral: return False, info`, no marker;
`rl_env.py:2668-2674`: the horizon is the only exit).

At 0.06 %/episode a WS-4.2 arm of 75 episodes expects **0.05** events, so **no
A/B at the project's N can measure this class**. Phase 2 therefore asks a
different, answerable question:

> **Q.** Can the direct harness (i) *attribute* every never-fired episode to
> its mechanism and (ii) convert a laterally-refused candidate into an attempt
> by re-selecting inside the same grade lane — without changing the shipped
> scene, the scripted lines, or the shipped-scenario rate?

## 2. The levers (all default off, direct-path only, byte-inert unset)

Four env knobs, resolved once in the env's constructor and read only inside
`presentation == "direct"` branches:

| knob | default | what it does |
| --- | --- | --- |
| `FRUIT_POLICY_REFUSE_DIAG` | `0` | one note per refused fruit: `lateral refuse: fruit x=... beyond the lateral gate (station ..., lateral ...)`. **Run-neutral** (a print); ON in *every* arm of every phase-2 batch. |
| `FRUIT_POLICY_REFUSE_END` | `0` | at a *provable* refusal, end the episode with `no firable fruit: candidate x=... beyond the lateral gate (x >= ... admitted)` and set `outcome="no_firable"`, instead of burning the horizon. |
| `FRUIT_POLICY_RESEED` | `0` | at a *provable* refusal, re-select inside the same grade lane (below); implies the diag. |
| `FRUIT_POLICY_RESEED_MAX` | `2` | the re-selection budget per episode (0 = off). |

**The provable refusal.** In `should_fire`, the lateral check moves to the same
"last check" position the reach-cliff guard uses: `info["lateral_refuse"] = dx`
is set only when **`|dx| > lateral` and every other gate passes**
(`dy <= reach_eff`, `dy >= -0.05`, `speed > 1e-3`, `t_arrive <= lead`). The
return value stays `False` in every case, so the *shipped* behaviour is
byte-identical with the knob off; `x` is fixed after the settle
(`P1_RESULTS.md` §2), so "provable" means "will never fire on this pass".

**The re-selection** (bounded, same lane, direct only). On the first provable
refusal, and only while `not self._triggered`:

1. `state = task.select_target(spawner.state(), reach_anywhere=False,
   lane=self._bin_index, exclude=seen)` — the direct interface's pinned
   selector (R11-A scope), restricted to the episode's grade lane so the arm
   and bin stay valid; `seen` accumulates the refused indices.
2. The returned candidate is accepted only if it **also passes the lateral gate
   at the adoption tick** (`|x - station_x| <= lateral`); otherwise it is added
   to `seen` and the loop repeats, up to **4** candidate scans.
3. On acceptance: `spawner.unprotect(old.index)`, adopt the sample, rebuild
   `_goal` (position, velocity, diameter, `bin_index`) and `_belt_rest` exactly
   as the reset does, `spawner.protect(new.index)`, `_reseed_left -= 1`, and
   log `reseed: adopted index N (class) after a lateral refusal at x=...`.
4. If nothing is accepted (or the budget is spent) and `FRUIT_POLICY_REFUSE_END`
   is on, end with the explicit class; else continue as today (the timeout).

**What does not change.** `select_target`'s rules, `_dynamic_select_floor()`,
`trigger.lateral`, the 1500-tick horizon, the reward, the supplies, the scene,
`configs/*`, the scripted/collector/two-line/handoff paths. The phase-2 diff is
confined to `policy/trigger.py` (the `info` key) and `rl_env.py` (the four
knobs, the note, the reseed loop, the terminal class).

## 3. The arms and the scenarios

Arms: **A** = the control (diag only). **B** = diag + `REFUSE_END`. **C** =
diag + `RESEED` (+ `REFUSE_END` as its fallback). A and C always run in the
same batch; B runs in the mechanism batches only.

Every run: `HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_NO_ATTACH=1
FRUIT_NO_SLEEP=1 FRUIT_SIZE_FILTER= FRUIT_SUPPLY_SCATTER=1
FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9
FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_DYNAMIC_PICK=1 FRUIT_RESET_ALIGN_DIAG=1`
(the P36/P37 scenario verbatim), plus `FRUIT_POLICY_SEED=11`, checkpoint
`checkpoints/moe_v13s/policy_best.pt`, `--episodes 15`, and
`FRUIT_ARM_PARK` **unset** (the shipped deployment).

### M1 — the forced band (100 % refused; the attribution and the bound)

`FRUIT_SUPPLY_X_MIN=0.10 FRUIT_SUPPLY_X_MAX=0.17`, `SEED=5`, `--seeds 5`,
15 episodes per arm, arms A / B / C.

*Every* candidate is below both admission floors by construction, so no arm can
fire. Predictions:

| arm | expected |
| --- | --- |
| A | 15/15 `timeout: no grasp within 1500 ticks`, ticks = 1500, 0 attributed notes |
| B | 15/15 `no firable fruit`, median ticks **<= 500** (the refusal is detectable at dy ~ 0.30 m ~ tick 300) |
| C | 15/15 `no firable fruit` after **2** adopted-but-unfirable candidates per episode (the budget), i.e. the re-selection is bounded and cannot loop |

### M2 — the mixed band (28 % refused; the conversion)

`FRUIT_SUPPLY_X_MIN=0.10 FRUIT_SUPPLY_X_MAX=0.36`, `SEED=5`, `--seeds 5, 101,
202` (three runs), 15 episodes per arm, arms A / C.

28 % of the draws are below 0.173 (`(0.173-0.10)/0.26`), i.e. ~4 of 15 per
run. Predictions: A's refused episodes end at 1500 ticks (unattributed unless
the diag names them); C's refused episodes adopt a firable candidate and
**fire** (`intercept trigger` or a policy close), then reach whatever outcome
the grasp gives.

### M3 — the shipped patch band (the safety endpoint, the same-batch control)

`FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25` (the P37
scenario), `--seeds 77, 101, 202, 303, 404` (five runs, one supply seed each),
15 episodes per run, arms A and C interleaved **A then C** in one claim.

### M4 — the scripted no-harm

`scripts/accept.sh` twice (knobs unset, then all four set) and
`scripts/selfcheck.sh` once. The knobs are direct-only, so the requirement is
**byte-identity** of the `[fruit]` stream plus `fingerprint: matches`.

## 4. The endpoints (all pre-registered, no retro-fitting)

| # | endpoint | population | pass rule |
| --- | --- | --- | --- |
| **P1** | *attribution*: the refused episodes that carry a named mechanism | M1 | A 0/15 vs **B 15/15** and **C 15/15** (deterministic; no statistics needed) |
| **P2** | *conversion*: the refused episodes that fire | M2 | A 0 of its refused episodes vs **C >= 10 of 12** (exact McNemar on the paired episodes, one-sided p <= 0.01; if the batch yields fewer than 10 refused episodes the endpoint is *reported as underpowered* and repeated once) |
| **P3** | *the terminal class replaces the timeout*: the number of `timeout: no grasp within 1500 ticks` episodes | M1 + M2 | **0** in B and C; the class name is `no firable fruit` (a *named* failure, not a pass) |
| **P4** | *safety*: right-arm placed, C - A | M3 | delta > **-0.10** (the P35/P36/P37 margin), same-batch control, seeds fixed; **the refusal exposure is reported per arm**; with 0 exposure the endpoint is a safety check, not a power test |
| **P5** | *no new reason*: the failure-reason sets of A and C | M3 | equal after mapping every `lateral refuse:` / `no firable fruit:` note to the class `lateral-refuse`; any other new reason fails |
| **P6** | *cycle*: the median cycle over **fired** attempts, C vs A | M3 | <= **+5 %**; the `no firable fruit` episodes are excluded from this median and reported separately (they are not attempts) |
| **P7** | *scripted no-harm* | M4 | the `[fruit]` stream byte-identical to the knob-off run, `fingerprint: matches`, `selfcheck.sh` PASS |

## 5. The falsifiers

* **Fa** — on M1 the diag note never appears (the predicate is dead): the phase
  **fails**; do not run M2/M3 on it.
* **Fb** — on M1 arm C fires (it must not: there is nothing firable in the
  band): the re-selection ignores the lateral gate or the admission arithmetic
  is wrong → the phase **fails**.
* **Fc** — on M2 arm A fires on a candidate whose delivered x is below 0.173
  (the diag note and the fire on the same episode): the admission arithmetic is
  wrong → re-derive `P1_RESULTS.md` §3 before any lever claim, and the phase
  **stops**.
* **Fd** — on M3 the right-arm delta <= -0.10, **or** a new non-attribution
  reason appears, **or** the scripted stream moves: **not adopted**; C is
  rejected and B is the fallback candidate for phase 3.
* **Fe** — on M2 C's converted episodes reach `carried-not-placed` (grasped
  but not placed) more often than A's overall carried rate: the re-selection
  trades a no-fire for a grip failure (the P37 §4.5 warning) → **not adopted**;
  B only.
* **Ff** — the reseed loop adopts a candidate of the *other* grade lane (the
  arm/bin would be invalid): the implementation is wrong → the phase **fails**.

## 6. The decision rule

Report a **recommendation only**; no shipped default changes in phase 2.

```
adopt-recommended  iff  P1 and P2 and P3 and P4 and P5 and P6 and P7
                        and none of Fa..Ff fired
B-only-recommended iff  P1 and P3 and P7 hold and (P2 fails or Fe fires)
not-adopted        iff  P4 or P5 or P6 or P7 fails, or Fa/Fb/Fc/Ff fire
```

`adopt-recommended` means phase 3 may flip `FRUIT_POLICY_RESEED` /
`FRUIT_POLICY_REFUSE_END` on (the owner's sign-off, the AGENTS "shipped default
change" rule), and it must then re-record nothing (the knobs are direct-only
and the scene is untouched) but must re-run `accept.sh` + `accept_policy.sh`
as the shipped-default gates.

## 7. The OOD and scenario caveats (binding on the reading)

* **The re-selection changes the observation mid-episode.** `_goal` is part of
  the policy's input (`rl_env.py` `_obs_snapshot` -> `goal`, fed to the
  checkpoint); a mid-episode switch is an input pair the checkpoint never saw
  (the default-off P4b2 `present` path is the only precedent). The *exposure*
  on the shipped band is ~0.3-0.8 % of episodes, so **M3 cannot measure its
  cost**; only M2 (28 % exposure) exercises it, and M2 is a *forced* scenario.
  The M2 conversion read therefore says nothing about the *shipped* rate.
* **M1/M2 are probes, not scenarios.** Their bands (0.10-0.17, 0.10-0.36) are
  outside the shipped 0.20-0.36, their delivered-x distributions are not the
  shipped one, and **no rate from them is quotable** — only the counts
  (attribution, conversion, cycle).
* **P4 is a safety check, not a power test.** At 0.06 % the expected exposure
  in 150 episodes is 0.09 events; the endpoint can only fail if the change is
  *harmful when it fires* or if it changes a path it should not touch.
* **The cycle changes population.** `no firable fruit` episodes are ~4x shorter
  than a 1500-tick timeout, so the pooled median would "improve" without an
  attempt being made — hence P6's fired-only population.
* **The class is not a pass.** `no firable fruit` is still a failure
  (`success=False`) and stays in the rate denominator; the endpoint is
  *attribution*, not elimination. The owner-facing sentence must be "the class
  is named and no longer unattributed", never "the failure is fixed".
* **The guard class is out of scope.** The opt-in `FRUIT_POLICY_TRIGGER_X_MAX`
  refusal (x = 0.39-0.42) is a different, operator-selected class
  (`P1_RESULTS.md` §3); phase 2 does not run the guard and does not claim it.
* **The transport is not touched**, and phase 1 says it should not be
  (0.000 mm). No supply/scene change is in phase 2; the supply lever is
  registered as **P38b** with `P1_RESULTS.md` §4.3's arithmetic.

## 8. The budget, the stop conditions, and the artefacts

Two claims: **M1+M2** (3 arms x 15 + 2 arms x 3 x 15 = 90 episodes, most of them
short in B/C) and **M3** (10 runs x 15 = 150 episodes, ~70-90 min wall on the
P37 measurement). One scripted acceptance pair (~10 min) and one selfcheck
(~7 s offline).

Stop conditions: **Fa/Fb/Fc/Ff stop the phase immediately**; a simulator wedge
follows the collector's rule (skip and retry, never stop the belt); the claim
script never kills another lane's run (`154_claim_run.sh`).

Artefacts: `logs/p38/P2_RESULTS.md` (the record: the per-arm tables, the exact
counts, the reason sets, the exposure, the decision), `logs/p38/p2_*.log` (the
runs), `logs/p38/MD5.txt` (all pins, before and after), and the docs
(`AGENTS.md` + `WORKLOG.md` only in phase 3, unless a phase-2 number changes a
documented claim).

## 9. What would make this pre-registration wrong

Named in advance, so phase 2 can be judged on them:

1. **The 4-candidate scan is too narrow** in a mixed band where every eligible
   fruit in the lane is below the floor — then C's conversion is low and the
   read is "the supply has no alternative", not "the lever works". Mitigation:
   the scan bound and the per-episode `seen` set are reported, and M2's band
   guarantees ~72 % firable draws.
2. **`select_target`'s `lane` filter is stricter than the trigger's** (it is
   grade-based, the trigger is not), so C may find fewer candidates than the
   fruit physically present. Reported per episode.
3. **The re-selected fruit is too far upstream** for the horizon
   (`_dynamic_select_floor` ~0.40 m at 0.12 m/s): the fire must still happen
   before tick 1500. If C's converted episodes cluster at `decision` ~1500 the
   conversion is nominal and the endpoint P2 must be read on *fires*, which is
   why P2 is "fires", not "placed".
