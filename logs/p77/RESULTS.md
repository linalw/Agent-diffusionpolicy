# P77 results — the 60 N clamp at three seeds: the **count** converts, the
# **escape class** does not, and the pry is mostly replaced by a shallow axial exit

**Evidence phase (owner-chosen), not a shipping claim.** Nothing adopted, no
default changed, no commit, `configs/*` untouched. Two arms - **C** the shipped
10 N (`FRUIT_FINGER_MAXFORCE` unset) and **T** `FRUIT_FINGER_MAXFORCE=60` -
interleaved by seed, **seeds 77 / 101 / 202**, 15 picks each, one claim per cell,
the P66-phase-3 / P71-phase-2 / P73 / P74 / P75 / P76 scenario verbatim,
`moe_v13s` `61da390a`. The rule was pinned before any run
(`PREREG.md`, md5 **`d31c3e4a`**).

**The honesty frame, which governs every number below.** 60 N per finger joint
(a delivered pinch of ~52-56 N here) is **jaw-feasible** - commercial parallel
jaws in this class deliver 20-235 N - but it **would bruise a 3.6 cm berry in
reality**, and **this simulator has no bruise model, no damage model and no
flesh-compliance model**. So a clean read below is a statement about **geometry
and retention**, never about fruit quality. That is exactly why this cell is a
**sensitivity** and not a decision to ship.

---

## 0. Verdict — the owner's two questions

| question | answer |
|---|---|
| **does the class the prys belong to convert at the population level at 60 N?** | **In count, yes; in mechanism, no.** Left placed **11/21 -> 17/20** (Fisher **p = 0.043**; 3/3 seeds improve; class-standardised **0.524 -> 0.927**), left `cnp` **7 -> 3**, left never-held **3 -> 0**. But the pre-registered mechanism bar **fails**: left escape legs **7 -> 3** (43 % of the control, not <= 1/3), and the residue is a **different mode** - **2 of the 3** T escapes leave through a **3.4 / 7.9 mm** pad opening (the pads essentially closed on the fruit) instead of the control's **13.5-39.9 mm** pry, and **1 of 40** T legs still pries fully to the 98.1 mm stop |
| **what would shipping it cost?** | **Both motion references and every store.** At 60 N the scripted acceptance **moves at attempt 0** (`fingerprint: DIFFERS`, 378 vs 346 `[fruit]` lines) and the two-line **moves too** (`190` gate FAIL on the fingerprint alone, 8/10 at its own 0.60 floor). A cap is global (both arms, both presentations), so a flip owes **both motion references** (plus the patch/bed references wherever those scenarios are gated), a re-baseline of every scripted number and a provenance re-record for every store - for a class reduction that is real but not a deletion |

**P76's single-draw headline does not reproduce at 3 seeds.** P76 read
**0/26 pried, 0/26 escaped** at 60 N (seed 77, one draw) and concluded "the pry
is deleted". At 40 left carry legs across three seeds, 60 N reads **1 pried and
3 escaped** - and the same instance that P76 saw held (a 6.8 cm pear, `place0`,
`sep_max` 75.2, slip 0.0 mm) escapes here at **`sep_max` 76.2, slip 834.7 mm**.
The cap **reduces** the class by more than half and **changes its mode**; it does
not delete it. That is the correction this cell exists to make.

---

## 1. The batch, and the manipulation check

Six cells, all evaluable. Two independent confirmations plus the behavioural one:

| cell | build print `maxForce=` | env derev | live read-back `[drive]` | manifest `physics` | held `force_min` median |
|---|---|---|---|---|---|
| C 77 / 101 / 202 | `10.0` (shipped string) | (unset) | (absent by construction) | `finger_maxforce: null`, `readback_matches: true` | **9.72 / 9.96 / 9.71 N** |
| T 77 / 101 / 202 | `60.0` | `60` | `60.00/0.00 N` both arms | `finger_maxforce: 60.0`, `readback_matches: true` | **56.31 / 53.41 / 52.08 N** |

