# P120 - the 60 N jaw: a +10-point screen that does not replicate, so the shipped 10 N stays

Owner's answer to the scene-lane closure: **"可以动场景和硬件啊 只是不改那些基本要求"** -
the scene *and* the hardware are on the table, only the dynamic scattered pipeline
(no diverter / stop gate / guide / pause) is fixed. The one hardware lever the
record has a **success** measurement for is the clamp force: P77's direct-line
cell read **left 11/21 -> 17/20** at 60 N (Fisher p = 0.043), and it had **never
been measured on the shipped scripted two-line**. This phase measured it there
and then replicated.

**Verdict: NOT ADOPTED. The shipped 10 N stays** (the owner's decision, and the
pre-registered replication agrees: the +10-point screen was a branch draw).

## 1. The four-seed screen (20 attempts/seed, same-seed controls)

| seed | control (10 N) | treatment (60 N) | delta |
| --- | --- | --- | --- |
| 5 | 16/20 | 18/20 | +2 |
| 6 | 12/20 | 15/20 | +3 |
| 101 | 15/20 | 14/20 | -1 |
| 202 | 15/20 | 19/20 | +4 |
| **pooled** | **58/80 = 72.5 %** | **66/80 = 82.5 %** | **+10.0 pts, Fisher p = 0.1846** |

Mechanism-side numbers (branch-free): the escape census (`clean_slip_max > 100 mm`
on a carry leg) fell **22 -> 12 legs**, and the pooled interval **11.34 -> 10.63 s**
(-6.3 %). The class was **not deleted** (12 legs still escaped; one landing miss
at seed 101, `final=(0.472, +0.803, 1.199)`, `on_belt=False`, `roll=-15 /
skid=-215 mm`). `[drive]` read the 60.00 N cap back on both joints' drive
(`joint2` is the drive-less mimic), so the arm under test was really at 60 N.

## 2. The pre-registered replication (`PREREG.md` md5 `b9b7ec5c`, pinned before the cells finished)

Rule, pinned: the direction is credible only if **both** new seeds are not
negative **and** the pooled six-seed Fisher p <= 0.10.

| seed | control (10 N) | treatment (60 N) | delta |
| --- | --- | --- | --- |
| 303 | 16/20 | 14/20 | **-2** |
| 404 | 16/20 | 17/20 | +1 |
| **pair** | **32/40** | **31/40** | **-1, Fisher p = 1.0** |

**Both clauses fail**: 303 is negative, and the pooled six-seed cells read
**97/120 = 80.8 % against 90/120 = 75.0 %, Fisher p = 0.3505**. The escape census
also stops moving the right way (303: 6 legs against its control's 3; 404: 2
against 3).

So the four-seed +10 points was **one branch draw**, exactly the shape P93's
four-seed rule exists to catch - and the same shape the *scoped* 60 N arms
already had (P78's `place-left` p = 0.50, P79's `grasp-left` p = 0.16). The
direct line's P77 number (+6, p = 0.043) stays that interface's own result; it
does not transfer to the scripted cell.

## 3. What is recorded about the two costs

* **The landing**: one payload-present release off the belt (seed 101) - a
  release/landing event, not an upstream loss. If 60 N were ever revisited, the
  release block would need its own cell.
* **The crush guard is not readable in these cells**: `sep@loss=n/a` on the legs
  that did not lose the payload, so the guard is the precedent P76's own 60 N
  strawberry row (`sep@loss - dia = +0.5 mm` at a 36.1 mm span, 60.16 N). The
  real bruise question cannot be answered in this sim at all (no bruise model).

## 4. Decision

`FRUIT_FINGER_MAXFORCE` stays **unset** (the shipped 10 N). No `src/`, `configs/`
or reference change; no store re-baselined. The 60 N lane is archived as a
**measured draw on the scripted cell**, and the remaining success levers are not
force or scene: P50's delivered-x compensation (the 25 % acquisition class) and
the policy/interface lane.

Evidence: `logs/p120/mf60_s{5,6,101,202,303,404}.log`, `ctrl_s{303,404}.log`,
`PREREG.md` (`b9b7ec5c`), `PREREG.md5`, `report.py`.
