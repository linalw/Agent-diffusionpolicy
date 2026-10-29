# P60 phase 3 — the direct left is the **closed grip class** (seated then slid), not a take-off seating defect

**Verdict (registered endpoints, `logs/p60/PREREG_P3.md`).** With the `[carry]`
onset instrument armed on the shipped direct profile, **19 of 19 left
`carried-not-placed` failures are `seated_then_slid`**: the payload is between
the pads, in contact, at carry level (**`force@onset` p50 10.06 N
[2.44-22.58]**, `contacts@onset` 1 on 14 and 2 on 5), for **65 % of the lift leg
on median** (`onset_row` p50 104 of ~160 ticks), and the escape is a mid-lift
contact loss (`force_min = 0.00` and `loss_row` set on **17/19**; the other two
slide 16.6 / 26.2 mm and are lost at the transfer's start). **`never_seated` on
the lift is 0/19**, so the "never properly seated at take-off" object does not
exist on this line. The signature is **the scripted comparator's, field for
field** (scripted left: 4/4 escapes `seated_then_slid @grasp_lift`, onset
93-149, force 7.68-18.19 N), and it reproduces on an independent 40-attempt
direct-left corpus (P43: **38/38** `seated_then_slid @grasp_lift`).
**Consequence: the direct left's loss is the object `logs/p42/SIM_LIMIT.md`
closes** (the loaded slide on this pad geometry); this instrument opens no new
lever, and the "seat it better" family stays closed.

The single most important reading rule, and the reason the brief's comparator
row looks like "never seated": **the `place0` row is the downstream view.** The
cited scripted row (`left place0: onset_row=2 contacts@onset=0 force@onset=0.00N`)
belongs to an attempt whose **lift** row reads `onset_row=93 contacts@onset=1
force@onset=12.12N ... loss_row=127` — the payload was held for 93 of 163 ticks
and left mid-lift. On this cell the same structure appears on **18 of 19** cnps
(their `place0` row starts at tick 1-6 with `contacts@onset = 0`), which is
exactly what a payload already gone at the transfer's start must print.

---

## 1. The cell, and what the instrument did (P1)

3 seeds x 15 picks, one claim per run, the shipped direct profile, `moe_v13s`
`61da390a`, `FRUIT_CARRY_DIAG=1` only (PREREG §2). Logs
`logs/p60/p3/D_{77,101,202}.log`; driver `logs/p60/p3/run_p3.sh`; batch
09:02:54-09:31:25, **3/3 exit 0, no wedge** (F1 unused).

| read | value |
|---|---|
| episodes | 45 (15 per seed) |
| `[carry]` rows | **88** (left 41 / right 47); every left attempt 21/21 has >= 1 row |
| fields on every row | `onset_row` 88/88, `contacts@onset` 88/88, `force@onset` 88/88, `clean_slip_max` 88/88 |
| the knob actuated? | **no** — `guard=0 events=0 holds=0 reseat=0.0mm relief=0` on **88/88** rows (`FRUIT_CARRY_GUARD` / `FRUIT_CARRY_RELIEF` unset) |
| default-off proof | `[carry]` rows in the P59-p3 control, P58-p3a and P59-p2 corpora: **0 / 0 / 0** |
| wall | 9.5 / 9.6 / 9.4 min per run against the control's 9.1 / 9.5 / 9.3 — **no measurable diag cost** |
| scenario echo | `trigger=arrival lead=0.90 ... acq=on`, `park=back(default)`, `[supply] direct profile: cadence=on(default) band=on(4)(default) feed=on(default)` |

**P1 passes with no named exception**: no left attempt lacked a row. The one
`never-held` left attempt (below) printed a single aborted `grasp_lift` row. (The
P43 context corpus does contain the exception in the other direction — 2 of its
110 right attempts, **both `never-held`**, printed no carry row at all — so the
"row absent" case exists, it just did not occur on this cell; `report.py` buckets
such attempts as `no_row`, never as `no_slip`.)

## 2. The split (P2)

| arm | n | placed | cnp | never-held |
|---|---|---|---|---|
| left | 21 | **1** | **19** | 1 |
| right | 24 | **23** | 0 | 1 |
| pooled | 45 | **24** | 19 | 2 |

Per seed (left, placed/cnp/never-held): 77 `0/8/0`, 101 `1/7/0`, 202 `0/4/1`.

**The left's cnps, by the onset signature of their first escaping leg** (PREREG
§3.4):

| signature | left cnp | left placed | left never-held |
|---|---|---|---|
| `seated_then_slid` (contacts >= 1, force >= 2 N) | **19** | 0 | 0 |
| `marginal_contact` (contacts >= 1, force < 2 N) | 0 | 0 | 0 |
| `never_seated` (contacts = 0) | **0** | 0 | 1 (the aborted lift) |
| `no_slip` (no 2 mm event) | 0 | **1** | 0 |

