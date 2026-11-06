# P124 - adopting the third lane was measured and **reverted**: the scripted line takes it, the policy interface does not

The owner said "要" (adopt), so the flip was executed and priced: default
`FRUIT_OUTPUT_LANES=3`, the tests moved, both motion references re-recorded from
the three-lane scene, and the acceptance plus the policy canary run. **The
scripted cell passes; the hybrid policy interface collapses.** The default is
back at **2**, the references are back at `30fb99f8` / `30fb99f8` / `8952c320`,
and the revert is **421/421 `[fruit]` lines byte-identical** to the P123 record.

## 1. What the flip measured

| cell | scene | result |
| --- | --- | --- |
| `accept.sh` (two-line, 10 attempts) | **3 lanes** | **7/10 = 70 %**, `190: PASS` after re-recording, budgets clean |
| `accept.sh` (two-line, repeat) | 3 lanes | 7/10, **bit-identical** to the reference-source run |
| `accept.sh` (`FRUIT_BIARM=0`, 10) | 3 lanes | **6/10 = 60 %** (the standing single-arm branch, rate-only FAIL) |
| **`accept_policy.sh` (hybrid canary)** | **3 lanes** | **4/10 = 40 %** - sample 1 |
| **`accept_policy.sh` (hybrid canary)** | **3 lanes** | **4/10 = 40 %** - sample 2 |
| `accept_policy.sh` (hybrid canary) | **2 lanes (control)** | **8/10 = 80 % PASS** |

The canary's failures are the pick-station grip class (5 and 6 grip losses, one
"fruit left the pick station during the close" - the P41 class), i.e. **upstream
of the new lane**. The new body is nevertheless in the **head camera's view**
(it spans x 0.48-1.20, |y| 0.28-0.40, and the camera looks at (0.34, 0.22,
1.10)), and it changes the stage's collider set - the two channels P36 measured
as the park's mediator (the image carries it) and P71 measured as the release-y
shift. **A scene change is an input change for a policy trained on the old
scene**; two 4/10 samples against the control's 8/10 is not a draw.

## 2. Why it is not shipped

The adoption price this phase's own brief named was "**the direct/policy
interface measured**". It was measured: **8/10 -> 4/10, twice**. A default that
halves the interface of record cannot ship, whatever the scripted line does.
The third lane is a **working physical destination** (P123: 25/25 tray
agreements) - it is the *policy* that has not seen it.

## 3. What is archived for the recollection

`logs/p124/`:

* `accept_three_lane.log`, `accept_three_lane_b.log` - the scripted acceptance
  on the flipped default (7/10), plus the single-arm cell (6/10);
* `motion_reference{,_twoline,_single}_pre_p124.json` - the pre-flip records
  (`30fb99f8` / `30fb99f8` / `8952c320`), restored to `configs/`;
* the three-lane references written during the flip are **not** kept: they were
  produced from a scene that does not ship, and a reference is per scenario;
* `accept_policy_three_lane.log` / `_b.log` (4/10 each) and
  `accept_policy_two_lane.log` (8/10) - the interface measurement that decided
  it;
* `accept_restored.log` - the restore's own acceptance (8/10, `190: PASS`,
  **421/421 identical** to `logs/p123/accept_final.log`).

## 4. The named next step, and the read rule

**A policy recollection on the three-lane scene** is the precondition for the
flip: collect with `FRUIT_OUTPUT_LANES=3`, fine-tune, then the same canary must
read at or above the 2-lane control before the default moves. Until then
`FRUIT_OUTPUT_LANES=3` is **opt-in** and the third lane is a per-run capability.

**Read rule**: a scene flip is not proved by the scripted acceptance alone -
**the canary is the second leg**, and it is the one that binds here; two samples
of a non-reproducible loop are the minimum, and they were taken.