`joint2` is the drive-less `PhysxMimicJointAPI` mimic and reads `0.00` on both
arms in both arms' manifests. The pinch (a median of **53.4 N** at 60 N against
**9.72 N** at 10 N) is P41's law - delivered pinch ≈ cap - and it is ~89 % of the
cap, the same 85-99 % band P76 measured. `logs/p77/p77_report.py --check` exits
**0**: every cell's declared cap is the cap the drive read back, all six cells
carry 15 episodes, and all **166** `[carry]` rows parsed.

**Order and drift.** Arms are adjacent within a seed and the order alternates by
seed (`77 C->T`, `101 T->C`, `202 C->T`), so a monotone wall-clock drift cannot
load onto one arm; the arm mix confirms it - C drew **21** left attempts, T
**20**, against 45 attempts per arm.

**Wall clock.** Phase 1 (the six cells) ran **17:26:59 -> 18:24:58** (58 min,
9.7 min/cell); phase 2 (the two price runs) **18:24:58 -> 18:35:06** (10 min).
No cell was re-run, no claim overlapped, and `run_p77.sh` reports `fail=0`.

**A same-configuration replay check, because the pairing depends on it.** C_77
re-runs P76's F10_77 exactly (same seed, same config, same scenario): **2 of 15
episodes are identical, the first divergence is at episode 2** (a 3.6 cm
strawberry in P76's cell vs a 6.0 cm peach here). So the direct loop is **not
reproducible** even at the same seed (the documented rendered-frame branch), an
instance cannot be paired across arms, and every per-arm count below is **one
draw of a branch** - which is why the mechanism rows carry the claim.

## 2. The mechanism — the pry is mostly gone, the exit is not

Per `[carry]` leg (both arms instrumented identically, `FRUIT_CARRY_DIAG=1`),
escape = `clean_slip_max > 100 mm` with a pinch, pried = `sep_max >= 95 mm` of
the 98.1 mm travel stop:

| arm | left carry legs | escapes (> 100 mm) | of which > 800 mm | **pried to the stop** | never-held |
|---|---|---|---|---|---|
| **C** (10 N) | 38 | **7** | 5 | **4** | 2 |
| **T** (60 N) | 40 | **3** | 3 | **1** | 0 |
| C right | 43 | 0 | 0 | 0 | 1 |
| T right | 45 | 0 | 0 | 0 | 1 |

**Every escape and every pry in both arms is a left `place0` leg** - the site is
invariant, the mode is not. The discriminator is the **pad opening beyond the
fruit's own width** (`sep_max - dia`), and the two populations separate:

| arm | leg | `sep_max` | `dia` | `sep_max - dia` | `gap@sep_max` | slip | `fmax` |
|---|---|---|---|---|---|---|---|
| C | pear 6.1, left `place0` | 89.8 | 61.3 | **+28.5** | 60.1 | 740.0 | 14.95 |
| C | peach 5.8, left `place0` | **98.1** | 58.2 | **+39.9** | 57.1 | 918.0 | 11.38 |
| C | apple 7.0, left `place0` | **98.1** | 69.6 | **+28.5** | 68.7 | 843.4 | 16.89 |
| C | kiwi 6.7, left `place0` | 85.7 | 66.8 | +18.9 | 65.7 | 811.7 | 14.65 |
| C | kiwi 5.3, left `place0` | 66.8 | 53.3 | +13.5 | 57.7 | 858.7 | 13.19 |
| C | kiwi 6.7, left `place0` | **98.1** | 66.8 | +31.3 | 66.9 | 709.0 | 15.28 |
| C | kiwi 5.7, left `place0` | 80.4 | 57.1 | +23.3 | 57.4 | 828.6 | 12.90 |
| **T** | pear 6.8, left `place0` | 76.2 | 68.3 | **+7.9** | 69.9 | 834.7 | 57.83 |
| **T** | pear 6.6, left `place0` | 69.3 | 65.9 | **+3.4** | 66.3 | 844.5 | 58.79 |
| **T** | peach 6.2, left `place0` | **98.1** | 61.9 | **+36.2** | 63.5 | 782.9 | **64.52** |

Three readings, in order of strength:

1. **The pry is reduced, not deleted.** 4/38 -> 1/40 left legs reach the stop
   (25 %, inside the pre-registered 1/3 bar) - but one **does**, at a peach 6.2
   with `fmax` **64.52 N**, i.e. **above the 60 N cap's own delivered level**,
   and it walks 782.9 mm. So 60 N buys a 4x reduction in pries, not a
   guarantee.
2. **The escape that remains is a different object.** At 10 N, **all 7** escapes
   leave with the pads **13.5-39.9 mm** past the fruit's width (a genuine
   expulsion through an opening gap; 3 of them at the travel stop). At 60 N,
   **2 of 3** leave with the pads **3.4 / 7.9 mm** past the width - the pads
   essentially closed on the fruit, and the payload walks out **along the tool
   axis**, which is P61's measured direction (leg-frame mean unit `(-0.351,
   +0.240, +0.905)`, 25.2 deg off the tool axis) and P75's `place0` geometry.
   **Force resists the radial pry; it does not resist the axial slide.**
3. **The one control pry that recovered is named.** A kiwi 6.7 at 10 N reaches
   `98.4 mm` and slips only **13.1 mm** (it placed): a pry whose payload was
   re-seated, so `sep_max >= 95` alone is not an outcome - the escape count is.

The delivered pinch is **9.72 N (C) vs 53.41 N (T)** by cell medians
(9.72/9.96/9.71 against 56.31/53.41/52.08), i.e. T sits at **87-94 %** of its
cap on all three seeds, so the arm under test is the arm that ran.

## 3. The crush guard, and the strawberry (the binding class)

**C1 (`sep@loss - dia <= -15 mm` on a physical, pinched leg) and C2
(`force_min >= 35 N` on an escape leg) fire on 0 legs in both arms** - 0/6 cells.
The smallest fruit, per leg:

| arm | legs | placed | `sep_max` | `sep_max - dia` | `fmax` | verdict |
|---|---|---|---|---|---|---|
| **C** | 5 strawberries (35.6 / 38.8 / 40.4 / 43.0 mm) | **5/5** | 38.8-47.5 | +2.5 .. +8.7 | 5.55-69.08 | held, no interference |
| **T** | 7 strawberry legs (35.6 / 38.8 / 40.4 mm) | **6/6 real legs** | 36.1-45.0 | **-0.7 .. +6.2** | 38.89-73.33 | held, no interference |

The 60 N cell holds the **3.6 cm** berry at a **36.7 mm** span under a
**52.6-54.2 N** pinch (`sep_max - dia` **+1.1 mm**) and places it - the same
reading P76's extension cell made, now at three seeds. **The one non-placed
strawberry leg is an artifact, not a crush**: T_101, `sep@loss` **10.0 mm**,
`fmax` **0.00 N**, `clean_slip_max` **160 769.6 mm** - a recycled payload whose
position was teleported (P76 A3's class), excluded because the leg was never
held and its slip is not physical. It is listed here so the exclusion is visible.

## 4. The counts — the primary, with the pairing stated

| seed | C left placed | C left `cnp` | T left placed | T left `cnp` | left delta |
|---|---|---|---|---|---|
| 77 | 3/6 | 2 | 6/7 | 1 | **+3** |
| 101 | 4/10 | 4 | 5/6 | 1 | **+1** |
| 202 | 4/5 | 1 | 6/7 | 1 | **+2** |
| **pooled** | **11/21 = 52.4 %** | **7** | **17/20 = 85.0 %** | **3** | **+6** |

* **Fisher exact, left placed vs not: p = 0.043**; left `cnp` vs placed:
  p = 0.144 - the `cnp` class moves **7 -> 3**, but its denominator is only the
  *grasped* attempts (18 vs 20), so it is the weaker of the two contrasts and is
  reported, not leaned on.
* **Left never-held 3 -> 0** (the acquisition class is not the one this cell
  moves; it went the right way by 3 attempts and is *not* counted as a win).
* **Run level: T's left placed is higher in 3 of 3 seed pairs** (deltas
  +3/+1/+2). The one-sided sign test's **minimum attainable p at N=3 is 0.125**
  and that is what it reads - the run level cannot be stronger than that, and it
  is quoted as a ceiling, not as confirmation.
* **Class-standardised (T re-weighted to C's species mix, 21/21 attempts in
  shared classes): 0.524 -> 0.927**, in the same direction as the raw pooled
  0.524 -> 0.850, so the delta is not a class-draw artifact. Per class:
  kiwi 4/11 -> 4/4, peach 1/2 -> 4/5, pear 3/4 -> 5/7, apple 1/2 -> 2/2,
  orange 2/2 -> 1/1, lychee (T only) 1/1.
* **The pairing that can be defended** - `(seed, arm=left, species, diameter to
  0.1 cm)`, greedy one-to-one: **11 of C's 21 left attempts pair** (10 are
  **unpairable**: a fruit the other arm never drew), **both placed 5, C-only 0,
  T-only 6, neither 0**, exact McNemar **p = 0.031**. This is a **descriptor**,
  not the primary: the fruit presented depends on earlier outcomes (a
  post-treatment variable), and §1's replay check shows why no instance-level
  pairing exists on this interface.

## 5. The guards

* **The right is not worse**: placed **21/24 (C) -> 22/25 (T)**, `cnp` **0 -> 0**,
  never-held 3 -> 3, escapes **0 -> 0**, and **no new right failure reason**.
* **Failure ledger by class, both arms**: every non-placed episode is either
  `cnp` (grasped-not-placed, which carries **no reason string** - the class is
  read from `grasped`/`placed`) or never-held. The only **reason** string on a
  failure in either arm is `fruit fell off the line` (**C 3, T 2** - the supply
  class, not the grip). **No new reason appears in T.**
* **Landing class**: `did not land` 0, `discharged` 0, `fell off the line`
  C 3 / T 2. No payload reached the wrong place in either arm.
* **Arm mix per seed** (arm = grade = lane, `rl_env.py:2516`): C 6/10/5,
  T 7/6/7 left of 15 - pooled 21 vs 20, so the count delta is not an arm-mix
  artifact.
* **Cycle ticks** (median per cell): C 1779 / 1765 / 1795, T 1770 / 1776 / 1753 -
  **-0.5 %** at the median of medians. The 60 N cap does not cost cycle time.

## 6. The registered decision rule, evaluated

```
M1  T left escapes <= 1/3 C's:      C 7 -> T 3      FAIL  (43 %, not <= 33 %)
M2  T left pried   <= 1/3 C's:      C 4 -> T 1      PASS  (25 %)
M3  zero crush legs in T:           0               PASS
M4  C's left escape set non-empty:  7               PASS
->  MECHANISM: DOES NOT CONVERT (the escape class survives at half strength, in
    a different mode; the pry does convert)

