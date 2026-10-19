### P15 Stage-M screen (2026-10-19, branch `p-supply`, offline read of the two run-lane runs): M2 (`FRUIT_CLOSE_CONTACT_LEAD=0.10`) passes the mechanism gate — the hold walk collapses (the control's three hold-walk attempts' fruit 31.9/38.1/54.8 → 0.0–2.5 mm, the no-grasp count 7 → 4, the fruit braked ~97 → ~39 mm/s) — and is promoted to the outcome battery; M1 (`FRUIT_CLOSE_LOAD_RATE=0.04`) fails (a) and K2 fires (the no-grasp class 7 → 12, the never-held signature 3 → 5, the freeze median 20.5 → 47.0 ticks): the C1 stage-P trade reproduces on the two-line; K1 does not close (the walk is a close/hold quantity)

**Scope: offline, read-only.** The two screen runs (`logs/p15/10_m1_trace.log` + `traces_m1/`,
`logs/p15/11_m2_trace.log` + `traces_m2/`; SEED 11, 20 attempts each, the mass-base two-line patch
scenario verbatim, `FRUIT_DYNAMIC_TRACE=1`; `logs/p15/run_screen.sh`, `logs/p15/90_driver.log`)
were executed by the P15 run lane and completed cleanly (`[fruit] DONE`, 20/20 results, `exit=0`,
13:23:38–13:31:48 / 13:32:08–13:40:30, Tier A solo; no wedge — K5 clean). This lane ran no
simulator, wrote only under `logs/p15/`, and changed no default. Tree pins as read: `tasks.py`
`810658b802d22bbd63013726fc78af81`, `fruits.py` `d28546d26137d4540421caa7fa34a139`, `meshes.py`
`0e32b1ad1830b04dc0a4bddadfc84a5f` (the design's pins). The gate read is
`logs/p15/CLOSE_HOLD_DESIGN.md` §4 verbatim against the on-disk traced control
(`logs/p14b/10_seed11_trace.log` + `traces_s11/`, `TRACE_RESULTS.md`, `master_table.md`); the
metric implementation is `logs/p14b/trace_p14b_analysis.py` reused verbatim; the analysis is
`logs/p15/trace_p15_analysis.py` → `logs/p15/trace_p15_tables.txt`; the report is
`logs/p15/SCREEN_RESULTS.md`.

**1. The corpus.** Control (on disk): ok 11 / carried 2 / **no-grasp 7** (B1 4 + B2 3). **M1**:
ok 7 / carried 1 / **no-grasp 12** (B1 11 + B2 1). **M2**: ok 12 / carried 4 / **no-grasp 4**
(B1 2 + B2 2). Failure notes: only the baseline `fruit did not follow the gripper` (no new reason
in either arm). Per-attempt spans comparable (medians 14.2–14.4 s). The knobs move the timing, so
the **branch moved** between all three runs (different fruit picked) — the cross-arm tracking
below is by fruit identity, stated where used; the control's numbers re-derive from its trace to
the p14b record exactly (the three hold walks 38.1/31.9/54.8, the probe-1 3/7 at s11).

**2. The hold walk (the metric: the payload's hand-frame drift change across the hold, from the
freeze).** **M2 collapses it**: ok 0.0–0.2 mm (0/12 > 2 mm; the control 0.0–12.8, 2/11), the
no-grasp median 1.8 → 1.3, the top 54.8 → 31.6 (1 attempt > 20 vs 3), and every trackable
instance of the control's three hold-walk attempts reads 0.0–2.5 mm (left orange index 0:
0.0/0.1/2.5; left tomato index 6: 0.0/0.0 — the orange converts at attempt 1, the tomato does
not). **M1 raises it**: B1 median 35.0 → 52.1, max 54.8 → **85.8**, 8 no-grasp attempts above the
control's B1 floor, 9/12 above the ok ceiling, walk speeds 0.073–0.224 m/s (the control's
0.083–0.143). The actuation checks (the design's §4 (iii)): **M1's freeze moves later** — the
primitive's own freeze lines read median **20.5 → 47.0 ticks** (16–38 → 4–131; 12/17 ≥ 40, 3/20
never freeze, freeze-force median 4.38 → 8.12 N, two span-negative jam freezes at 190/232 N),
reproducing the R11-B signature (18.0 → 55.5) on the two-line; the trace-side proxy (the
commanded-gap stall) validates to ~1 tick. **M2's freeze is unchanged** (21.0 vs 20.5) — expected;
its actuation is the shear: the fruit's |v_y| at the close-end/hold is braked (all attempts −97.3
→ −38.7 mm/s; per class ok −54.5 → −29.5, carried −118.8 → −79.7, no-grasp −98.5 → −55.8), the
R11-B C2 direction, with the relative velocity through the hold ≈ 0.