The 19 cnp first-escaping legs, all `grasp_lift`: `onset_row` **p50 104
[71-142]** (leg length p50 160; **65 % [45-85 %] elapsed**), `force@onset`
**p50 10.06 N [2.44-22.58]**, `contacts@onset` 1 (14) / 2 (5), `clean_slip_max`
**p50 171.2 mm [16.6-519.0]**, `force_min = 0.00` 17/19, `loss_row` set 17/19.
**Threshold sensitivity (PREREG §3.3):** >= 1 N 19/19, >= 2 N 19/19, >= 3 N
18/19, >= 5 N 18/19 — the verdict does not depend on the 2 N bar. No onset is a
contact spike (max 22.58 N).

The two `force_min > 0` legs are `D_101` ep 0 (apple: 16.6 mm slip, `force_min`
3.16 N, then `place0` `seated_then_slid` onset 102, `loss_row` 117) and `D_101`
ep 14 (kiwi: 26.2 mm, `force_min` 1.43 N, lost at `place0` tick 2). Both are
still *in the hand and sliding* at the lift's end — not "never seated".

**The controls.** Left **placed** (1: kiwi, `D_101` ep 3) reads `no_slip` on both
legs (`clean_slip_max` 0.0 mm, `force_min` 9.57 / 9.46 N). Right **placed** (23)
read `no_slip` 19/23 and a transient 4/23 (`clean_slip_max` 2.6-11.3 mm,
`force_min` 1.50-6.58 N, `lost` **0/4**; three of the four onset forces are
sensor spikes 35-61 N, flagged in the report). So the instrument separates the
classes on this cell: the left's escapes run 16.6-519 mm and **17/19** lose
contact (`force_min = 0.00`), while the right's transients run 2.6-11.3 mm and
**0/4** do — the W8-B split (clean 0.02-1.43 mm, escapes 17.9+).

**The left `never-held`** (1: lychee, `D_202` ep 3) is the phase-1 §5 class, not
a carry object: its single aborted `grasp_lift` row reads `never_seated`
(`contacts@onset = 0`, onset row 1) with no place leg — the pre-contact / +x
reach-cliff case.

## 3. The comparator (P3): the direct left **matches** the scripted left

Scripted left, `logs/p41/p2/accept_profile.log` (the file the brief names; its
trace twin is identical):

| scripted left attempt | outcome | lift leg | `place0` leg |
|---|---|---|---|
| 0 | escape | onset 93, contacts 1, F 12.12 N, fmin 0.00, loss 127 | onset 2, contacts 0, F 0.00 |
| 1 | escape | onset 127, contacts 2, F 7.68 N, fmin 0.08 | onset 83, contacts 2, F 10.10, loss 104 |
| 2 | **placed** | onset 70, contacts 2, F 10.43 N, fmin 2.36, slip 20.0 mm | **no_slip** |
| 3 | escape | onset 130, contacts 1, F 18.19 N, fmin 0.00, loss 145 | onset 3, contacts 0, F 0.00 |
| 4 | escape | onset 149, contacts 1, F 8.03 N, fmin 0.00, loss 161 | onset 3, contacts 0, F 0.00 |

**Scripted left: 4/4 escapes `seated_then_slid @grasp_lift`; the placed one is a
20 mm transient with no loss and a clean `place0`. Direct left: 19/19 cnps
`seated_then_slid @grasp_lift`; the placed one is `no_slip`.** Same signature,
same leg, same failure shape. Across all five scripted-left files in
`logs/p41/p2/` the lift row is `seated_then_slid` **24/24** and the `place0` row
is `never_seated` **14/22** — i.e. the scripted line has *always* been a
seated-then-slid failure viewed through a transfer-leg row (`accept_profile`,
`accept_profile_trace`, `accept_preprofile`, `accept_preprofile_trace`,
`pear_profile` — 10, 10, 7, 7 and 12 left rows respectively). The other two named
directories carry **no** `[carry]` rows at all (`logs/p58/p3a` 0, `logs/p59/p3`
0), which is why the phase-1 census could not make this comparison.

One bookkeeping correction to the brief's framing: the scripted acceptance
`logs/p41/p2/accept_profile.log` places **6/10 overall** but its **left lane is
1/5** (right 5/5), so the like-for-like comparator is "scripted left 1/5 vs
direct left 1/21", not "6/10 vs 2/20".

## 4. Independent corroboration (context, not an endpoint)

`logs/p43/p3/{A,B}_*.log` (N = 5 x 15 per arm, `FRUIT_CARRY_DIAG=1` on both
arms, post-P41 profile, **pre-P58 burst supply**, tree pins `rl_env.py`
`0cefb13d` / `tasks.py` `a1b3d673`) — pooled left **40 attempts: 1 placed, 38
cnp, 1 never-held; 38/38 cnp `seated_then_slid` with the first escaping leg
`grasp_lift`**, onset p50 27.5, `force@onset` p50 8.35 N. The same corpus shows
the instrument discriminates by configuration as well: the **unparked right**
(A arm) has 20 cnps, **20/20 `seated_then_slid`**, while the **parked right**
(B arm) has **0** cnps and 53/53 placed with `no_slip`. So the class is the
arm-agnostic loaded slide that P43's park removed on the right — the direct left
has no park vector and no other lever from this family.

