# P98 PREREG - revert P97: the clearance pre-pose goes back to opt-in

Pinned before any simulator run of this phase. Owner decision: **revert P97.**

## 0. Why

P97 shipped P96's clearance pre-pose as the two-line session's default as an
**invariant** fix, with no rate claimed. Its own record (`logs/p97/RESULTS.md`):

| reading | P97 shipped default | pre-P97 / P94 |
| --- | --- | --- |
| `scripts/accept.sh` (10 attempts) | **6/10 at the 0.60 floor** | **8/10** |
| seed-5 sanity cell (20 attempts) | **12/20 = 60 %** | 17/20 |
| inter-placement interval (seed 5) | **16.02 s** | 10.59 s |
| contact census `<= 6 mm` | 1/20 (the proxy's own floor) | 4/40 pre-P96 |

The invariant is real (P96's census: contact 1/40 -> 0/40), but the **shipped
acceptance cannot sit on its floor**: a zero-margin gate cannot distinguish the
shipped line from a regression. The count was never a gain (P96's two-seed draw
29/40 -> 27/40). So the flip comes back out; the fix stays available as the
opt-in `FRUIT_BIARM_PREPOSE_CLEAR=1`.

## 1. The one change

`tasks.PREPOSE_CLEAR_TWO_LINE_DEFAULT = True -> False`. Unset + two-line resolves
**off** (origin `explicit`, the pre-P96 label); `=1` still arms P96's measured
pose (z=0.165, hold=calib, band [0.155, 0.25], the `253` arithmetic and solve
site unchanged). The P97 wiring (`_prepare_two_line_stations(two_line)`) stays:
it is inert with the cell off and it is what makes `=1` correct on the first
batch. `rl_env.TASKS_MD5` follows (metadata only).

## 2. Predictions (registered before the runs)

* **P1 - the flip-back is resolution-only.** `scripts/accept.sh` on the reverted
  tree reads **8/10, ~9.0 s/attempt**, `fingerprint: matches
  configs/motion_reference.json` = **`30fb99f8`**, `190: PASS`, and its
  `[fruit]` physics stream is **419/419 byte-identical** to
  `logs/p94/accept_final.log` (P97's own `=0` A/B already proved this path
  bit-for-bit; the revert must land exactly on it).
* **P2 - the references are restored byte-identically.** Both two-line-side
  files copy back from `logs/p97/motion_reference{,_twoline}_pre_p97.json`
  (**`30fb99f8`** verified before any run);
  `configs/motion_reference_single.json` stays `8952c320`.
* **P3 - the `=1` A/B reproduces P97's arm.** With
  `FRUIT_BIARM_PREPOSE_CLEAR=1` the acceptance reads **6/10** (P97's own default
  count), passes the **0.60** rate floor, and its fingerprint **DIFFERS by
  construction** against the restored `30fb99f8` (the arm moves every attempt).
  Its `[fruit]` physics stream is **identical to `logs/p97/accept_final.log`**
  once the two `[fruit] [biarm] pre-pose` rows are dropped (their only difference
  is the registered origin label, `1(default)` -> `1(explicit)`); budgets pass.
* **P4 - nothing else.** No new lever, no other default, no store, no
  checkpoint, no direct/policy run: the knob is `scope-off` without a
  `CoopSession`. The single-arm reference is untouched and the scripted single
  arm cannot read the knob.

## 3. Gates

`scripts/accept.sh` (P1) and `scripts/190_twoline_gate.sh` on it,
`scripts/selfcheck.sh`, `scripts/211_bed_audit.py`,
`scripts/106_index_audit.py`, `scripts/107_collect_merge_test.py`; the `253`
leg's table is re-pinned to the reverted default.

## 4. What is not claimed

No rate. The revert does not measure the clearance pose (P96 did), does not
re-draw P96's census and does not say the invariant is small - it says the
shipped acceptance cannot carry it at its floor. P97's numbers stand as the
record of the arm that was shipped for one phase.

## 5. Falsifiers

* **F1**: the reverted acceptance is not 8/10, does not match `30fb99f8`, or is
  not `[fruit]`-identical to `logs/p94/accept_final.log` -> the revert is **not**
  resolution-only; stop and diagnose before publishing anything.
* **F2**: the `=1` arm does not reproduce `logs/p97/accept_final.log`'s physics
  stream (pre-pose rows dropped) -> the opt-in path changed; stop and diagnose.
* **F3**: any gate red for a reason other than P1's expected rate-only standing
  floor (the acceptance's own scenario is an 8/10 branch, so it should pass).
