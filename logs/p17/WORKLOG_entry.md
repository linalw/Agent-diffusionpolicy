### P17-B (2026-10-19, branch `p-supply`, offline): the capture-lever design — the actuator inventory (the belt speed, the hold's tracking compensation, a slide-tolerant capture criterion, the friction/hold-length/probe-shape residuals), the pick (the arrest-verified capture criterion: the hold/probe-1 slide gate + the bounded in-place re-seat, with the freeze-side two-sided gate as the alternative arm), and the strongest reason it could fail (the re-seat re-centres the contact but does not change the friction margin — the walk does not fall, K1 closes at Stage M)

**Scope: offline, read-only.** No simulator run; no `src/`/`scripts/`/`configs/`/`datasets/`/
`Paper/` write; no commit; writes only under `logs/p17/`. Tree pins as read: `tasks.py`
`54f70584b07fa249418f1efe30f30af0` (the P16-I tree), `fruits.py`
`d28546d26137d4540421caa7fa34a139`, `meshes.py` `0e32b1ad1830b04dc0a4bddadfc84a5f`, `rl_env.py`
`be0248e0c3b88b28b0ec47ff28e1b68c`; HEAD `4a9f665`. The design executes the mission framed by
the P14-B/P15/P16 findings: the no-grasp loss localizes to the HOLD + probe-1 (the loaded capture
transient; the payload slides at ~belt speed with the force present while the hand's own motion
is small); the failure mass is conserved across the tested close/carry actuators (the P15's M2);
the descent's shortfall does not feed the capture (the P16's K1). Deliverable:
`logs/p17/CAPTURE_LEVER_DESIGN.md` (the inventory + the ranking + the pick + the pre-registration
sketch + the constraints).

**1. The target (refreshed).** The hold walk: ok −0.6…12.8 mm (median 0.2, n=45) vs the three
hold-walk B1s **31.9 / 38.1 / 54.8 mm** at 0.083–0.143 m/s ≈ the belt; the probe-1 (4/8 no-grasp
first departures in probe block 1; the B1s' lift dz −1.2…+0.9 mm); the release completes hold 2 /
probe-1 2 / window 2 / gap 1 / carry 1, so **every failure is detectable while still in the span**
and the existing recovery (the probe's failed lift → the 101-tick re-seat) fires after the payload
is 22–55 mm out on 5/8. The P16 §1.3 world decomposition: the B1s' rel_dy −51.1…−1.0 (median
−28.5) while the hand's own y moves −1.6…+3.4 mm; the fruit's |vy| peak median 0.205 (the oks
0.078) — the payload *accelerates past the belt speed* while the pads hold it — and the |vx|
squeeze-out 0.185 vs 0.071: a 3D escape, not a pure y slide. The arm asymmetry (the P15 tables):
the right hand's dy ≈ the fruit's dy (it moves with the fruit); the left hand's dy is small
(−0.8…−14.9) while the fruit moves −20…−46 — the left's full belt travel must be absorbed by the
pad-fruit friction.

**2. The inventory (each: the mechanism, FOR/AGAINST, the expected movement, the cost, the
falsifier).** **(a) The belt speed** (`FRUIT_BELT_SPEED`, the scenario constant 0.12; no
station-local slowdown exists): the walk's *rate* scales with v, but the arrest is stick/slip
(Coulomb, speed-independent), the escape is geometric, and the B1s' |vy| peak exceeds the belt
(the squeeze-out is a co-driver) — a mechanism probe, not a reduction. The R3 §4 screen (quoted:
0.12 = 12/20, 3.63 window/min, interval 16.53/17.30/19.90 s; 0.15 = 14/20, **4.69**, +29 %; 0.18 =
14/20, 3.82 with the starved slots 115/38) tested **only upward** and says the two-line is
arrival/supply-limited, not servo-limited, up to ≥ 0.15; the fixed 1.5 s floor (`v·1.5`) widens
the usable band as the belt slows, but the arrival rate falls with it. **(b) The hold's tracking
compensation** (the lead; the OpenArm hand's fingers are the contact bodies, so the arm's
achieved motion is the fingers' motion): **measured** — the M2 (lead 0.10) collapsed the walk
(0.0–2.5 mm on the tracked fruit; the left hand followed; the fruit's world dy fell to −9…−14 mm),
cut the no-grasp 7 → 4 and the falls 3 → 1, **but traded the total** (pooled 45 → 38; the carried
2 → 4 s11, 0 → 6 s5; the interval +8 %). What M2 did NOT do: a hold-only variant; the *reactive*
form (its static lead perturbed every attempt — the s5 ok 17 → 10); the lead's optimum (0.10–0.26
unmapped); the left's non-following *cause* (the 21.6 mm commanded offset past the reach band is
the leading hypothesis, not proof). **(c) A slide-tolerant capture criterion**: the shipped
freeze (0.5 N / 3 ticks / 0.15 mm-tick; never re-evaluated) and the probe (0.006/60/0.01) are
**static** — they never check whether the payload was *arrested*; the failures are visible over
tens of ticks while still in the span. The mechanism: the bounded in-place re-seat (the W8-B
guard's form; the F1 re-grabs measured: a13's w1 4.3 → 3.0 mm at 19.97 N) fires *early*, on the
sliding attempts only — the one conversion the M2's *static* centring did not test. AGAINST: the
guard family's two N=5 near-misses (5–1 p = 0.1094; 3–1 p = 0.3125; the 100–400 mm band 0/37);
the R6-B "no warning" finding (the *carry* escape is late-signalled — the hold walk is not); the
P11-C from-open re-draw; the deeper-freeze ejection prior (for the freeze-side form); unbuilt.
**(d) The others**: the pad friction (env-only; measured negative on the ancestor class by the
P3-faces screens — combine=max / mu=8 left A2/A8 unchanged and re-ejected A4; the combine
semantics flagged unverified by the P11 audit G5); the hold length (a re-draw — the walk's rate
is constant, the escape migrates to the probe/window); the probe's shape (weak specificity; the
completion, not the origin); the pad width (the 40 mm arrest window — a `src/` constant, not a
knob); the closed families (the servo/chase — F1; the x-seek — W5-C cfg4; the hand-vmax —
logs/150; the squeeze/depth — R6-B; the re-seat floor — F1; the arrival family 35/31/30 vs
39/60; the verify dwell — a detection lever).