This corpus is **declared in advance as context only** (different supply
profile, different pins); the registered endpoints are §1-§3.

## 5. Instrumentation and failure reasons (P4, F3)

* **P4 — no new failure reason.** `113_rl_report.py`'s digit-normalised note
  keys are **identical** to the control, cell = control: `intercept trigger
  (...)` 45 + `fruit did not follow the gripper` 2 (the two never-held). Placed
  counts are reported only: **24/45**; no rate claim (the direct loop conditions
  on rendered frames and is not reproducible).
* **F3 fires, formally.** Class counts differ from the P59-p3 control
  (diag off, same scenario/tree pins): left **1/19/1 (21)** vs **2/17/1 (20)**,
  right **23/0/1 (24)** vs **24/0/1 (25)**, pooled placed **24/45** vs **26/45**.
  The difference is one left placement and one right episode — and it cannot be
  attributed to the diag: the direct loop is not reproducible, and the diag's own
  added work is **one `tcp_pose()` + one tactile read per carry tick**, i.e.
  exactly the per-tick link-read class `AGENTS.md` §2 records as outcome-moving.
  So this is an **instrumentation-or-branch** effect, quoted as such, and no
  delta is claimed. It does not touch P1/P2/P3, which read the rows, and the
  signature is uniform within the cell and reproduces on a diag-on corpus of a
  different scenario (§4).

## 6. What this settles, and what it does not

**Settled.** The phase-1 alternative is resolved in favour of **O1**: the direct
left's carry loss is the **closed grip class** (`logs/p42/SIM_LIMIT.md`'s loaded
slide), at **19/19** of its cnps, with the scripted line's own onset signature.
The "never properly seated at take-off" hypothesis is **refuted on the lift leg**
and survives only as the downstream `place0` artefact. The left's deficit is
therefore **not** a seat/close-timing defect, and the family the record already
closed by measurement (force, seat, gripper geometry, and the P41 profile) is the
family this instrument re-confirms — **no new object is opened, and the seat
family stays closed**.

**Not shown.** (a) *Why* the left loads the slide at the census's **47x** rate
ratio (58/69 vs 2/111; on this cell 19/21 vs 0/24): this cell cannot separate the
**arm** from **lane 0 / grade A** (the direct env maps `grade A -> bin 0 ->
left`, phase 1 §6), and the gripper asset is shared by both hands — a
discriminating battery needs a code change (an explicit active-arm override) or
the two-line's right station, not another diag. (b) The
`force@onset` is a **single-tick contact-sensor sample** (three placed right legs
read 35-61 N spikes), so the numbers are quoted as orders of magnitude and the
classification's threshold sensitivity is reported (§2) rather than a precise
carry force. (c) The P43 context corpus is a different supply profile; it
corroborates the signature, not the rate.

**Named next, if the arm/lane question is ever wanted:** the phase-1 §7 item 3 —
an explicit active-arm override for a diagnostic battery (no existing knob
decouples arm from lane/grade). Nothing in this phase moves a shipped default.

## 7. Reproduce / provenance

```bash
bash logs/p60/p3/run_p3.sh                      # 3 claims, ~28.5 min
python3 logs/p60/p3/report.py --check           # -> logs/p60/p3/P3_report.txt
```

`report.py` prints the per-leg evidence table for both arms, the split, the
comparator, the P43 context and the F3 table, and `--check` re-asserts 15
invariants (15 episodes per log, every cnp attempt ran a carry leg, every
escaping leg classifies, **and the diag did not actuate**) — **all PASS**.

Pins: `logs/p60/PREREG_P3.md` **4434578c** as registered (**1f7d0e2f** with
Amendment A1, bookkeeping only), `logs/p60/p3/run_p3.sh` **1b9647f4**,
`logs/p60/p3/report.py` **3ea12351**, `P3_report.txt` **e1728c18**,
`D_77.log` **d3070b23**, `D_101.log` **af8c7044**, `D_202.log` **8f315da5**,
`header.txt` **0ab01bfc**; tree HEAD **70b6d1f**; `rl_env.py` **1b1e5cdf**,
`tasks.py` **8ad8ddc8**, `fruits.py` **c7461d41**, `policy/trigger.py`
**b09d3cb2**, `configs/arm_parks.json` **42ab4fb7** (identical before and after
the batch, `tree_md5_{before,after}.txt`), checkpoint `moe_v13s` **61da390a**,
`scripts/110_rl_rollout.py` **abd2b5f1**. **No `src/`, `configs/` or `scripts/`
edit; no default change; no commit.** `FRUIT_CARRY_DIAG` stays default **off**.


## P60 gate-3 correction: the offset is not the term (added after review)

The census's `|dx| <= 66 mm` split was read from the left's **observed placed max at
n = 7** and must never be quoted as a tolerance. This cell refutes it as a term:
**the single left placement is at `dx = -11.7 cm = 117 mm`** (`p3/D_101.log`), i.e.
**outside** the "ceiling", and **4 of the 19 cnps sit inside 66 mm**. What the split
describes is a sample, not a boundary.
