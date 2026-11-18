# P211 result - the small-fruit selector floor does not convert the small class

The last software lever the record left for the 3.0-3.4 cm fruit is selection timing: a
size-conditioned extra floor that refuses a small fruit too close to the station instead
of spending the attempt. It binds (`[bed-sel]` rows), but it does **not** make a small
fruit graspable, and the pooled count is a draw.

| cell | seed | placed | small fruit attempted / placed | notes |
|---|---|---:|---|---|
| control (E4/R5) | 808 | **4/6** | 1 / 0 | 3.1 cm lychee fails; a 6.5 cm right apple fails |
| `EXTRA=0.15` | 808 | **5/6** | 1 / 0 | only the 3.1 cm lychee at +0.565 (above the 0.549 floor) is attempted; all five large fruit place |
| `EXTRA=0.25` | 808 | 3/6 | 1 / 0 | the +0.475 lychee is refused, but a **3.3 cm strawberry at +0.673** (above the 0.649 floor) is attempted and fails; then a right apple and a 6.6 cm orange fail |
| control (E4/R5) | 303 | 3/6 | 0 / 0 | orange/pear failures (not small) |
| `EXTRA=0.15` | 303 | 3/6 | 1 / 0 | 3.0 cm lychee at +0.614 is above the 0.549 floor, attempted, fails |

**What the floor actually does.** The `[bed-sel]` rows show the small candidates refused
(`0.184 < 0.549`, `0.255 < 0.549`, `0.403 < 0.549`, ...) and the large ones chosen. The
0.15 seed-808 cell's 5/6 is therefore a **selection effect**: it attempts one small fruit
and five large ones, and the large ones all place. It is not a grip conversion - the small
fruit it does attempt still fail. The 0.25 cell admits a **3.3 cm strawberry at +0.673**,
i.e. 0.27 m above the normal floor, and that still fails: the class is not "the fruit is
too close"; it is the hand/perception limit on a small object.

**The count is a draw**: 0.15 pooled **8/12** against the control's **7/12** (+1), 0.25
**3/6** (-1 against its same-seed control). The dose is non-monotone and the difference is
one attempt. A floor high enough to skip the class entirely (> 0.45 m) would discard 3-5
of the 16-fruit pool - a yield trade, not a sorting improvement. **Not adopted; the small
class remains the hardware/perception residual.**

The knob is default 0 and direct-only; the `[bed-sel]` diag is reporting only. `TASKS_MD5`
is updated because the selector carries the two parsers.

**Pins.** `tasks.py` **`d1b18e2a`**, `rl_env.py` **`d6198b9a`**,
`scripts/274_p211_small_select_selftest.py` **`56f12c8e`**, `selfcheck.sh`
**`a3d85726`**; evidence `logs/p211/{PREREG,RESULTS}.md`, `S_s808`, `S25_s808`,
`S_s303` and their manifests.
