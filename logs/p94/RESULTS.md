# P94 RESULTS — the `_gripper_offset` jump is bounded; the carry is unchanged everywhere else

Registration: `logs/p94/PREREG.md` (md5 `4d793195…`, pinned before any run;
`logs/p94/PREREG.md5`). Battery: `logs/p94/run_p94.sh` →
`logs/p94/battery_driver.log`. Census: `logs/p94/census.py` →
`logs/p94/census.txt`. Readout: `logs/p94/p94_report.py` →
`logs/p94/p94_report.txt`, per-leg table `logs/p94/leg_table.txt`. Gates:
`logs/p94/gates.sh` → `logs/p94/*.budgets`.

**Verdict in one line: SHIPPED as a one-ternary correctness fix. The reading
`_gripper_offset` may now only be applied as a tool offset when it is one
(`FRUIT_CARRY_OFFSET_MAX`, 0.20 m shipped, `=0` restores the pre-P94 path bit for
bit); a commanded jump of 350 mm and one of 1211 mm become **0**, every leg below
the bound is verified unchanged (0 legs moved), three of the four seeds replay
their pre-fix records line for line, no seed loses a placement, and the scripted
single arm is 346/346 byte-identical.** The fix **converts nothing** — both
guarded legs stay `never_held` / `cnp` — and **no rate gain is claimed**: the two
+1 counts (seed 5 `16 -> 17`, the acceptance `7/10 -> 8/10`) are downstream
branch draws on moved attractors.

## 0. The defect, and the three sites that decide what it is

