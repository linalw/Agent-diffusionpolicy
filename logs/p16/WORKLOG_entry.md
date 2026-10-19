### P16 (2026-10-19, branch `p-supply`, offline): the descent-boundary design — the diagnosis refresh (the shortfall is 8.1–15.3 mm and the solver closes it; the K1 "walk-is-settling" branch is refuted on the mass base), the three bounded options (the completed descent / the scene / the post-descent handoff), the pick (the completed descent), and the pre-registration sketch

**Scope: offline, read-only.** No simulator run; no `src/`/`scripts/`/`configs/`/`datasets/`/
`Paper/` write; no commit; writes only under `logs/p16/`. Tree pins as read: `tasks.py`
`810658b802d22bbd63013726fc78af81`, `fruits.py` `d28546d26137d4540421caa7fa34a139`, `meshes.py`
`0e32b1ad1830b04dc0a4bddadfc84a5f`. Deliverable: `logs/p16/BOUNDARY_DESIGN.md` (the diagnosis +
the options + the pick + the sketch + the constraints); this lane's tooling is
`logs/p16/descent_boundary_analysis.py` → `descent_boundary_tables.txt` (the `end=` rows, the
60-attempt hold-walk decomposition, the ejection/tracking/handoff reads, the R10 map
re-derivation; the class labels from the P14-B `master_table.md`).

