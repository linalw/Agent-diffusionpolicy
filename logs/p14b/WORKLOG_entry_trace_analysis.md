### P14-B trace-run analysis (2026-10-19, branch `p-supply`, offline): the per-tick corpus on the mass base separates the no-grasp class (ok 0.0–27.2 mm vs no-grasp 294.8–95 403.7 mm) and phase-localizes it — the loss is a failed capture transient in the hold / at the probe's lift, the re-seat windows never eject a held payload (F1 confirmed), so the re-seat floor is dead and the close/hold family (R11-B C1 first) is the selected lever

**Scope: offline, read-only.** The three trace runs (`logs/p14b/{10_seed11,11_seed5,12_seed23}_trace.log`
+ `traces_s11/`, `traces_s5/`, `traces_s23/`, 20 attempts each) were already executed by the P14-B
run lane; this lane analysed them, ran no simulator, and wrote only under `logs/p14b/` (no
`src/`/`scripts/`/`configs/`/`datasets/`/`Paper/` write, no commit, the running P14-A canaries not
touched). Tree pins as read: `tasks.py` `810658b802d22bbd63013726fc78af81`, `fruits.py`
`d28546d26137d4540421caa7fa34a139`. The design executed: `logs/p14b/GRIP_DIAGNOSTIC.md` §2.

**1. The corpus and the no-harm re-test.** The three runs are the mass base
(`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1` + balanced
A:B:C + `FRUIT_PHYSICS_REAL_MASS=1`, `ATTEMPTS=20`) + `FRUIT_DYNAMIC_TRACE=1` at SEED 11/5/23:
**45 ok / 7 carried / 8 no-grasp** (B1 5: seed-11 a01 orange, a06 tomato, a08 orange, a13 tomato
+ seed-23 a02 strawberry; B2 3: seed-11 a02 peach, a04 tomato, a07 tomato) — the §1.1 census
exactly. **The trace-on runs replay the mass base byte-identically**: all `[fruit]` lines
identical to `logs/p12a2/{10_seed11,11_seed5,12_seed23}_mass.log` (950/1047/1084 lines, exact,
including the `sim=` values; the only extras are the `[trace]` rows). Wall overhead +7–8 s
(~1.5 %); the simulated branch is unchanged — the W5-A "the trace was run-neutral" result
generalizes to the mass base. The pairing is 60/60 verified (the NN-th dump file = the NN-th
`[biarm] result` line = completion order; side/outcome/window/species cross-checks; the `[carry]`
rows pair per arm by rank).

