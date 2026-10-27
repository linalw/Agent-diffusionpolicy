# P49 phase 2 — the scripted selector x-ceiling: pre-registration

Written **before any run**, after the phase-1 census (`SELECT_CENSUS.md`). Lane:
`.slim/deepwork/p49-x-ceiling.md`. Tree: HEAD `ebc2c9c`, `tasks.py` **`b6de439c`**,
`rl_env.py` `93e35ef7`, `fruits.py` `dff684b1`, `scene.py` `27e3d64a`,
`configs/motion_reference.json` **`8a399626`**, `..._twoline.json` **`2246f83c`**.

**The census's prediction, stated first because it governs what the battery can
mean.** The chosen fruit's x is above 0.39 in **3 of 174 unique attempts
(1.7 %)**, all in the release-speed (`S2`) cell and the two-line; the shipped
acceptance branch tops out at **0.3653** and the pear at 0.3510, and no usable
candidate in 40 full-set selections exceeds **0.369**. Therefore:

* **P-A**: a ceiling arm on the shipped acceptance and on the pear refuses
  **0 times** and must be **byte-identical** to its control. These arms are an
  *inertness + no-harm* test, **not** a conversion test.
* **P-B**: the only single-arm instance the lever can meet in this corpus is
  **E1** (`accept_s5_S2` attempt 1, kiwi 5.6, delivered x = **0.3969**, its
  *selection* x bounded to **[0.378, 0.397]**), which lives in
  `FRUIT_SPEED_RELEASE=1`. Hence the battery carries an **event-bearing arm**
  (§2.2) — without it the registered `C/X/X+U` cells cannot exercise the knob at
  all, and the one open question (does the ceiling fire at the selection
  instant?) is unanswerable from the record.

Everything below is fixed before the first run. Deviations get an amendment
(`PREREG_A1.md`), not an edit here.

---

## 1. The knob

| | |
| --- | --- |
| name | **`FRUIT_SELECT_X_MAX=<m>`** (metres; **`0`/unset = off**; registered **`0.39`**) |
| site | `tasks.py select_target`, the **scripted single-arm** branch — i.e. after the `lane is not None` and `prefer_lane is not None` returns, in the same place as the `FRUIT_SELECT_NEAREST_ABOVE_FLOOR` resolution (~`:5881`) |
| rule | keep `usable = [c for c in usable if c.x <= ceiling]`; the shipped farthest-upstream rule then takes the largest `along` of what remains; **if nothing remains the call returns `None`** → `[run] attempt N: no eligible fruit` → the driver's existing skip path |
| off path | unset/`0` skips the block; the stream must be **byte-identical** to `logs/p44/p2/*` (P44's pin is this tree) |
| parse | one `os.environ.get` per selection (the shape `FRUIT_SELECT_NEAREST_ABOVE_FLOOR` already uses); a non-numeric value raises `ValueError` (fail loud); `<= 0` disables |
| print | **one `[xsel]` row per attempt, only when the knob resolves > 0**: `[xsel] attempt N: ceiling=0.390 usable=U kept=K over=O decision=pass\|substitute(x=...)\|skip`. Print-only, no new pose reads (the positions are already in hand) |
| must not change | the diag rows' meanings (the `[bed-sel]` `live/window/admitted` counts keep meaning "what the floor admitted"; the ceiling's effect is read from the `[xsel]` row cross-read against the same attempt's block) |

**Scope, by construction (all four are code properties, not conventions):**

1. **two-line** — returns at `prefer_lane is not None` before the site;
2. **shared-station worker** — returns at `lane is not None` before the site;
3. **direct / policy** — `select_target(..., direct=True)` (the P43 L1 precedent);
   the block is `and not direct`, so no direct baseline moves;
4. **indexed pick** (`FRUIT_DYNAMIC_PICK=0`) — `_prefer_upstream` is False, so
   the call returns at the `station`/`upstream` blocks *below* the site;
5. **reach-anywhere** — returns at `_reach_anywhere_select` before the site.

A scripted single-arm *dynamic* line only. `accept.sh`, `accept_policy.sh` and
`demo_2min.sh` are unaffected with the knob unset.

---

## 2. The arms

One `scripts/154_claim_run.sh` claim per run, strictly sequential, one
instrumentation set on **every** arm: `FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
FRUIT_BED_DIAG=1`. The last is the census's condition C1 — it is **proven
print-only** (`d0_accept_A_s5` vs `post_revert_accept_unset`, **387/387**
`[fruit]` lines identical, `SELECT_CENSUS.md` §1.2), and with it on *every* arm
the refusal's substitute is a read value instead of an inference. `ATTEMPTS=10`
throughout; `SEED=5`.

### 2.1 The registered battery (the spec's cells)

| # | scenario | arm | env |
| --- | --- | --- | --- |
| 1 | acceptance | **C** | — (control) |
| 2 | acceptance | **U** | `FRUIT_SPEED_ALL=1` |
| 3 | acceptance | **X** | `FRUIT_SELECT_X_MAX=0.39` |
| 4 | acceptance | **X+U** | `FRUIT_SELECT_X_MAX=0.39 FRUIT_SPEED_ALL=1` |
| 5 | pear | **C** | `FRUIT_SUPPLY_SPECIES=pear` |
| 6 | pear | **U** | `+ FRUIT_SPEED_ALL=1` |
| 7 | pear | **X** | `+ FRUIT_SELECT_X_MAX=0.39` |
| 8 | pear | **X+U** | `+ FRUIT_SELECT_X_MAX=0.39 FRUIT_SPEED_ALL=1` |

Interleaved C -> U -> X -> X+U per scenario (the arms of a contrast inside one
stretch, AGENTS §3b). U = `FRUIT_SPEED_ALL=1` = P44's S13 union (place 0.52 +
release 1 + lift 0.36).