**1. The diagnosis refresh (the mission's task 1).** (i) **The shortfall**: on the mass base
(60 descents) `end=` = **8.1–15.3 mm (median 9.2)** — seed 11 8.3–15.3 (9.4), seed 5 8.2–12.9
(8.9), seed 23 8.1–11.9 (8.9) — on a 5.5–5.9 cm hover→grip leg at `|v|max` 0.105–0.118, the aim
`station + 0.0170…0.0180`, the wait 50–88 ticks. The v1/static-line contrast (the AGENTS §2
record): 42–90 mm (`logs/161`/`160`), the integral bias 53 mm and worse `|v|max` (`logs/163`,
withdrawn), the soft gains unchanged (`logs/165`), the collision probe stopping the jaw at
z = 1.247 with the belt vs 23 cm without (`logs/166`/`167`). (ii) **The post-descent solver**:
the catch-up inherits a first-row residual of **11.1–61.7 mm (median 14.6)** — the tip 5–12 mm
above its desired z and ~12 mm downstream of the fruit — and closes it to **5.1–6.0 mm** in ~11
ticks; the R8-A note stands (the floor is the loop's threshold-crossing value). (iii) **The
hold-walk decomposition**: on the three hold-walk B1s (s11 attempts 1/7/9, all left) the hand's
own y motion is **−1.6 / −13.2 / +3.4 mm** while the fruit slides **−35.6 / −41.7 / −47.6 mm**;
the hand's x (+22.5…+34.0) is the bounded x-seek following the fruit's own squeeze-out (the
fruit's |vx| peak 0.185 m/s vs the oks' 0.071) and the hand's z (−8.5…−10.5) is a sag that
**grows with the slide** (z_err −1.9 mm at the freeze → −11.0 at the hold's end; the oks
−3.3 → −4.3). (iv) **The reach geometry**: the aim is **inside** the R10 clean bands (left
x=0.20 −0.10…+0.15, x=0.28 −0.05…+0.10, x=0.36 0.00…+0.10; right station-relative 0.00…+0.20 /
+0.15 / +0.10); the capture sweep leaves the band on almost every attempt **including the oks**
(the ok median margin −53 mm, the B1 −124, the carried −78 — overlapping, no separation); the
belt stop (1.247) is 10–38 mm below the grip aim (jaw z = fruit_z + 0.070) and the standoff axis
is closed both ways (S3 +20 negative at every seed, D2a −8 negative, −10 a jam).

**2. The K1 branch is refuted on the mass base (the design's decisive input).** The P15 §K1's
"the walk may be the hand's own descent-settling motion" does not obtain: the settling term is
secondary (10–35 mm of hand motion vs 28–51 mm of fruit slide), it is *downstream* of the slide
in time (the z sag grows with it), and the **handoff states of the failures are cleaner than the
oks'** — the post-descent residual B1 13.2–14.4 mm vs the oks' 11.1–61.7; the freeze z_err
−1.9 vs −3.3; the handoff's relative tip–fruit velocity puts all 5 B1s in the "matched" band
(−24…−30 mm/s) while the "at-rest" band (≥ +50 mm/s) holds 23 oks and only 3 fails (the 2×2:
matched 9/15 fails vs 18/45 oks; at-rest 3/15 vs 23/45). The walk is the **loaded slide** (the
B1s' fruit accelerates to |vy| peak 0.109–0.251 m/s during the hold, the oks arrest at a 0.078
median); the hand's motion is its **response**. The P15's screen had already shown the walk is
*movable* (M2 collapsed it) and the outcome traded; this lane adds that the walk is *not* the
settling — so the descent-boundary family's direct premise is weak before any run.

**3. The options, the ranking, the pick (tasks 2–3).** **(a) The completed descent** — after the
jerk-limited profile, hold the aim until the TCP error ≤ `FRUIT_DYNAMIC_ARRIVE_TOL` (0.006) or
`FRUIT_DYNAMIC_ARRIVE_MAX` (24 ticks) (a `src/` change, default-off, dynamic-capture-scoped) +
the `[arrive]`/`[boundary]` reporting rows. **(b) The pick station clear of the belt** — the
D3-proper form; the P12-B.2 derivation makes a raised deck catch-null (the catch is
fruit-relative); the bounded proxies (D2a/D2b/D3/S3) are measured negative; the S4 containment is
the only certain movement and is grip-null (the falls). **(c) The post-descent handoff** — a
sustained acquisition (`FRUIT_HANDOFF_ACQUIRE_TICKS`) + the `[handoff]` state row; its premise is
*directly* refuted by §2's handoff read. **Ranking: 1. (a), 2. (c), 3. (b).** The pick is **(a)**:
it is the only option that moves the mission's first mechanism endpoint — the descent's `end=`, a
quantity **no prior lever has ever moved** — and it is **upstream of the capture**, so a
conversion cannot trade by construction (the close/carry actuators' conserved mass came from
acting inside the capture window; a descent-side change hands the shipped carry its payload).

**4. The sketch (frozen in the doc §4).** The mass base verbatim + the trace; Stage M at SEED 11
(M0 the on-disk traced control; H1 = the pick; H2 = the handoff completion if the budget allows),
the promotion gate = the `end=` median ≤ 6 mm and the first-row residual ≤ 8 mm **and** the hold
walk into/below the ok ceiling (≤ 20 mm) on ≥ 2 of the three hold-walk attempts or the seed-11
no-grasp −2 with conversions, **and** the probe-1 departures/dz not worsening, **and** no new
failure reason (incl. the finger–belt jam) / no never-grasped growth; ONE promoted arm → the
outcome battery at SEED 11/5/23 (the no-grasp + the carried + the falls + the pooled outcome, the
doubles bit-identical); the kills K1–K5 (K1 = the mechanism gate: the `end=` moves but the walk
does not — close at M); the no-harm (the knobs unset: acceptance 9/10 + fingerprint, the two-line
dense re-record + `190`, selfcheck, the mass-base control replay). ~1.5–2 h Tier A solo.

**5. The honest constraints (task 4).** The standoff axis is closed both ways (S3 +20 negative at
every seed; D2a −8 negative; the −10 jam); the reach/aim family is excluded from the two-line and
measured negative on the single arm (R11-A 9/10 → 4/10; R11-A.1 4/9, the left post-catch hold);
the W2 catch lead traded the rate; the scene proxies fail (S1 catch-null by derivation, S5
infeasible, S2 the highest cost + the D3 supply risk); the close/carry actuators are saturated
(the P15's conserved mass: M2 45/60 → 38/60 with the carried 2/0/2 → 4/6/2; C1's never-grasped
0 → 5, reproduced 7 → 12); the boundary's owner-gated history stands (the R10-A "do not re-tune
the |v|max budget" note; the D3-proper gate; the AGENTS §2 "settle what the criterion should mean
with the owner"). **The strongest reason the pick could fail**: the premise is already partially
refuted by the pick's own control — the B1 failures' handoffs are *cleaner* than the oks' — so
the most likely Stage-M read is **the `end=` falls while the hold walk does not move**: K1 closes
the descent-boundary family with the measured negative (the shortfall does not feed the capture)
and the program's next candidates are the outcome-side residual (the carried class) or the
owner-gated D3-proper. A narrower mode: the arrival cannot be completed within the cap (the drive
settling, τ = 0.2 s) — also a definitive statement about the boundary on this cell.
