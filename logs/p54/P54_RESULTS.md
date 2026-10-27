# P54 phase 1 - the shipped direct configuration measured: ACQ off vs ACQ=1

Measured **2026-10-28** on this tree (HEAD `c717de0`, the P53 close). One battery,
six runs, one simulator, one claim (`logs/p54/p1/batch_outer.log`, wall **3070 s**).
No `src/` edit, no `configs/` change, no commit: both arms are **env-only** and the
knob was verified to be so (`FRUIT_POLICY_TRIGGER_ACQ` is read at
`src/fruit_sorting/policy/trigger.py:167`, unset = `"0"`, no `presentation` guard,
no `configs/` field; nothing else in `src/` reads it).

Reproduce:

```bash
nohup bash logs/p54/run_batch.sh > logs/p54/p1/batch_outer.log 2>&1 &
python3 logs/p54/p54_report.py   --dir logs/p54/p1 --a A --b B   # -> logs/p54/p1/P54_report.txt
python3 scripts/113_rl_report.py logs/p54/p1 --a A --b B          # -> logs/p54/p1/P54_113_A_B.txt
python3 logs/w7/B_ab_report.py   --dir logs/p54/p1 --a A --b B   # -> logs/p54/p1/P54_w7acq.txt
```

**The four sentences this phase exists to support.**

1. **The shipped direct configuration was never the configuration on record.** With
   `FRUIT_POLICY_TRIGGER_ACQ` unset (the shipped default, R5 decision 4) the direct
   interface reads **right 15/28 = 53.6 %, left 1/17, pooled 16/45 = 35.6 %**; with
   `=1` (the state every park-era batch runs) it reads **right 34/35 = 97.1 %, left
   0/10, pooled 34/45 = 75.6 %**. The 94.6 % right of `MODEL_CENSUS` §4 is the second
   column - **the shipped configuration is 44 points behind it on the right arm.**
2. **The mechanism is the fire budget, and it is measured on both arms with the same
   instrument.** ACQ off fires at the first tick the arrival prediction reaches the
   shipped `lead = 0.90 s` - **all 45 fires land at `t_arrive` 0.89-0.90 s** - while
   the direct handover's own setup takes **1.17 s** to enter its wait loop
   (`wait` stamp p50; 0.98 s to reach hover). ACQ=1 extends the lead by
   `0.60 + |jaw-station| / 0.20` and the same handover then starts with **2.11 s**
   of belt time (1.59-2.59) - it hovers at 0.85 s and **waits 0.75 s for the fruit**
   instead of 0.17 s.
3. **The class the knob targets collapses**: never-held (`grasped=False`) goes
   **26/45 = 57.8 % -> 2/45 = 4.4 %** (two-sided Fisher **p = 3.2e-8**), the
   catch-up residual **p50 90.6 -> 5.7 mm** (24/45 over the 6 mm tolerance -> 1/44),
   and the close-start offset **|y| 185.7 -> 3.6 mm** on the left. All 26 ACQ-off
   never-held rows are **trigger-path** (0 policy-gate), i.e. inside the knob's reach.
4. **E1 FAILS in the direction that matters**: the shipped config is not
   non-inferior, it is **materially worse** (delta `rate_A - rate_B = -0.436`
   against a `-0.10` bar; behind in **3/3 runs**). E3 also fails on its letter (one
   new reason key in B, characterised in §5 as the P38 supply x-tail, not the knob).

---

## 1. What was registered (before the run) and the battery