**3. The probe-1 first departures (the 2 mm rule, phase-bracketed, the W5-C pre-probe label).**
Neither arm raises the count: no-grasp control 3/7 (pooled 4/8) → **M1 2/12 → M2 1/4**; all
attempts 7 → 5 → 3. The composition moves: M1's departures move **earlier** — 10/12 no-grasp
attempts are already out at the probe's first sample (hold pre-probe; the walk consumed them
during the hold) against the control's 2/7; M2's 4 no-grasp attempts depart probe-1 1 / probe-2+ 1
/ takeoff 1 / the untraced gap 1 — the hold-walk shape is absent. The probe-1 dz does not worsen
(M2's ok low tail improves: min 6.1 vs 0.0; M1's walkers read the never-rise 0.0).

**4. The K1 check — the walk is movable, so K1 does not close.** The design's K1 ("if the walk is
the hand's settling, no close/hold actuator moves it") is refuted by M2's collapse; the named next
of the K1 closure (the descent-boundary/scene family) is not triggered. The trace's limit #6 still
bounds the claim, and the world-frame decomposition measures it: on the control's B1s the walk is
dominated by the fruit's belt slide (relative y −50…−78 mm) with a secondary hand-settling term in
x/z (hand dx +22…+34, dz −8…−10 mm) — slip with the hand still finishing the approach; M2's hold
shows the arrest is achievable (the fruit braked and followed the hand exactly). M1's top walkers
add large hand-motion components (the rate-limited close leaves a transient the hold inherits).

**5. The K2 check (the C1 late-freeze trade), per arm.** **M1 fires K2**: the no-grasp class
**7 → 12 (+5)**, the R11-B never-held signature (onset ≤ 3, force@onset = 0, contacts@onset = 0)
**3 → 5 (+2)**, 12/17 late freezes (≥ 40 ticks), freeze force median doubled, two span-negative
jams — the stage-P trade ("the fruit rides the faces > 1 s; the marginal grip slips at the pluck")
reproduces on the two-line at this seed; M1 is negative, not adopted. **M2 does not fire K2** (7 →
4, signature 3 → 2, no new reason); recorded for Stage P: M2's **carried-not-placed rises 2 → 4**
(not a gate item; a baseline class the control shows 2 of).

**6. The verdict (the gate §4, item by item).** **(a)** M1 FAIL (the walk rises; the count rises);
M2 PASS (every trackable instance of the three hold-walk attempts' fruit ≤ 2.5 mm; the count −3).
**(b)** both PASS on the count (the departures do not rise; M1's move earlier is recorded) and the
dz. **(c)** M1 FAIL (K2); M2 PASS (the carried +2 recorded). **M2
(`FRUIT_CLOSE_CONTACT_LEAD=0.10`) is promoted to the outcome battery at SEED 11/5/23** (one run
per seed, each with a bit-identical double — K3; the no-grasp class by the P10-E rules, the falls
`lowest payload point` ≤ −1000 mm with the partials −100…−1000 reported separately, the
carried-not-placed, the pooled outcome, the mechanism checks; the rate is not the endpoint). **M1
closes negative (K2), not adopted.** The two hypotheses the screen was built to discriminate
resolve cleanly: the **hold-window arrest (the lead)** moves the walk; the **freeze-state (C1)**
moves the freeze but raises the walk and the class.

**7. The honest limits.** N = 1×20 per arm, one seed (11), one scenario/tree; single-sample class
counts, no rate quoted; the branch moved between arms (cross-arm pairing by fruit identity,
stated); the metric is a relative displacement, not a force decomposition (the attribution is
measured displacement; the freeze/|v_y| readings are direct, the causal chain inferred); the K2
signature is not zero-baseline on this scripted path (the census is the primary read); Stage M
carries no doubles (K3 is a Stage-P rule). The runs' provenance is the run lane's
(`run_screen.sh`, `90_driver.log`); this lane wrote only under `logs/p15/`.
