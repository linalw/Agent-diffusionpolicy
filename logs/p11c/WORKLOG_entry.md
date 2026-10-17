### P11-C implementation (2026-10-18, branch `p-supply`, offline): the re-seat arrival geometry knob - `FRUIT_DYNAMIC_REGRASP_FROM_OPEN` (default off, consumed only in the two-line W1 keep branch) makes the re-seat descend at the pre-close open gap and close horizontally to the same keep depth, the P11-B probe's ejection-free geometry; the knob-off path executes the byte-identical 80/80 command log vs `HEAD`; no simulator run (the Tier-A battery is a separate lane)

**Scope: implementation + offline verification only.** No simulator command was issued (the
Tier-A battery is a separate lane per the frozen `logs/p11c/PREREG_REGRASP_ARRIVAL.md`). Writes:
`src/fruit_sorting/tasks.py` (the knob + the arrival branch; md5 `6574d92e...` ->
`810658b8...`), `src/fruit_sorting/rl_env.py` (the metadata-only `TASKS_MD5` follow, line 271;
`8413fece...` -> `9a2c3872...`), and `logs/p11c/` (this entry, `IMPLEMENTATION.md`,
`check_regrasp_from_open.py` md5 `8f280b82...`, `selfcheck.log`). No commit by the lane; no
branch operation; `Paper/`, `datasets/`, `checkpoints/` untouched. **Post-commit note
(2026-10-18):** the orchestrator committed this implementation (`30cde55`) and launched the
Tier-A battery (seeds 11/5/23, A vs B); HEAD `8082993` then recorded the P11-B Oracle R1-R5 -
the probe's `plow` group ran a rise-and-return, so the "descending jaws eject" reading is
**withdrawn** (the corrected plow re-run is queued, `logs/p11b/90_plow_fix_*`). The
implementation is exactly the frozen pre-registration's change and is unchanged; what the
withdrawal re-opens is the mechanism prediction, which the battery + the corrected re-run own.
The plow citations below are annotated accordingly.

**The change (the measured lever, sharpened by the probe).** P11-B measured the **close-from-open**
geometry as ejection-free (`belt` 0/3, `air` 0/3 at every delta) and the contact parameters as
inert; its `plow` group was originally read as the shipped descend-at-a-sub-width-gap geometry
ejecting 3/3, but that reading is **withdrawn** (R1: the plow ran a rise-and-return - it closed
the pads at the grip pose and the loop's first target raised the loaded jaws - and the escape
precedes any descent in the trace). P10-E's B1 chain supplies the context (the marginal close
-> the failed probe ->
the force-servo chase -> the re-seat at the chased sub-width keep-gap -> the ejection, 13/18
falls). The W1 keep branch (two-line-only via `_dynamic_profile`, `tasks.py:8698`) now resolves
`regrasp_from_open = self._dynamic_profile("FRUIT_DYNAMIC_REGRASP_FROM_OPEN", "0", "0") == "1"`
(env wins; a future flip is one literal; default 0 = the shipped form). The descent phase is
**shared** and only the gap it holds differs: `descent_gap = float(gap_open) if
regrasp_from_open else keep_gap` - with the knob off this is literally `keep_gap`, so the
shipped 40-tick loop is byte-unchanged. With the knob on the jaws descend around the fruit at
the pre-close open gap (`FRUIT_GRIPPER_OPEN`, 0.09 m - wider than the measured *centred*
blocking span `extent + ~11 mm` of link span for every pool fruit: 0.070 + 0.0113 = 0.0813,
0.0855 with the mesh bias, both < 0.09, and above the probe's widest *commanded* anchor
extent + 15 mm - the descent geometry itself is under the R1 withdrawal, so the per-attempt
no-contact readout is the battery's to confirm), then close
**horizontally** to the same keep depth with the initial
close's own two-phase shape
(`np.concatenate([min_jerk_ramp(gap_open, wide, fast_ticks), min_jerk_ramp(wide, keep_gap, load_ticks)])`).
Everything else in the W1 profile is untouched: the `keep_gap` expression
(`squeeze_gap` else `grip_gap`), the `_force_servo_reset`, the ratchet
(`FRUIT_DYNAMIC_REGRASP_STEP`), the cycle bound, the non-keep regrasp branch. The say row keeps
the shipped `dynamic regrasp: re-seated in place (gap N mm kept)` text and gains exactly
` [from-open]` when the knob is on (the battery's geometry marker; existing `mm kept` greps are
unaffected). Choices recorded with their alternatives in `logs/p11c/IMPLEMENTATION.md`: the
descent gap = the pre-close open gap (alt: live extent + the measured offset - rejected as a
new hand constant); the close shape = the initial close's two-phase form (alt: the non-keep
path's 45-tick single ramp); the close depth = `keep_gap` (alt: `grip_gap` - rejected as a
re-seat-depth change, the chase stop stays a separate optional arm per the pre-reg). The
initial close's contact freeze is not reproduced (the shipped re-seat holds a fixed depth too;
the probe's belt/air groups held the sub-width gap 0.5 s without ejection), and the pad
**opening** phase is the fix's essence - the W1 "pads never leave the fruit" property is
deliberately not preserved for this arm, matching the pre-reg's honest expectation (the class
may shift toward B2/C slip; the rate may not improve).