`logs/p54/PREREG.md` (written before the first arm finished; `logs/p54/p1/P1_header.txt`
is the batch's own timestamped header). The question: `logs/p52/MODEL_CENSUS.md` §4-§5
records that the direct baseline **right 94.6 % / left 4.8 %** is an **ACQ=1** number
while the shipped default is ACQ **off** (W7-B; R5-4), and `60_eval_policy.py` (the
hybrid canary, the interface of record) never constructs the direct env at all - so
the shipped direct configuration had **no measurement**.

| arm | meaning | env |
| --- | --- | --- |
| **A** | **the shipped configuration** | `FRUIT_POLICY_TRIGGER_ACQ` **unset** |
| **B** | the configuration of record | `FRUIT_POLICY_TRIGGER_ACQ=1` |

Everything else is the P43 protocol verbatim: `checkpoints/moe_v13s/policy_best.pt`
(`61da390a`) on both arms, the W6-A/W8-A patch sheet
(`FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25`),
`FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1`, the
park **default** (`back`, P43), **N = 3 runs x 15** per arm, seeds 77/101/202, policy
seed 11, interleaved A then B, **one** `154_claim_run.sh` claim, no `--record` (no
endpoint here reads a store). Instruments on **both** arms: `FRUIT_ACQ_DIAG=1
FRUIT_CARRY_DIAG=1 FRUIT_PARK_DIAG=1`.

**The manipulation check passed before any outcome was read** (`P54_report.txt` §0):
A's three logs print `[rl] trigger=arrival lead=0.90s lateral=0.160 reach=0.20
finger=0.040 frame=station encoder=on present=off` **with no `acq=` term**, B's three
print `acq=on(speed=0.20,margin=0.60,cap=4.50,reach_margin=0.05)`; and in the
per-episode notes A carries **no** `lead=` suffix (0/45) while B carries it on **44/44**
fires (the suffix exists only with the knob on, `rl_env.py:3802-3806`). F1 did not
fire.

## 2. The outcome table

`P54_report.txt` §1-§2. `placed` is the gate's own flag; sim s = median ticks / 120.

| arm | run | seed | placed | right | left | never-held | cnp | ticks p50 | s/attempt | wall s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **A** | 1 | 77 | **6/15** | 6/10 | 0/5 | 8 | 1 | 1796 | 14.97 | 521.1 |
| A | 2 | 101 | **4/15** | 3/8 | 1/7 | 10 | 1 | 1951 | 16.26 | 447.9 |
| A | 3 | 202 | **6/15** | 6/10 | 0/5 | 8 | 1 | 1838 | 15.32 | 452.7 |
| **A pooled** | | | **16/45 = 35.6 %** | **15/28 = 53.6 %** | **1/17 = 5.9 %** | **26** | 3 | 1838 | **15.32** | 31.6 /ep |
| **B** | 1 | 77 | **14/15** | 14/14 | 0/1 | 0 | 1 | 1828 | 15.23 | 454.2 |
| B | 2 | 101 | **11/15** | 11/11 | 0/4 | 1 | 3 | 1776 | 14.80 | 424.8 |
| B | 3 | 202 | **9/15** | 9/10 | 0/5 | 1 | 5 | 1815 | 15.12 | 416.2 |
| **B pooled** | | | **34/45 = 75.6 %** | **34/35 = 97.1 %** | **0/10** | **2** | 9 | 1798 | **14.98** | 28.8 /ep |

**The pooled placed pair carries an arm-mix caveat, and the standardisation is
reported because of it** (the direct loop is not bit-reproducible, so the two arms
draw different fruit streams: `113` pairs only 14 of 45 episodes on the same fruit).
A drew 28 right / 17 left, B 35 right / 10 left. Arm-standardised:

| read | A (shipped) | B (ACQ=1) |
| --- | --- | --- |
| at a 50/50 arm mix | **29.7 %** | **48.6 %** |
| each at its own mix | 35.6 % | 75.6 % |
| **B at A's mix** | - | **60.4 %** |

So the gap is **19 points at a neutral mix, 25 at A's mix, 40 at B's** - the
direction never changes. The registered endpoint (below) is the right arm, where the
denominators are 28 and 35.

`113_rl_report.py` (`P54_113_A_B.txt`): pooled **16/45 (36 %) vs 34/45 (76 %)**,
paired 3 both-ok / 5 both-fail / **5 B-only / 1 A-only** (31 excluded: fruit class
differs), sign test p = 0.1094 at 6 discordant pairs; median cycle 1838 -> 1798
ticks (-2.2 %). **The paired test is not the design's read here** - the streams
diverge, so only a third of the episodes are pairable; the per-run counts are.

## 3. E1 - is the shipped config non-inferior? **NO** (FAIL, and by a wide margin)

Registered: the right-arm placed delta `rate_A - rate_B >= -0.10`.

| seed-run | A right | B right | delta (A-B) | A placed | B placed |
| --- | --- | --- | --- | --- | --- |
| 1 (77) | 6/10 | 14/14 | **-0.400** | 6/15 | 14/15 |
| 2 (101) | 3/8 | 11/11 | **-0.625** | 4/15 | 11/15 |
| 3 (202) | 6/10 | 9/10 | **-0.300** | 6/15 | 9/15 |
| **pooled** | **15/28 = 0.536** | **34/35 = 0.971** | **-0.436** | 16/45 | 34/45 |

**E1 FAIL.** The shipped configuration is behind on the right arm in **3/3 runs**
(-0.400, -0.625, -0.300 = **4, 5 and 3 attempts** at A's own denominators 10/8/10),
and the pooled right-arm difference is **Fisher p = 3.6e-5** (pooled placed
p = 2.6e-4). A 3-run design's smallest one-sided run-level sign p is 2^-3 = 0.125, so
the run level can only be **reported** (3/3), not gated - the pooled per-arm contrast
is what carries the significance, and the per-episode mechanism (§4) is what carries
the interpretation.

**What fails here is not a marginal bar.** The registered question was "is the shipped
config within 10 points of the one on record"; the answer is that it is **44 points
behind on the right arm and 40 points behind pooled**, with the failures concentrated
in one class that ACQ=1 deletes.

## 4. E2 - does ACQ=1 reduce the pre-contact acquisition class? **YES**

`P54_report.txt` §4-§5. Class = `grasped=False` (never held), split by fire path.

| arm | side | n | never-held | rate | trigger-path | policy-gate |
| --- | --- | --- | --- | --- | --- | --- |
| A | right | 28 | **12** | **0.429** | 12 | 0 |
| A | left | 17 | **14** | **0.824** | 14 | 0 |
| A | both | 45 | **26** | **0.578** | 26 | 0 |
| B | right | 35 | 1 | 0.029 | 1 | 0 |
| B | left | 10 | 1 | 0.100 | 1 | 0 |
| B | both | 45 | **2** | **0.044** | 2 | 0 |

Two-sided Fisher: pooled **p = 3.2e-8**, right **p = 1.1e-4**, left **p = 7.5e-4**.
**E2 PASS** - and every ACQ-off row is on the **trigger path**, so the knob can reach
all of them (the policy-gate fire that bypasses the trigger is 0/45 in both arms).

### 4.1 The mechanism, from the `[acq]` rows and the fire notes

| quantity | A (ACQ off) | B (ACQ=1) |
| --- | --- | --- |
| fire `t_arrive` (the arm's belt budget) | **0.89-0.90 s on 45/45** | **2.11 s** p50 (1.59-2.59), 44/44 |
| recorded `lead=` / `reach=` | not recorded (the shipped 0.90 s / 0.20) | 2.11 s / 0.30 p50 (0.24-0.36) |
| `|dy|` at the fire | **10.8 cm** | **25.3 cm** |
| handover: time to hover (stamp) | 0.98 s | 0.85 s |
| handover: `wait` stamp p50 (to the wait loop) | **1.17 s** | 1.59 s |
| hold at hover (`wait - hover`) | **0.17 s** | **0.75 s** |
| catch-up residual `res` p50 / p90 / max | **90.6 / 391.6 / 1212.6 mm** | **5.7 / 5.9 / 216.8 mm** |
| attempts over the 6 mm tolerance | **24/45** | **1/44** |
| close-start `|y|` p50 (left / right) | **185.7 / 4.9** mm | **3.6 / 3.9** mm |
| close-start `|y|` max (left / right) | 566.6 / 435.7 mm | 4.2 / 210.5 mm |

**The arithmetic the two arms differ by.** A's fire is a pure function of the shipped
lead: every attempt fires at `t_arrive` = 0.89-0.90 s. Its handover then spends
**0.98 s reaching hover and another 0.19 s entering the wait loop** - already more
than the 0.90 s budget - so the "hold at hover" collapses to **0.17 s**, the catch-up
runs out against its measured 200-tick / 200 mm reach budget, and the close starts
with the fruit **far past the pad centre** - left median **185.7 mm** (max 566.6),
right p90 **179.3 mm** (max 435.7) - against **3.6-3.9 mm** in B. B fires at 2.11 s,
hovers at 0.85 s, **waits 0.75 s for the fruit**, and closes on it at 3.6-3.9 mm. The
`wait`/`hover` stamps are taken from the handover's own start
(`tasks.py:8945`), so the fire -> handover dispatch sits between the columns and is
not logged; the **measured** miss is the `res` column, not this arithmetic.

**This is the same class W7-B named** (left no-contact 9 -> 1, close-start 88.8 ->
1.4 mm, pooled +11 pt at N=3), reproduced here on the **post-park** interface with
3.5x the n on the class readout. Two things are new: the **right** arm is where most
of the loss is now (12 of 26), and the ACQ-off rows include violent contact
(**F up to 754.9 N** at `contact=@0t`, the pads closing on belt geometry after the
fruit has gone).

## 5. E3 - a new failure reason? **FAIL on the letter** (one key, characterised)

`P54_report.txt` §6 strips the whole `intercept trigger (...)` stamp before keying
(the stamp carries `lead=..s/reach=..` **only** with ACQ on, so a raw key comparison
manufactures three fake "new reasons" - `113`'s own output shows exactly that). After
stripping:

| arm | failures | keys |
| --- | --- | --- |
| A | 29 | `fruit did not follow the gripper` **x26**; trigger-stamp only x3 |
| B | 11 | `fruit did not follow the gripper` x1; **`fruit fell off the line` x1**; trigger-stamp only x9 |

**B-only keys: `fruit fell off the line` (1/45).** The episode: **`B_2` ep4, a grade-A
kiwi on the left**, `bin=0`, 1434 ticks, reward 0, **no `[acq]` row at all** (the
direct capture never started). Its `[park] call` census reads **`x = 0.176 m`**, i.e.
**4 mm below the left arm's 0.180 m admission floor** measured in
`logs/p38/` phase 1 (`right >= 0.1730`, `left >= 0.1800`) - the fruit rode the belt
past the station and off the end before anything could fire. That is the **P38 supply
x-tail**, a scenario property the knob cannot reach: P38's census puts the sub-floor
delivered-x share at **0.31 % below 0.173 m and 0.77 % below 0.180 m of 653 direct
episodes**, and the resulting never-fired class at **2/3103 = 0.06 %** on the shipped
gate - so at 45 episodes per arm the expectation is **0.03-0.35 events** and **which
arm sees one is close to a coin flip**. A produced none (0/45).

**Verdict: E3 FAIL by the registered rule** (a key in B that A never produced), and
the event carries **no evidence about the knob** - it is the same tail P37's S3 gate
failed on, reached from the other side. It is **not repaired by widening the gate**
(P38 measured the reach residual at x = 0.16 as 8.3 mm, marginal) and it is **not**
retried here.

## 6. The left arm (reported, not an endpoint)

| arm | placed | cnp | never-held | catch-up res p50 | s/attempt |
| --- | --- | --- | --- | --- | --- |
| A | **1/17 = 5.9 %** | 2 | **14** | 187.4 mm | 16.26 |
| B | **0/10** | **9** | 1 | 5.7 mm | 15.80 |

**The left's failure class moves, its placement count does not.** With ACQ off the
left never grips (14 of 17 are acquisition misses with a 186 mm median close-start
offset); with ACQ=1 it grips and loses the payload in the carry - **9 of 10 are
carried-not-placed**, the class `logs/p42/SIM_LIMIT.md` closes (loaded slide; the
park's left-only vector is the P43 no-op, so the park never moves this arm). This is
the W7-B reading reproduced on the post-park tree: ACQ converts the left's
acquisition failures into the *closed* grip class, so the left's rate stays at 0-6 %
either way. **Do not read the left as an ACQ effect in either direction.**

## 7. What this does and does not mean

* **It does not touch the interface of record.** The hybrid canary
  (`scripts/60_eval_policy.py`) never constructs the direct env and never runs the
  trigger, so the recorded **5-8/10** canary spread and the shipped `moe_v12` path are
  unmoved by this phase (no code, no config, no default was changed).
* **It does not touch the scripted line.** Nothing in §2's numbers is a scripted
  number; the `[motion]`/`[fruit]` scripted path never reads the trigger settings.
* **It does label every pre-P54 direct number.** The park A/B (P43), the direct
  checkpoints (P33/P37/R9/W8-A), the P52/P53 cells and the ACQ A/Bs are **all ACQ=1**
  and stay valid *as ACQ=1*; what changes is that they can no longer be read as
  "the shipped direct configuration". A direct cell run with the shipped env resolves
  a **76 %-class** interface into a **36 %-class** one - a confound of the same size as
  the park lever itself.
* **It does not adopt anything.** R5 decision 4 kept `FRUIT_POLICY_TRIGGER_ACQ` off as
  a **measurement interface**, and R5-5 made the direct loop the mechanism-research
  interface; a default flip is an **owner decision**, not a measurement, and it is not
  taken here (no commit, `src/` and `configs/` byte-unchanged, §8).
* **The honest open question it creates** is therefore not "does ACQ help" (measured:
  it deletes a 57.8 % class) but **"should the shipped direct configuration be the one
  every direct baseline was measured in"**. The three options are the owner's:
  (a) flip ACQ on for the `direct` presentation (a default change, R5-4 revisited,
  needs its own no-harm: `accept.sh` + `accept_policy.sh` + both two-line gates);
  (b) keep ACQ off and **re-baseline the direct interface** (the 36 % class becomes the
  documented baseline, and every future direct A/B runs at ACQ=1 explicitly with a
  note that it is not the shipped config); or (c) make the fire budget explicit -
  the shipped `lead = 0.90 s` is **below the handover's own 1.17 s setup**, so *any*
  interface that runs this trigger at the shipped lead will show the class, ACQ or not.
  **This phase does not choose**; it publishes the two columns and the mechanism.
* **No rate claim beyond this interface**: the loop conditions on rendered frames and
  is not bit-reproducible (AGENTS §3b), so each per-seed cell is one draw; the class
  and mechanism columns are the measurements.

## 8. Falsifiers, pins, files

Registered falsifiers (`PREREG.md` §4): **F1** (the ACQ-off arm must not print
`acq=on`) - **passed**; **F2** (the fire lead must differ, else E2 is not evaluable) -
**passed**, 0.90 s fixed vs 2.11 s p50; **F4** (a wedge is a missing run, never a
silent retry) - **not triggered**, six runs complete, no wedge, no retry.

**F3 reads as a split, and the registration's own yardstick was imprecise - both are
recorded, neither is repaired in hindsight.** Its first clause (the shipped config's
rate is far outside the number it is on record as) **fired**: **right 53.6 % / pooled
35.6 %** against the record it is quoted as (**right 94.6 % / left 4.8 %**, both
ACQ=1) - reported as a **default-consistency defect** for the owner, not tuned. Its
second clause (below P43's own control by more than that arm's run-to-run spread) did
**not** fire: against **P43's pre-park control** (right 32/54 = 0.593, ACQ=1) the
shipped config sits within **~6 points**, well inside one sd at n = 28. And the clause's
first yardstick - the canary's 5-8/10 - was the **wrong comparison to register**: the
hybrid canary never constructs this interface, so its spread cannot bound a direct
rate. What the numbers actually say is the pair in the sentence above: this is **not a
regression against the pre-park interface**, it is **the loss of the park-era gain when
the knob it was measured with is removed** (park + ACQ=1 right 0.946; park + ACQ off
0.536; no park + ACQ=1 0.593 - three different branches, quoted as context, never as a
delta).

Pins before and after the batch (`logs/p54/p1/P1_header.txt`,
`P1_tree_md5_after.txt`): tree `c717de0`; `checkpoints/moe_v13s/policy_best.pt`
`61da390a`; `rl_env.py` **`a1ae217a`**; `tasks.py` **`b6de439c`**;
`policy/trigger.py` **`b09d3cb2`**; `configs/arm_parks.json` `42ab4fb7`;
`configs/motion_reference.json` `8a399626`; `..._twoline.json` `2246f83c` - **all
unchanged**, i.e. the arms differ only by the one env variable.

| artefact | md5 |
| --- | --- |
| `logs/p54/PREREG.md` | `f39620c566c83378d9d5c972032f349a` |
| `logs/p54/run_batch.sh` | `3ed62c4bf59258ad82f325e0748bf994` |
| `logs/p54/p54_report.py` | `25978644c608525c389b44c4ea3976e2` |
| `logs/p54/p1/P54_report.txt` | `055c3c985c6febcc00c5f4cf5fb1d09b` |
| `logs/p54/p1/P54_113_A_B.txt` | `b9c6e253d78f010e6befc67066cc548e` |
| `logs/p54/p1/P54_w7acq.txt` | `87044845a2c7fbada2fee52f0fe9304e` |
| `logs/p54/P54_RESULTS.md` | (this file; its md5 is in the WORKLOG hand-off, not in itself) |

`p54_report.py`'s header pin in `P1_header.txt` is `4dc32453` - that is the version the
batch started with; the three edits made **while or after the simulator ran** add the
`hover`/`wait` columns, flip the per-run delta sign to match E1 (`A - B`) and clean the
note-key quoting. They are **analysis-only** (the report reads finished logs), which is
why the batch's own `P54_report.txt` is regenerated from the final script above - and
the regenerated file's **E1/E2/E3 lines are unchanged** except the E3 key text losing a
stray apostrophe. Logs: `logs/p54/p1/{A,B}_{1,2,3}.log`, `batch_outer.log`,
`P1_header.txt`, `P1_tree_md5_after.txt`.

## 9. Named next items (not started here)

1. **The owner's decision on the shipped direct configuration** (§7, three options).
   Whatever it is, it needs its own pre-registration and no-harm set.
2. **The fire-budget arithmetic as a check, not a knob**: `lead 0.90 s` < the
   handover's 1.17 s setup is a **structural** mismatch on this interface; a
   `t_arrive >= wait` invariant would catch it in one line at the next interface
   change. Not built (it would be a `src/` change and this phase is env-only).
3. **The left's residual is unchanged** (0-6 % in both arms): it is the closed
   cnp class, not acquisition - the P42 `SIM_LIMIT.md` verdict stands.
4. **The `fruit fell off the line` tail** (1/45 here, x = 0.176 m < the left's
   0.180 m floor): still the P38b supply-margin item (a release floor >= 0.237 m),
   unstarted and unaffected by this phase.
