### P15 (2026-10-19, branch `p-supply`, offline): the close/hold grip-margin design — the actuator inventory (C1, the freeze criterion, the squeeze/depth, the hold compensation, the probe's shape), the pick (a two-arm Stage-M screen: C1 primary + the hold-window lead, gated on the trace's hold walk), and the strongest reason it could fail (the walk may be the hand's own descent-settling motion)

**Scope: offline, read-only.** No simulator run; no `src/`/`scripts/`/`configs/`/`datasets/`/
`Paper/` write; no commit; writes only under `logs/p15/`. Tree pins as read: `tasks.py`
`810658b802d22bbd63013726fc78af81`, `fruits.py` `d28546d26137d4540421caa7fa34a139`, `meshes.py`
`0e32b1ad1830b04dc0a4bddadfc84a5f`. The design executes the P14-B branch selection
(`logs/p14b/TRACE_RESULTS.md` §0/§4: the loss localizes to the HOLD + probe-1, the loaded capture
transient; the family selected is the close/hold grip-margin family, R11-B C1 first; the trace
cannot choose among the close-side actuators). Deliverable: `logs/p15/CLOSE_HOLD_DESIGN.md`
(the inventory + the ranking + the pick + the pre-registration sketch + the constraints).

**1. The target (the trace's endpoints, the design must move).** The **hold walk** — the
payload's hand-frame drift across the 0.4 s hold from the freeze: the ok attempts ≤ 12.8 mm
(median 0.2, n=45), the three hold-walk B1s **31.9 / 38.1 / 54.8 mm** walking at 0.08–0.14 m/s ≈
belt speed with the force still 3.4–15 N; and the **probe-1 first departures** (4/8 no-grasp cross
in probe block 1; the no-grasp B1s' probe-1 lift dz −1.2…+0.9 mm — the fruit never rises). At the
freeze every attempt's payload moves at ~0.10 m/s (a01 −0.099, a10 −0.101, a06 −0.102 in y): the
hold is where the pads must arrest the belt-speed motion, and whether they do is the ok/fail line
(ok arrest ≤ 12.8 mm; the three hold-walk B1s do not). The trace's seven limits bound the design —
above all #6: the metric is a displacement, **it cannot split the walk between the belt drag and
the hand's own settling motion** (the trace's own "the hand also translates ~30 mm as the
post-descent solver finishes the approach").

**2. The actuator inventory (close/hold-side, from the current knobs/code; each with the mechanism
vs the transient, the evidence FOR/AGAINST, the falsifier).** **(A) C1 `FRUIT_CLOSE_LOAD_RATE`**
(0 = off; test 0.04; the whole-close face-speed cap + the delivered-command limit, `tasks.py`
7423-7452/7867-7873): the only close-side actuator with a **measured actuation signature** on the
shipped dynamic-capture path (R11-B M1: the freeze row 18.0 → 55.5, the freeze-zone face speed
188.7 → 39.9 mm/s) and the mapping's first — but its one measured outcome is the stage-P trade
(12/20 vs 13/18; the never-grasped 0 → 5; "the fruit rides the faces >1 s; the marginal grip slips
at the pluck") and its link to the hold walk is indirect (it changes the freeze state entering the
hold). **(B) The freeze criterion** (`FRUIT_DYNAMIC_CONTACT_FORCE/TICKS/STALL` = 0.5 N / 3 /
0.15 mm-tick; the first sustained contact + span stall; never re-evaluated): the only close-side
lever aimed at the trace's open "tip/edge contact" root (the P10-E span +3.7…+35.1 mm wider than
the fruit) — **unbuilt** (`src/`, its own pre-registration), and the corrected P11-B plow is its
caution (a deeper interference ejects: tomato ≥10 mm 2/3, apple ≥2 mm 3/3). **(C) The squeeze /
close depth** (`FRUIT_DYNAMIC_CLOSE_DEEP` 0.97, `FRUIT_GRIPPER_SQUEEZE` 0.98,
`FRUIT_DYNAMIC_MIN_INTERFERENCE` 2.5 mm, `FRUIT_DYNAMIC_CLOSE_LIVE` 0.97): closed by mechanism on
the direct interface (R6-B's drive-saturated pinch: the relief to 0.5 mm leaves the force in the same
4.15–4.47 N band) with a flat prior (P10-E §3.3); unmeasured on the two-line. **(D) The hold
compensation for the belt motion** (`FRUIT_DYNAMIC_HOLD` 48; the lead `FRUIT_CLOSE_CONTACT_LEAD`
unset → `FRUIT_DYNAMIC_TRACK_LEAD` 0.18; the x pin/seek): **the trace's own window** — the lead is
the only knob whose measured variable class is the trace's (R11-B §4.4: lead 0.10 brakes the fruit
to |v_y| 8–19 mm/s, lead 0.26 punts it to 129–291; "the longitudinal variable is a
velocity/shear one, not a position one"), env-only, but its single class read is a null (M2 −1/±0)
and the walk may be the hand's settling (limit #6); the **hold length is not a lever** (the walk's
rate is constant at belt speed) and the x-seek is cross-belt. **(E) The probe's shape**
(`FRUIT_DYNAMIC_PROBE` 0.006 / `_TICKS` 60 / `_TEST_STEP` 0.01 two-line): targets the *completion*
(4/8 first departures in probe-1) but the specificity is weak (5 ok first probes also read ≤ 2.5 mm
and recovered via the re-seat; 3/5 B1s' losses precede the probe) and the W5-C probe screens are
closed. The closed families are recorded in the doc §2.6 (the servo/chase — F1: the re-seat never
ejected a held payload, the chase is a symptom; the re-seat floor — the seed-5 apple success with a
full-chase re-seat; the arrival family 35/31/30 vs 39/60; the takeoff screens; the pluck dwell; the
physics/shape/scene).

**3. The ranking and the pick.** Ranked on the trace's endpoint × the cost × the risk: **1. C1**
(the mapping's first; measured actuation; env-only; the failure mode pre-registered) — **2. the
hold-window lead (C2 0.10)** (the best mechanism fit to the trace's own window/variable class; ranks
below C1 only because its class read is a null while C1's actuation is measured) — **3. the freeze
criterion** (the best fit to the tip-contact root; unbuilt; the deeper-freeze ejection prior) —
**4. the squeeze/depth** (closed by mechanism; low expected movement) — **5. the probe's shape**
(the completion, not the origin). **The pick: a bounded two-arm Stage-M mechanism screen at SEED 11
— M1 `FRUIT_CLOSE_LOAD_RATE=0.04` (primary) + M2 `FRUIT_CLOSE_CONTACT_LEAD=0.10` (the hold-window
arm), read against the on-disk traced control (`logs/p14b/traces_s11`, no run), with the trace's
own hold-walk/probe-1 rules as the promotion gate; ONE promoted arm runs the outcome battery (the
no-grasp class + the falls) at SEED 11/5/23.** The two arms are the two mechanistically distinct
hypotheses for the hold walk — the freeze state entering it (C1) vs the hold-window arrest itself
(the lead) — which is exactly the choice the trace cannot make; both are env-only; the optional M3
(`FRUIT_DYNAMIC_CLOSE_DEEP=0.95`, the trace's own named "squeeze-side on the two-line" alternative)
appends to the same block if the budget allows; the freeze criterion is the named fallback (its own
pre-registration).

**4. The sketch (frozen in the doc §4).** The mass base verbatim (`FRUIT_PHYSICS_REAL_MASS=1` +
the two-line patch env + the trace; SEED 11 primary, 5/23 controls); the arms above; the mechanism
endpoints (the hold walk per attempt vs the control's own bands — the ok ≤ 12.8, the B1s
31.9/38.1/54.8; the probe-1 first departures + dz; the actuation checks: M1's freeze row/speed, M2's
hold shear, M3's freeze depth; the release bracket histogram); the outcome endpoints (the no-grasp
class by the P10-E rules, the falls = the `lowest payload point` ≤ −1000 mm, the carried-not-placed,
at SEED 11/5/23, the doubles bit-identical); the promotion rule (the hold walk into/below the ok
band or the seed-11 no-grasp count −2, with the probe-1 departures not rising and no
never-grasped growth); the kills (K1 the mechanism gate — the bounded negative, stop before P; K2
the class re-draw ≥ 2; K3 a non-bit-identical double; K4 the no-harm; K5 the protocol); the no-harm
(knobs unset: the acceptance 9/10 + `fingerprint: matches`, the two-line dense re-record + `190`
PASS, selfcheck PASS, the knob-off mass-base replay byte-identical). Budget ~1.5 h Tier A solo
(Stage M ~20 min, Stage P ~60 min incl. the doubles, the no-harm ~15 min).

**5. The honest constraints (the doc §5).** The R11-B negative is the pick's own prior (the
never-grasped 0 → 5; the stopped stage N); the pre-onset load path is closed; the squeeze side is
closed by mechanism; the reaction/guard, the control-side ejection, the re-seat floor, the
takeoff screens, the pluck dwell and the physics/shape/scene families are recorded negatives; the
trace's own limits (n=8, the untraced windows, the displacement-vs-force limit, one scenario) bound
the design. **The strongest reason the pick could fail**: the hold walk may not be a close/hold-chain
quantity at all — if it is dominated by the hand's own ~30 mm descent-settling motion (the AGENTS §2
boundary shortfall: every descent ends 40–90 mm short of the pick pose and the post-descent solver
finishes the approach), then neither C1 nor the lead moves it, both arms read flat at the mechanism
gate (K1), and the named next is the descent-boundary/scene family. The design makes that failure
cheap and informative: K1 stops the phase before the outcome battery, and the two arms discriminate
the freeze-state hypothesis from the hold-window hypothesis with one traced battery.