### 2.2 The event-bearing arm (added by the census, §P-B)

| # | scenario | arm | env |
| --- | --- | --- | --- |
| 9 | acceptance | **C'** | `FRUIT_SPEED_RELEASE=1` — **not run**: the pre-recorded control is `logs/p44/p2/accept_s5_S2.log` (same tree, same seed, 10 attempts, carries E1) |
| 10 | acceptance | **X'** | `FRUIT_SPEED_RELEASE=1 FRUIT_SELECT_X_MAX=0.39` |

C' is *replayed by the record*: if run 10's first divergence from
`accept_s5_S2.log` is not at the refusal tick, the arm is void (F6).

### 2.3 The scope arm (E6)

| # | scenario | arm | env |
| --- | --- | --- | --- |
| 11 | two-line dense | **T+X** | `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SELECT_X_MAX=0.39` — control is the pre-recorded `logs/p46/p1/twoline_s5_C.log` (bit-identical to `p44/p2/twoline_s5_C.log`) |

**Cost: 10 runs**, ~4.7 min each at the acceptance's 274-293 s measured wall
(`logs/p44/p2/batch_A_driver.log`) plus ~40 s inter-run overhead -> **~50-55 min
of one simulator, one claim**. Dropping the pear's U/X+U cells would save ~10 min
and is the only compressible part; it is **not** dropped unless the owner says so
(they are the X-vs-U interaction, and the pear is the second scenario).

---

## 3. Endpoints and decision rules