**2. The separation (the design's metric: the payload's hand-frame drift from the last `hold`
row).** Total per attempt: **ok 0.0–27.2 mm (n=45, median 1.5; 21 exceed 2 mm) vs no-grasp
294.8–95 403.7 mm (n=8, median 1 506)** — disjoint (the B1s 1 458–95 404, the B2s 294.8–344.8);
the **carried** class 3.4–1 407.3 mm overlaps both (its loss is the W8-B carry/place escape: 5/7
release in the carry, 2/7 at the place). The W5-C claim (0–20.5 vs 313.2–1 992.0 mm) reproduces
with the bands shifted by scenario (the ok band +7 mm — the mass base's hold walk; the fail tail
50× longer — the a06 tomato's blow-up). The **hold walk** (the drift change across the 0.4 s
hold, from the freeze): ok ≤ 12.8 mm (median 0.2) vs the three hold-walk B1s 31.9/38.1/54.8 mm —
the class's first observable divergence, at a >2.5× margin, separating 3/8 no-grasp. The
**probe-1 lift** (the fruit's z rise over the first probe cycle — a grip test, not a 6 mm command:
the aim tracks the fruit's live position + a 6 mm ramp, so a gripped fruit rides the feedback up):
the no-grasp B1s −1.2…+0.9 mm (the fruit never rises), the B2s +5.2…+7.8 and the carried
+8.8…+17.8 (held through the probe), the oks −0.4…+67.5 (median 8.4) — but 5 ok first probes also
read ≤ 2.5 mm and recovered via a re-seat (the 2–3-block oks), so a failed first probe is not
specific to the losses.

**3. The phase localization (the design's first-departure rule + the hold column, the W5-C
convention).** At the freeze every attempt's payload moves at ~0.10 m/s (belt speed); the hold is
where the pads must arrest it. **The no-grasp class's first departure: probe block 1 on 4/8**
(a01, a07, a13, strawberry), **the hold on 2/8** (a06 at t=64.18, a08 at t=84.03 — the payload
already out at the probe's first sample, F=0/c=0 *inside the hold*), the takeoff 1 (a02), the
takeoff→carry gap 1 (a04). The **release** (sustained F<0.5 N ∧ contacts==0): hold 2, probe-1 2
(a01 t=20.36, a07 t=78.20), **re-seat window 2** (a13 w2→3 t=138.71, strawberry w1→2 t=39.63 —
both with the payload already 22.4/25.8 mm out at the window's near edge), the takeoff→carry gap
1, the carry 1. The mechanism reads in three shapes: **shape A (3/5 B1)** — the payload walks
32–55 mm during the hold with the force still 3.4–15 N (a loaded capture transient; the servo
chases its whole range, `closed=18–19.2 mm`, `trips=54–60`) and the contact collapses inside the
hold or at the probe's first ticks; **shape B (2/5 B1)** — a clean hold, the fruit does not rise
with the probe's lift, the pads pry to their 98–99 mm limit with force spikes (33–88 N) and the
payload walks out, releasing across the next re-seat window; **the B2s** — clean holds, the fruit
rises (+5.2…+7.8 mm), the loss later (a02 takeoff walk→carry release; a04 the takeoff→carry gap;
a07 the probe's end). The **carried** class holds through probe/takeoff and loses in the carry
(5/7) or at the place (2/7).

**4. The re-seat verdict (F1).** **No re-seat window ever released a payload that was held
(≤ 2 mm, two-sided, ~4 N) at its near edge.** The three hold-walk B1s' payloads were gone before
the first window (near edges 16.0/77.6/118.4 mm, F=0); a13's and the strawberry's were already
22.4/25.8 mm out (single-sided, force-spiked); and the windows **re-grab** as often as they shear
(a13 w1: 4.3→3.0 mm at F=19.97; ok s11 t20 w1: 26.9→11.6; ok s5 t16 w1: 8.4→12.0). The only
re-seat-window movement of a held payload in the whole corpus is an **ok** (s11 t04: 0.9→12.5 mm,
stayed gripped, placed). **F1 is confirmed — the `FRUIT_DYNAMIC_REGRASP_FLOOR` lever is dead as
the initiator** (it stays an unproven secondary for the 2 partially-out cases, and only after the
window's own per-tick rows exist, a 4-line `src/` addition). New finding: **the takeoff→carry gap
(0.78–1.01 s) is a second untraced window and hosts two real releases** (a04 69.5 mm, s23 t01
1 242.6 mm — both held at the near edge) plus four ok small departures (≤ 11.8 mm).

**5. The falsifiers and the branch selection.** F1 confirmed; F2 partial (the close-phase summary
geometry overlaps — the freeze `sep−gap_cmd` 4.5–13.3 vs ok −0.0–14.7 mm, the close-start offset
10.7–14.8 vs 8.8–15.5 — but the first-departure phases are not the same; the separation is
dynamic, not a static close row); F3 partial (3/8 no-grasp complete at the probe's lift/end, but
3/5 B1s' losses precede the probe and ok first probes also fail to lift); F4 partial (2/3 B2s
takeoff/gap, a07 probe-end); F5 not obtained (the ok drift is small, the NG population is the
mass base's own). **The data selects the pre-lift family over the re-seat branch — the close/hold
capture transient for the B1 majority's initiation, the probe's shape as the secondary — i.e. per
the pre-registered mapping the close-side family (`FRUIT_CLOSE_LOAD_RATE` first, the squeeze-side
knobs unmeasured on the two-line and the freeze criterion as its alternatives); the belt-break
branch only for the B2 minority (2/3); the carry/place for the carried class. The trace
localizes; it cannot pick among the close-side actuators (C1's own scripted battery read 12/20 vs
13/18 — unconfirmed).**

**6. The W5-C comparison.** Same analysis, same metric: the separator and the no-grasp
disjointness reproduce (the new 294.8–95 403.7 vs the W5-C 313.2–1 992.0); the onsets differ in
mix (the new: hold 2 / probe-1 8 / takeoff 2 / gap 1 / carry 2 / none 1 across all 15 fails —
the mass base's class is the grip loss; the W5-C: hold 1 / takeoff 4 / probe 4 / carry 6 — the
dense W3 sheet's carry escapes). The scenarios differ (the W6-A patch sheet + real-mass + the
shipped tree incl. the W7-A park gate vs the W3 dense sheet + the W5-C screens + the pre-W7-A
tree): the analysis transfers, the numbers do not.

**7. Deliverables (uncommitted, all under `logs/p14b/`).** `TRACE_RESULTS.md` (the report: the
pairing verification, the 60-row master table, the separation, the histograms, the re-seat
brackets, the mechanism, the verdict, the W5-C comparison, the limits); `trace_p14b_analysis.py` →
`trace_p14b_tables.txt` (the full tables); `master_table.md`; `curves/<seed>_trace_NN_*.csv` (the
60 per-row drift curves). **No-harm:** no tree change at all (read-only lane; the single-arm
default untouched; the three runs' own no-harm is the byte-identical `[fruit]` replay above).