**3. The ranking and the pick.** **1. (c) the slide-tolerant capture criterion** — the only
candidate acting on the *measured* transient's own signal with a measured recovery window (the
in-span 4–20 mm vs the existing 22–55 mm); **2. (b) the hold's tracking compensation** — measured:
the mechanism win + the conserved mass; **3. (a) the belt speed** — untested downward, but a rate
change with a real supply cost; **4. (d) the others**. **The pick: (c), the arrest-verified
capture criterion**, two bounded forms in one Stage-M battery: **M1 the hold-side slide gate + the
bounded in-place re-seat** (`FRUIT_CAPTURE_SLIDE_RATE`/`_TICKS`/`_RESEAT_*`, default-off,
dynamic-capture-scoped: the arm's command drops the feed-forward lead and re-centres on the
payload at a bounded step when the drift rate exceeds the ok band, ≤ 1–2 times per attempt, with
the post-response drift rate recorded) and **M2 the freeze-side two-sided gate**
(`FRUIT_CAPTURE_SIDED_*`: the freeze commits only on a two-sided, load-sustained contact; the
shipped criterion as the bounded fallback) — the *recovery* vs the *commitment* hypotheses, the
choice the trace cannot make; the optional **M3** is the belt-speed probe (0.08). ONE promoted
arm runs the outcome battery.

**4. The sketch (frozen in the doc §4).** The mass base verbatim + the trace; SEED 11 primary,
5/23 controls; the mechanism endpoints (the hold walk vs the control's own bands; the probe-1
departures/dz; the response/actuation reads incl. the post-response arrest check; the release
brackets); the outcome endpoints — **the TOTAL failure mass (the no-grasp + the carried together;
the P15's lesson) + the falls** (the F6 convention), the interval reported; the promotion rule
(the walk into/below the ok band or the seed-11 no-grasp −2, **with the post-response arrest
confirmed**, the probe-1 not rising, no never-grasped growth, the re-seat budget respected); the
kills (K1 the mechanism gate — the bounded negative, stop before P; K2 the total-mass re-draw;
K3 the doubles; K4 the no-harm; K5 the protocol); the no-harm (the acceptance 9/10 + fingerprint,
the two-line dense + `190`, selfcheck, the knob-off replay, the offline stub identity). Budget
~1.5–2 h Tier A solo (excluding the `src/` + the stub).

**5. The honest constraints (the doc §5).** The R3 negatives (the catch is not the limit at any
tested speed; the speed changes *when* the fruit arrive; one branch per point); the supply-rate
coupling (the line is arrival-bound; a slower belt eats the idle then the throughput); the
R6-B/R8-A/R9 closures (the drive-saturated pinch; the D screen's three failures; the RWR lane's
negative — the scripted primitive owns the pre-onset facet); the conserved-mass lesson (three
instances; read the TOTAL); the trace's limits (n=8; the untraced windows; the displacement
metric; one scenario); and the sibling lane's NO-GO (the *in-window*, 0–2 tick reaction family
stays closed — this pick is not in it: its window is the tens-of-ticks hold/probe-1, its actuator
is the scripted arm command, and the scripted-side window is exactly the P17-C's survivor).
**The strongest reason the pick could fail**: the response re-centres the contact but does not
change the friction margin — the payload keeps sliding (now with the arm chasing it), the walk
does not fall, and **K1 closes at Stage M**; the second mode is the conserved mass itself (the
walk falls, the carried absorbs). Both are pre-registered and cheap: the mechanism gate stops the
phase before the outcome battery, and the two forms discriminate the recovery from the commitment
hypothesis with one traced battery.