| id | endpoint | definition | pre-registered prediction |
| --- | --- | --- | --- |
| **E1** | the ceiling's action | per arm: `[xsel]` rows with `decision != pass` (**refusals**), and the `[run] attempt N: no eligible fruit` rows (**skipped slots**), with the refused x and the substitute's x/along | **0 refusals, 0 skips on arms 1-8**; **0 or 1** on arm 10 — E1's *selection* x is bounded to **[0.378, 0.397]** by the census (§1.3), so the `[xsel]` row decides it; 0 on arm 11 |
| **E2** | placed count | `[stats] successes` per arm; contrasts **X vs C**, **X+U vs U** (both scenarios), **X' vs C'**; plus the event's conversion class (substitute attempted / skipped) | **X = C, X+U = U** exactly (inertness); X' either attempts a legal substitute or skips 1-3 slots — one instance, a **mechanism** read |
| **E3** | `s/attempt` | `[stats]` `s/attempt` (the project's definition of record, not span/attempts) | **identical** where E1 is 0; on X' no more than the skip cost (+0.5 s x skips over 10 attempts) |
| **E4** | no new reason | the per-attempt `notes=[...]` strings vs the baseline set (P44's: `fruit did not follow the gripper` only); `no eligible fruit` skips are **not** a note and are counted in E1 | **no new note** |
| **E5** | the motion gate | `python3 scripts/105_motion_regression.py <log> --fingerprint configs/motion_reference.json` on the single-arm arms; `scripts/190_twoline_gate.sh` (default reference `2246f83c`, floor 0.60) on arm 11 | C/U/X/X+U **`fingerprint: matches`** (all byte-identical); C' does not match (a different branch) and is gated on **budgets only**; arm 11 **PASS** |
| **E6** | the scope | arm 11's physics `[fruit]` stream vs `twoline_s5_C.log`, and the code properties of §1 | **byte-identical**; the two-line/shared/direct/indexed paths cannot reach the site |

**Instrument neutrality is a condition, not a claim**: the `[bed-sel]` census is
proven print-only (387/387); a *new* print (`[xsel]`) appears only on the X arms,
so E1's reading of the C arms does not depend on it, and the gate contrast is
X-vs-C *inside* the X arm's own refusal accounting. If any C arm fails to replay
its P44 record byte-identically, the battery is **void** (the tree or the branch
moved) — that is the tree check, not a result.

**Adoption rule (fixed now).** Adopt **iff all four**:

1. **E2-conversion**: on arm 10 the refusal finds a **legal substitute**
   (`kept >= 1`) and that attempt runs to a **baseline** terminal (a new
   `no eligible fruit` skip does not qualify — it is still a lost slot);
2. **E2-no-fall**: `X >= C` and `X+U >= U` on **both** scenarios (in-batch);
3. **E4** no new reason and **E5** the gates pass;
4. **E6** arm 11 byte-identical.

Anything else is **not adopted** and is published as the negative with the
mechanism. In particular: P-A predicts (2)-(4) pass *trivially* (inertness), so
the whole decision rests on (1) — **one instance in 174 attempts**. That is a
mechanism read at the P38/P43 precedent's strength, **not a rate**; a rate would
need the WS-4.2 N >= 5 seeds per arm, which this phase does not fund and does not
claim.

**Predictions that would make the phase a finding either way**

* **P1** C ≡ X and U ≡ X+U, byte-identical on both scenarios (0 refusals).
* **P2** arm 10's first divergence from `accept_s5_S2.log` is at attempt 1's
  **selection** (or not at all), and its `[xsel]` row prints the selection x,
  which the census bounds to **[0.378, 0.397]** — the run resolves whether the
  ceiling fires there. (A refusal is not assumed: 34/39 of the measured
  selections agree with their delivered x to <= 2.7 mm, 5/39 move 5-19 mm
  outward *after* the selection.)
* **P3** arm 10's outcome class is "1-3 skipped slots" **or** "one attempt on a
  substitute at x <= 0.39". The census cannot say which (the event arm's live set
  was never censused) — that is what arm 10 buys.
* **P4** arm 11 is byte-identical to `twoline_s5_C.log` **with the knob set**
  (the knob is unreachable from the two-line path, not merely unset).
* **P5** arms 1, 2, 5, 6 replay `logs/p44/p2/accept_s5_C.log`,
  `accept_s5_S13.log`, `pear_s5_C.log`, `pear_s5_S13.log` byte-identically.

---

## 4. Falsifiers (a fire is a published result, not a re-run)

| id | fires if | reading |
| --- | --- | --- |
| **F1** | any C/U arm fails to replay its P44 record | the tree or the branch moved -> battery **void**; nothing about the knob is measured |
| **F2** | **C != X** or **U != X+U** on a primary arm (any line) | the census's "no usable candidate above 0.369" is **falsified**; a refusal exists where 0 was predicted, and the phase must be re-read as a rate test with the refusal's own accounting |
| **F3** | arm 10 diverges from `accept_s5_S2.log` **before** its first refusal | the event arm's instance attribution is void (the census's cell claim is falsified) |
| **F4** | arm 10's refusal yields `kept = 0` (skip) | the lever is a **skip** by construction on this line: attribution only, **not adopted** (P38's precedent: naming a class is not converting it) |
| **F5** | arm 10's substitute attempt ends in a **non-baseline** reason or a grip loss | the substitute carries its own cost -> **not adopted** |
| **F6** | `X < C` or `X+U < U` placed | **not adopted**, whatever the event arm shows (this is the P44/P46 lesson: a speed/timing lever's count is branch-decided, so a fall is a fall) |
| **F7** | arm 11 is not byte-identical | the scope leaks -> **not adopted** and a `src/` defect is filed before anything else |
| **F8** | a new `notes=` string appears anywhere | **not adopted** |

---

## 5. No-harm and reference policy (fixed before the run)

* `configs/motion_reference.json` (`8a399626`) and
  `configs/motion_reference_twoline.json` (`2246f83c`) are **not** re-recorded:
  the knob is default off and no shipped default changes.
* `scripts/189_w7a_chain.sh` is **not** run (it rewrites the two-line reference
  from `logs/w7/10` before gating).
* `scripts/selfcheck.sh` after the `src/` edit (the leg must stay green; the
  knob's default-off path is what the selfcheck exercises).
* If (1)-(4) of the adoption rule pass, phase 3 owns the default flip, the
  `rl_env.py` `TASKS_MD5` follow, the reference question and the commits. If they
  fail, phase 3 owns the negative, the doc updates and the commits.

## 6. What this phase cannot show (stated now)

Nothing about a **rate**: the whole corpus holds 3 tail attempts, and the battery
can re-measure **one** of them. Nothing about the **direct/policy** interface
(`direct=True` scopes the knob off) and nothing about the **two-line** (out of
scope by construction). Nothing about the **choice of 0.39 over 0.40**: the
census says 0.40 and 0.42 are empty on this corpus, so the battery cannot
distinguish them either — 0.39 is P34's clean-band edge, taken as given.