N5  left placed up (11 -> 17), cnp down (7 -> 3), run level 3/3   PASS
N6  right within 1 (21 -> 22), no new right reason                PASS
N7  class-standardised moves with the raw pooled rate             PASS
->  COUNT: CONVERTS
```

**The two statements are both true and must be quoted together.** The cap
**more than halves** the class and **deletes three quarters of its pries**, and
at the count level that is a real gain (11 -> 17 left placements, p = 0.043,
3/3 seeds, right not worse). But the escape **mode** survives force: the
residue leaves axially through a 3-8 mm gap, which is the `SIM_LIMIT.md` / P61
loaded-slide geometry, and one leg in 40 still pries fully at 60 N. **A count
across arms is still a count across attractors** - the per-leg mechanism rows of
§2 are the claim; §4 is the paired report with its n.

## 7. The price of an adoption (report only - nothing re-recorded)

**P1 - the scripted line at 60 N** (`logs/p77/p1_accept_mf60.log`, one
`scripts/accept.sh`, 10 attempts), against `logs/p76/accept_noharm_full.log`
(the shipped-cap record, 346 `[fruit]` lines, md5 `d0079a23`):

| read | result |
|---|---|
| success count | 6/10 at 60 N against the archive's 6/9 - **same count, different attractor** |
| `[fruit]` stream | **378** lines vs 346; md5 `4d89c743` vs `d0079a23`; with the print-only rows (build print + `[drive]` read-back) dropped, **375 vs 345 physics lines and 57 identical at the same index** |
| first physics-line difference | **attempt 0's descent**: `|a|max` 2.061 vs 2.060 m/s², `|j|max` 246.3 vs 246.9 m/s³ |
| first **outcome** difference | **attempt 0 itself**: at 60 N `grasped=True placed=True lift=+0.411 m force=60.05 N`; at 10 N `grasped=True placed=False lift=+0.138 m force=9.98 N` |
| fingerprint | **DIFFERS** from `configs/motion_reference.json` (`8952c320`): legs 2-9 all move by 1-2 samples, and the run has 10 legs against the reference's 9 (the archive's own branch was 6/9) |

So a flip **moves the scripted branch at its first attempt** - the cap is a real
physics lever there, not just a diagnostic. Every scripted number in this file
would need re-baselining.

**P2 - the two-line at 60 N** (`logs/p77/p2_twoline_mf60.log`, 10 attempts),
against `configs/motion_reference_twoline.json` (`eb697f23`, **not**
re-recorded): **8/10 = 80 %** - above its own 0.60 floor - with all ten descents
inside their speed budgets (worst `|v|max` 0.129 against 0.160-0.161), and the
`190` gate still **FAILs on the fingerprint alone** (legs 3-10 move; leg 6
descends in 92 samples at 0.129 m/s against the reference's 88 at 0.109). Two of
18 carry legs show a rescued payload (>400 mm slip: 1485.7 mm and 484.2 mm, the
latter at a **9.12x** reported cone) - but the **shipped-cap** two-line from the
same scenario (`logs/p71/twoline/none.log`, cross-tree, 17 legs) has three of
its own (805.2 / 332.9 / 112 673 mm), so **60 N does not make the two-line
escape-free** and this run does not separate the cap from the branch.

**Verdict on the price:** a 60 N flip owes **`configs/motion_reference.json`,
`configs/motion_reference_twoline.json`** and **every store's `physics`
provenance** (a cap is global: both arms, both presentations), plus a scripted
re-baseline. For a class that shrinks but does not close, that is a real cost and
the owner should weigh it against §0's mechanism statement - not against P76's
single-draw "0/26".

## 8. No-harm, pins, and the evidence layout

**No `src/`, `configs/`, reference or checkpoint change in this phase** - it is
env-only, so the tree is byte-identical to P76's and `scripts/accept.sh` at the
**shipped** cap is untouched by construction (`configs/motion_reference.json`
`8952c320`, `..._twoline.json` `eb697f23`). `scripts/selfcheck.sh` was run at the
end of the phase: **PASS, 0 failures** (`logs/p77/selfcheck.log`).

```
logs/p77/PREREG.md          the rule, pinned before any run      (md5 d31c3e4a)
logs/p77/PREREG.md5         the pin + timestamp
logs/p77/header.txt         the md5 pin block of the batch
logs/p77/run_p77.sh         the driver (phase 1 = 6 cells, phase 2 = the price)
logs/p77/p77_report.py/.txt the per-leg table, the pooled primary, the guards,
                            the registered rule, the price
logs/p77/direct/<arm>_<seed>.log   6 cells, one claim each
logs/p77/rollouts/<arm>_<seed>/    the manifests (the physics block read-back)
logs/p77/p1_accept_mf60.log/.driver   the scripted price run at 60 N
logs/p77/p2_twoline_mf60.log/.gate    the two-line price run at 60 N
logs/p77/selfcheck.log              the close-out self-check
```

**Pins** (unchanged from P76, because nothing in `src/` or `configs/` moved):
`tasks.py` **`9d5824ef`**, `rl_env.py` **`7ca5aa70`**, `assets.py` `540406fa`,
`fruits.py` `c7461d41`, `scene.py` `27e3d64a`, `control.py` `9384ff4f`,
`policy/trigger.py` `b09d3cb2`, `configs/motion_reference.json` **`8952c320`**,
`configs/motion_reference_twoline.json` **`eb697f23`**, checkpoint `moe_v13s`
**`61da390a`**. The batch's own md5 block is `logs/p77/header.txt`.