`_gripper_offset[side]` is written **once per grasp**, at the grasp routine's
entry: `rot.T @ (spawner.position(sample) - arm.tcp_position())`
(`tasks.py:11047`). That is a **tool** offset only while the pads sit on the
payload. When the fruit is far out at the entry it is the payload's **distance**,
and the number is then unbounded (measured 11-1211 mm on the phase's own cells).

| consumer of `_gripper_offset` | code | guard |
| --- | --- | --- |
| `_carry` coherent branch | `arm.tcp_target_for_jaw(centre)` when `hand_is_jaw` | **`hand_is_jaw`** |
| `_carry` **assisted** branch | `arm.tcp_target_for_jaw(centre - rot @ offset_tool)` | **none** ← the defect |
| `_carry` tail (30-tick settle) | `placed if hand_is_jaw else placed - rot @ offset_tool` | **`hand_is_jaw`** |
| `_place_low` lowering ramp | `if hand_is_jaw: ik_step(jaw0 …)` else the offset form | **`hand_is_jaw`** |
| `_release_lower` (v2 ordering, off on the raised line) | `follow_arm` refuses past `FRUIT_RELEASE_ARM_TRACK` = 0.20 m | a **0.20 m** bound |

Two facts make the site live on the shipped line rather than a corner case:

1. **The shipped hand takes the assisted branch on every leg.** `coherent` in
   `_carry` is `self._coherent[side]` (`:4966`), and that flag is only set `True`
   when the **pre-close** fingertip-to-fruit error is `<= 20 mm`
   (`:11302-11308`); on the OpenArm hand the fallback branch prints
   `openarm fingertips <N> mm from the fruit; closing anyway` and **does not set
   it**, so it keeps its previous value (initially `False`). Measured: `p92/C5`
   prints `fingertip-to-fruit = 58.3-64.3 mm` on 20/20 attempts and
   **1638/1638** `[diag] carry-assist` rows across the P91-P93 corpus
   (531 + 639 + 468) read `coherent=False`.
2. **The documented reset is dead code.** `if not coherent:
   self._gripper_offset[...] = [0, 0, wrist_back]` (`:11609-11622`) sits **inside
   `if coherent:`** (`:11054`), so it never executes and the raw
   payload-minus-TCP value is what the carry reads. Reported, **not** repaired:
   moving it would set a *different* offset on every leg, i.e. it is Form A by
   another route (§8).

## 1. The fix

One site, one ternary, one resolver:

```
issued jaw target = centre - rot @ offset_tool      if  |offset_tool| <= BOUND
                    centre                           if  hand_is_jaw and |offset_tool| > BOUND
```

* `BOUND = tasks.parse_carry_offset_max()` → `FRUIT_CARRY_OFFSET_MAX`, **unset =
  0.20 m** (shipped), `=0` = off = the pre-P94 expression bit for bit.
* The bound is **not a new constant**: `0.20 m` is `FRUIT_RELEASE_ARM_TRACK`'s
  own pad/arm-relation threshold, already in code at `_release_lower`
  (`:14052-14058`).
* Scope: `hand_is_jaw` **only**. The kinematic-pad hand keeps its offset at every
  magnitude — for it the number really is a tool offset.
* The fallback is the same `hand_is_jaw` command the coherent branch and the
  `_carry` tail already issue: the pads.
* The diag row is unchanged in shape and now prints the **issued** target, so the
  census reads the *applied jump* (`|jaw_target - cmd_centre|`) from either arm's
  records with no new field.

**Why a bound and not the unconditional guard.** The unconditional form
(`hand_is_jaw` → `centre` on every leg) would move all 142 legs by their own
11-117 mm reading, i.e. re-calibrate the carry and make the defect's removal
unattributable on a 20-attempt cell. That is why the PREREG pinned **F1** (a leg
below the bound must not move) — and it is the reason this fix is shippable at
all (§5). The unconditional form stays the registered replacement (§8).

## 2. Admissibility: the tree was the control, and the flip is the measured arm

| pair | reading |
| --- | --- |
| `N5` (unset, pre-flip tree = `0`) vs `p92/C5` | **1033/1033** `[fruit]` lines identical |
| `P5_preflip` (unset, pre-flip tree) vs `p92/C5` | **1033/1033** identical (a second, independent replay) |
| `P5` (unset, **post-flip** tree) vs `T5` (explicit `0.20`) | **974/974** identical |

So: the pre-fix tree reproduces the control record, and after the default flip
the *unset* tree is byte-identical to the measured arm. The flip is
resolution-only — the shipped default **is** the arm the battery measured.

## 3. E1 — the commanded-jump census (primary)

`read` = the `_gripper_offset` the carry saw; `applied` = `|jaw_target -
cmd_centre|`, the distance the carry actually commanded the arm from the pads.

| cell | seed | placed | legs | read p50 | read max | above 200 mm | applied max | guarded |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C5 | 5 | 16/20 | 36 | 33 | 350 | 1 | **349.6 mm** | 1 |
| **T5** | 5 | **17/20** | 37 | 25 | 1211 | 2 | **63 mm** | 2 |
| C6 | 6 | 12/20 | 33 | 23 | 117 | 0 | 117 mm | 0 |
| **T6** | 6 | **12/20** | 33 | 23 | 117 | 0 | 117 mm | 0 |
| C101 | 101 | 15/20 | 38 | 23 | 46 | 0 | 46 mm | 0 |
| **T101** | 101 | **15/20** | 38 | 23 | 46 | 0 | 46 mm | 0 |
| C202 | 202 | 15/20 | 35 | 21 | 96 | 0 | 96 mm | 0 |
| **T202** | 202 | **15/20** | 35 | 21 | 96 | 0 | 96 mm | 0 |

**The invariant holds on every leg of every treatment cell**: the largest applied
jump is **117 mm** (T6, and that is an unguarded leg's own reading), and every
leg whose reading is above the bound reads **applied = 0**.

**The guarded legs** (the reading above the bound), with the arm's own motion
(`|v|max`/`|a|max` from the `[motion] carry` row — never the in-hand number):

| leg | reading | applied | class | arm `|v|max` | arm `|a|max` | `a_win5` | `res_end` | `tilt_max` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T5 att 1 `left grasp_lift` (kiwi) | 350 mm | **0** | `never_held` | **0.270** (was 1.108) | **1.99** (was 9.47) | **1.42** (was 9.13) | 60.0 mm (was 81.7) | 27.9° (was 58.3) |
| T5 att 10 `right grasp_lift` (kiwi) | 1211 mm | **0** | `cnp` | 0.309 | 1.95 | 0.64 | 80.0 mm | 20.9° |

The 1211 mm leg is the **second sighting of P93's class** — it appears at a
different seed and arm, on the branch the first guarded leg moved into, and it
has no pre-fix counterpart (the stream had already diverged). It is the phase's
best argument for shipping: the defect recurs, and the fix bounds it wherever it
appears.

**F1 (the registered falsifier): 0 legs below the bound moved.** The per-leg
table (`logs/p94/leg_table.txt`, 183 lines) pairs every leg of every seed on
`(attempt, arm, leg, fruit)` and reports `read c/read f/applied c/applied f`;
every row below the bound reads `unchanged`, and the only two `GUARDED` rows are
the two above.

## 4. E2/E3 — the classes and the placed count at the four seeds

| seed | placed (control → fix) | `cnp` | `never_held` | reason keys |
| --- | --- | --- | --- | --- |
| 5 | **16/20 → 17/20** | 2 → 2 | 2 → 1 | `fruit did not follow the gripper` only |
| 6 | **12/20 → 12/20** | 7 → 7 | 1 → 1 | same |
| 101 | **15/20 → 15/20** | 5 → 5 | 0 → 0 | same |
| 202 | **15/20 → 15/20** | 3 → 3 | 2 → 2 | same |

**No seed loses a placement; no class rises; no new failure reason** (E7). Seed 5
gains one, and it is **not** a conversion of a guarded leg: that leg stays
`never_held` in both arms, and the +1 is a downstream draw on the moved branch
(the acceptance, §6, shows the same shape - the guarded leg stays `never_held`
and one *other* attempt's `cnp` becomes a placement).

The three seeds with no leg above the bound are **byte-identical to their
controls end to end**, which is stronger than "no class moves": the fix cannot
act, so nothing did.

## 5. E4 — the delivered side (report only, no gain claimed)

| cell | ok | interval | p90 | window | batch | wall | wall/pick | wall/min | sim | w/sim |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C5 | 16 | 10.59 | 17.8 | 5.66 | 5.05 | 330.1 | 16.5 | 2.91 | 190.1 | 1.74 |
| T5 | 17 | 9.37 | 18.2 | 6.40 | 5.63 | 323.7 | 16.2 | 3.15 | 181.1 | 1.79 |
| C6 | 12 | 11.08 | 17.6 | 5.41 | 3.94 | 304.0 | 15.2 | 2.37 | 182.6 | 1.66 |
| T6 | 12 | 11.08 | 17.6 | 5.41 | 3.94 | 308.3 | 15.4 | 2.34 | 182.6 | 1.69 |
| C101 | 15 | 12.16 | 22.5 | 4.93 | 4.87 | 334.6 | 16.7 | 2.69 | 184.8 | 1.81 |
| T101 | 15 | 12.16 | 22.5 | 4.93 | 4.87 | 330.6 | 16.5 | 2.72 | 184.8 | 1.79 |
| C202 | 15 | 11.53 | 18.9 | 5.20 | 4.98 | 310.1 | 15.5 | 2.90 | 180.6 | 1.72 |
| T202 | 15 | 11.53 | 18.9 | 5.20 | 4.98 | 310.1 | 15.5 | 2.90 | 180.6 | 1.72 |
| N5 | 16 | 10.59 | 17.8 | 5.66 | 5.05 | 331.1 | 16.6 | 2.90 | 190.1 | 1.74 |
| P5 | 17 | 9.37 | 18.2 | 6.40 | 5.63 | 323.3 | 16.2 | 3.15 | 181.1 | 1.79 |

Seeds 6/101/202 have identical intervals and both denominators to the control
(same stream); their wall differs by **-1.5 % / +1.2 % / 0.0 %**, i.e. harness
noise on an identical run. Seed 5's better interval and rate are the moved
branch's, not the fix's: the guard acts on **one** leg of 37 and that leg still
fails. **No throughput claim is made** (PREREG §4 E4).

## 6. E6 — the scripted line is shared, and the acceptance's own A/B names the leg

The carry code is shared, not two-line-only: the scripted single arm runs the
same assisted branch (`logs/p83/D5.log`: 114 `carry-assist` rows, all
`coherent=False`, readings 11-44 mm). Pre-run census of 48 scripted logs / 950
readings: p50 26 mm, p99 81 mm, max 351 mm, **2 above 0.20 m**.

**The acceptance moved, and the movement is the guard's alone.** Two runs at the
same scenario and seed, `FRUIT_CARRY_DIAG=1` on both arms:

| arm | placed | `cnp` | `never_held` | legs | above bound | applied max | fingerprint |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `FRUIT_CARRY_OFFSET_MAX=0` (pre-fix) | **7/10** | 2 | 1 | 17 | 1 (350 mm) | **349.6 mm** | **matches `423896f7`** (the record) |
| unset (fix) | **8/10** | 1 | 1 | 18 | 1 (350 mm) | **48.2 mm** | moved (the guarded leg's branch) |

**Prefix identity: 110/492 `[fruit]` lines common, first difference at 110 = the
guarded row itself** (attempt 1, `left grasp_lift`, kiwi, 350 mm — the same leg
as the seed-5 two-line cell). The pre-fix arm *reproduces the reference
fingerprint and the recorded 7/10*, so the acceptance's movement is the flip's,
not a tree change.

**The single arm is inert**: `FRUIT_BIARM=0 scripts/accept.sh` reads **6/9**,
`fingerprint: matches configs/motion_reference_single.json`, and its **346
`[fruit]` lines are byte-identical (346/346)** to `logs/p71/accept_rails_none.log`.

**References re-recorded (both two-line-side files, as the tree's arrangement
requires):** `configs/motion_reference.json` `423896f7` → **`30fb99f8`** and
`configs/motion_reference_twoline.json` `423896f7` → **`30fb99f8`**, both from
`logs/p94/accept_p94.log`; the pre-P94 pair is archived at
`logs/p94/motion_reference_pre_p94.json` and
`logs/p94/motion_reference_twoline_pre_p94.json`.
`configs/motion_reference_single.json` `8952c320` is **untouched**. The final
acceptance on the shipped tree reads **8/10, `fingerprint: matches`, `190: PASS`**
(`logs/p94/accept_final.log`, **420/420** `[fruit]` lines identical to the
reference-source run `logs/p94/accept_p94.log`).

## 7. E5 — the motion budgets

`scripts/105_motion_regression.py --min-success-rate 0.0` per cell
(`logs/p94/gates.sh`, `logs/p94/*.budgets`); the fingerprint clause is recorded,
never gated (every 20-attempt two-line reference predates P87's clock).

| cell | descent legs | over budget | worst cone |
| --- | --- | --- | --- |
| C5 / **T5** | 20 / 20 | **0 / 0** | 1.57x / **7.10x** |
| C6 / **T6** | 20 / 20 | **1 / 1** (leg 12, `0.164/0.160`, +2.5 %) | 1.69x / 1.69x |
| C101 / **T101** | 20 / 20 | **1 / 1** (leg 9, `0.224/0.160`, +40 %) | 1.28x / 1.28x |
| C202 / **T202** | 20 / 20 | **0 / 0** | 5.49x / 5.49x |

**No treatment cell has more over-budget descents than its own control, and no
over-budget leg is a guarded leg.** The two over-budget legs are the control's
own (C6 leg 12 = the standing P86/P87/P88 branch leg; C101 leg 9 = a *control*
excursion P93 already recorded). The budget was **not** re-tuned (AGENTS §2).

**T5's 7.10x cone is the guarded 1211 mm leg** (`right grasp_lift`, 247 ticks):
its payload had already left the line — the reading is 1.19 m in tool z, i.e. the
kiwi was ~1.2 m *below* the TCP at the grasp's entry — so the leg's
`|a|max 91.8 m/s²` at tick 0.09 is an impact, not a commanded jump, and its
`res_end` is **80 mm** (a 1.2 m flight would read ~1.2 m). The cone is *reported*
on this line, never gated (AGENTS §2).

## 8. The decision rule, applied (PREREG §5)

| clause | reading | verdict |
| --- | --- | --- |
| (a) the invariant on every leg of every cell + F1 | applied max 117 mm (< 200) on treatments, **0** on both guarded legs; **0 legs below the bound moved** | **PASS** |
| (b) no seed loses a placement | 16→17, 12→12, 15→15, 15→15 | **PASS** |
| (c) no class rises / no new reason | `cnp` 2→2, 7→7, 5→5, 3→3; `never_held` 2→1, 1→1, 0→0, 2→2; one reason key everywhere | **PASS** |
| (d) no budget regression | 0/0, 1/1, 1/1, 0/0; no over-budget leg is a guarded leg | **PASS** |
| (e) acceptance + single arm unchanged | acceptance **moves first at the guarded row** (110/110 prefix, 7/10 → 8/10, no placement lost); **single arm 346/346 identical**, `matches` | **PASS** (E6's prefix rule) |
| (f) F2 prefix identity | seed 5 prefix holds at the guarded row (111/111); seeds 6/101/202 **inert end-to-end** (970/970, 1001/1001, 986/986); post-flip `P5` = `T5` 974/974 | **PASS** |

**→ SHIPPED.** `FRUIT_CARRY_OFFSET_MAX` defaults to **0.20 m**;
`=0` restores the pre-P94 path. `scripts/251_p94_offset_selftest.py` pins the
resolver table, the single site, the jaw-hand scope, the two branch expressions
(executed) and the diag row's issued target; `scripts/236` was re-pinned for the
new `_jaw_target` operand (its meaning kept: the assist branch records the exact
array `ik_step` was handed).

## 9. What this phase does **not** show

1. **It is not a rate lever.** It acts on 1-2 legs per 80 attempts, and both
   guarded legs stay failures. The two +1 counts are moved-branch draws
   (`16 -> 17`, `7/10 -> 8/10`) and carry no claim; they are reported because the
   ship rule forbids a *loss*, not because they are evidence.
2. **It does not re-calibrate the 11-117 mm offset.** The assisted branch still
   commands `centre - rot @ offset_tool` on every leg inside the bound, while the
   same leg's *tail* (`:6087`) commands the pads — an internal inconsistency of
   the order of the reading itself. That is **Form A**, registered and **not run**
   (it would move all 140-odd legs).
3. **The dead-code reset** at `:11609-11622` stays dead (`if not coherent:`
   inside `if coherent:`). Fixing it is Form A by another route.
4. **The 1211 mm reading's cause is not diagnosed.** Its payload was ~1.2 m below
   the tool at the grasp's entry — a supply/depenetration event upstream of the
   carry (P93's own open item, `logs/p93/RESULTS.md` §1a). This phase bounds the
   *command* that event produced; it does not explain the event.
5. **No `clr`/`clr_edge`/landing regression is claimed or measured** beyond the
   usual `[motion] carry clearance` rows: the landing guard was not part of this
   phase's battery (nothing in the fix touches the release).

## 10. Pins and evidence

The battery ran on a **dirty tree of exactly two files** - `tasks.py` `de9abd5a`
(the fix, `FRUIT_CARRY_OFFSET_MAX` resolving **off** until the flip) and
`rl_env.py` `1d30563b` (the `TASKS_MD5` follow) - which is what the header
records (`logs/p94/header.txt`, `dirty=2`); every other pin is the P93 tree.
**Shipped** (post-flip) tree: `tasks.py` **`19cd4028`** (default `0.20`),
`rl_env.py` **`4149fab4`**, `bimanual.py` `9b7fc33f`, `fruits.py` `dcabe16b`,
`scene.py` `3681aad3`, `assets.py` `eb30c77a`, `control.py` `9384ff4f`,
`conveyor.py` `fb2c58c6`, `scripts/selfcheck.sh` `d62a8a2f`,
`scripts/accept.sh` `5399bff1`; `configs/motion_reference.json` =
`..._twoline.json` = **`30fb99f8`**, `..._single.json` **`8952c320`**; checkpoint
`moe_v13s` `61da390a`.
New instruments: `logs/p94/census.py` `3018225710`, `logs/p94/p94_report.py`
`be0b662d`, `logs/p94/gates.sh` `2689fd10`, `logs/p94/PREREG.md` `4d793195`,
`scripts/251_p94_offset_selftest.py` `7f36da77` (selfcheck leg),
`scripts/236_p66_lift_selftest.py` `80f67e4a` (re-pinned). Evidence: `logs/p94/{PREREG.md,PREREG.md5,census.txt,
p94_report.txt,leg_table.txt,header.txt,battery_driver.log,gates.sh}`,
the ten cells `{C5,T5,C6,T6,C101,T101,C202,T202,N5,P5}.{log,stamps,driver}` +
`P5_preflip.*`, `{C,T}*.budgets`, `smoke.log`, `accept_p94.*`,
`accept_single_p94.*`, `accept_ab_pre.*`, `accept_ab_fix.*`, `accept_final.*`,
`motion_reference{,twoline}_pre_p94.json`.