**The offline evidence.** (1) `python3 -m py_compile` on both files: OK. (2) The new stub
`logs/p11c/check_regrasp_from_open.py`: **PASS** - source checks (the triple, the four
consumption sites, the shared descent loop's shipped statement sequence and `ik_step`
expression with only the `descent_gap` argument changed, the exact two-phase ramp, the
`_force_servo_reset` order, the unchanged non-keep branch/ratchet, the `wide`/`fast_ticks`/
`load_ticks` scope); a resolution truth table (the real statements exec'd, 18 rows: unset ->
False on every session, `=1` -> True everywhere, `true` -> False); and the approach branch
exec'd end-to-end against recording fakes (knob off -> `[keep_gap] * 40`, no close block, the
shipped say string; knob on -> `[gap_open] * 40` + the 84-tick ramp, monotone, ending exactly at
`keep_gap`, first tick still ~`gap_open`; the geometry invariant). (3) The four existing stubs
(`logs/p10c/check_twoline_scope.py`, `logs/p10c2/check_confirm_gate.py`,
`logs/p9a/check_skip_predicate.py`, `logs/p10c3/check_flip_resolution.py`): all PASS. (4)
`scripts/selfcheck.sh` (`SELFCHECK_LOG=logs/p11c/selfcheck.log`): PASS, 0 failures, 1 skipped
(motion budgets need a run log). (5) The strongest form of the pre-reg's kill #1: a one-off
harness exec'd the ORIGINAL `HEAD` keep-branch statements and the NEW knob-off path against
identical fakes - the recorded command logs (40 `ik_step` targets + 40 `follow_centre` gaps,
80/80 ops) are **identical**; with the knob on the same harness records 124 ops (40 x 0.09 m +
the ramp to exactly 0.0519 m, equal to the independent reference). So the A-side replay is the
battery's confirmation, not a re-derivation.

**Deferred (the battery's to measure).** The pre-registered arms (A = the shipped two-line, no
env; B = A + `FRUIT_DYNAMIC_REGRASP_FROM_OPEN=1`), the W6-A patch battery at SEED=11 (hard) +
seeds 5/23, and the endpoints: the per-attempt arrival geometry (the ` [from-open]` marker +
no descend-at-the-gap contact), the no-grasp class split and the falls (`[carry] lowest payload
point <= -100 mm`), the outcomes, the `105` budgets + the `190` gate + no new reasons, and the
cycle (+5 % margin). The kills stand as frozen: the knob-off replay, the falls/blowups not
disappearing, a new failure reason, or the acceptance no-harm. The battery lane should re-run
the A-side replay vs the P10-C.3 records modulo reporting rows, and update any parser that
anchors on the full say line for the new ` [from-open]` token.
