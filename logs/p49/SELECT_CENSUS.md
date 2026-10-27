# P49 phase 1 — the scripted selector's x-ceiling: the selection census

Offline phase: **no simulator, no `src/` edit, no commit.** Tree read clean at HEAD
`ebc2c9c`; `tasks.py` **`b6de439c`**, `rl_env.py` `93e35ef7`, `fruits.py`
`dff684b1`, `scene.py` `27e3d64a`, `configs/motion_reference.json` **`8a399626`**,
`..._twoline.json` **`2246f83c`** — i.e. exactly the P44 pin, so every P44/P45/P46
log below was produced by this source. The files written are this one,
`PREREG.md` and the read-only reader (`select_census.py` -> `select_census_out.txt`).

The question: **P48 named a scripted selector x-ceiling as the next lever (the
delivered-x tail is 0/6 placed above 0.39, p = 2.1e-11). Where does the chosen
fruit's x actually sit, how often would a ceiling at 0.39/0.40/0.42 refuse, is
there a legal substitute when it does, and what does a refusal cost?**

The answers in order, before the tables:

1. **The chosen x is a tight distribution with a 1.7 % tail**: pooled unique
   p50 **0.276**, p90 **0.347**, max **0.3969** (the *delivered* value; §1.3
   bounds the selection value from below); **3 of 174 unique attempts
   (1.7 %) above 0.39, 0 above 0.40, 0 above 0.42**. So on this corpus the
   *only* ceiling with any action is 0.39, and its action is confined to the
   0.390-0.397 window; 0.40 and 0.42 are measured no-ops.
2. **The usable set is one fruit, nearly always**: across the 40 selection
   instants that carry a full live-set census, 25 (62.5 %) had exactly **one**
   eligible fruit above the catch floor, 14 (35 %) had two, **none had three**,
   and the usable population's x never exceeds **0.369** — 21 mm inside the
   registered ceiling. A ceiling at 0.39 therefore refuses **0/40** on the
   shipped acceptance and pear scenarios.
3. **A binding refusal is a skip 60 % of the time** (no second eligible fruit
   exists), and when a substitute does exist it is *cheaper* than the fruit it
   replaced (the shipped rule's substitute is the nearer one: +0.88 to +2.08 s
   of belt travel saved). The cost of the skip is **1-5 attempt slots of the
   ten** (0.5 s each), because the refused fruit's x is constant and the slot
   resumes only when a *different*, legal fruit crosses the floor.
4. **The three tail events reduce to two instances**, and their alternatives are
   **not in the record**: no arm that carries them ran `FRUIT_BED_DIAG`, and the
   only live-set proxy they print (`queue`) is a 0.50 m along-band count that is
   not the floored set. Whether a ceiling would have *converted* or only
   *skipped* them is unanswerable offline — it is what phase 2's event-bearing
   arm measures (`PREREG.md` E1/E2).

---

## 1. The full live-set corpora (`[bed-sel]`, `FRUIT_BED_DIAG=1`)

Four logs in this tree's history carry a per-attempt live-set census on the
**shipped** scenario, all at seed 5:

| log | scenario | selection rule |
| --- | --- | --- |
| `logs/p43/p2/d0_accept_A_s5.log` | shipped acceptance (`scatter pool=16`) | **shipped farthest-upstream** |
| `logs/p43/p2/d0_pear_A_s5.log` | pear (`FRUIT_SUPPLY_SPECIES=pear`) | shipped farthest-upstream |
| `logs/p43/p2/r_accept_B_s5_diag.log` | shipped acceptance | P43 nearest-above-floor (cross-check) |
| `logs/p43/p2/r_pear_B_s5_diag.log` | pear | nearest-above-floor (cross-check) |

The two shipped-rule logs are the population of record; the two nearest-rule logs
are a cross-check of the *sets* (each block is an independent reading of the belt,
whatever rule chose from it).

### 1.1 The sets

| quantity | value |
| --- | --- |
| selection instants | **40** (4 logs x 10 attempts) |
| usable-set size | **1** in 25 (62.5 %), **2** in 14 (35.0 %), **0** in 1 (2.5 %), **>= 3 in 0** |
| usable candidate x | n=53, min **0.209**, p50 0.258, p90 0.349, max **0.369** |
| chosen x | n=39, min 0.209, p50 0.261, p90 0.334, max **0.365** |
| `live` on the belt at selection | 2-6 (median 3); the `live` count also includes output-lane fruit |

The two-candidate blocks are the whole population a substitution could ever draw
on, so the arithmetic in §3 is exhaustive for this scenario:

| block | chosen (x / along) | the other usable fruit (x / along) |
| --- | --- | --- |
| accept att 1 | 0.229 / +0.670 | 0.243 / +0.435 |
| accept att 9 | 0.224 / +0.661 | 0.369 / +0.411 |
| pear att 0 | 0.291 / +0.653 | 0.239 / +0.417 |
| pear att 3 | 0.211 / +0.674 | 0.331 / +0.545 |
| pear att 5 | 0.330 / +0.678 | 0.211 / +0.528 |
| pear att 6 | 0.212 / +0.675 | 0.257 / +0.547 |
| pear att 9 | 0.262 / +0.527 | 0.331 / +0.422 |

**Nothing in this corpus is near the ceiling**: the largest usable x is 0.369
(`accept` att 9) and the largest chosen x is 0.365 (att 0). The census's first
result is therefore negative in the strongest form available offline — *the
shipped acceptance/pear line never presents a fruit the registered ceiling would
refuse.*

### 1.2 The instrument is print-only (why a census can sit inside an arm)

`d0_accept_A_s5.log` (`FRUIT_BED_DIAG=1`) versus `post_revert_accept_unset.log`
(no diag), same scenario, same tree: **387/387 `[fruit]` lines identical** once
the `[bed-*]`/`[supply-diag]`/`[feed]` rows are filtered out. The bed census adds
print rows and one fruit-pose read; it touches no control input. (P44's batch
header already stated this equality; this is the re-derivation.)

### 1.3 Is the chosen x the x at the wait loop? (the "drift" question)

The block reads the chosen fruit's x **at the selection**; the attempt's own
`wait step=0` row reads it **1.64 s later** (0.197 m of belt travel, §3.3). The
difference, over the same 39 selections:

| | value |
| --- | --- |
| `chosen_x (selection) - fruit_x (wait loop)` | n=39, min **-19.2 mm**, p50 **-0.1 mm**, p90 +0.3 mm, max +2.7 mm |
| agreement to <= 2.7 mm | **34/39 selections** |
| larger moves | **5/39**: 5.3, 12.3, 13.0, 18.9, **19.2 mm**, all **-x** (the fruit moves *outward*, +x), all on the **acceptance's stocked belt**, none on the pear |

Read with P38 phase 1 (the transport's lateral contribution is **exactly
0.000 mm** over 475 transits), the x is a constant of the *transport*; the
5-19 mm moves are **post-selection motion on the belt**, not transport — they are
P38's own named "open residual 5-20 mm ... a pair depenetration" (two fruit
released abreast within 0.10-0.16 m of each other push apart as PhysX resolves
the overlap). So:

* the **selection x is the delivered x to -0.1 mm median**, with a **13 %
  (5/39) chance of a 5-19 mm outward move** between the selection and the wait
  loop;
* therefore a wait-loop tail value is a **selection-time value within that
  bound**: E1's **0.3969** implies a selection x in **[0.378, 0.397]**, i.e.
  above the 0.39 ceiling **iff the move was < 6.9 mm** — which holds in 34/39 of
  the measured population. **The census cannot settle E1's selection x; the
  phase-2 event arm prints it** (`[xsel]`/`[bed-sel]` read the selection
  instant), and that is now a named question rather than an assumption.

---

## 2. The chosen-x distribution (every corpus, `wait step=0 fruit_x=`)

`x` is the lateral belt coordinate: spawn band **0.20-0.36**, measured clean
reach **0.18-0.39** with a hard cliff at **0.42** (P34/P38/P47); the pick station
sits at x ~ 0.333, so the tail that matters is the **high** side.

Why `wait step=0` is taken as the selection's x — with a **measured 5-19 mm
exception**: the transport contributes exactly 0.000 mm of lateral motion (P38
phase 1), and 34 of 39 selections agree between the block's selection read and
the wait-loop read to <= 2.7 mm (median -0.1 mm). But **5 of 39 move 5.3-19.2 mm
outward** between the two instants (post-selection belt motion, P38's
pair-depenetration residual — §1.3). So the wait-loop value is the *delivered* x
and an upper bound on the selection x, not an identity; §1.3 carries the bound
and what it leaves open for the tail.

| corpus | logs | n | min | p50 | p90 | max | >0.39 | >0.40 | >0.42 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| shipped (`p39/p3`, `p41/p2`) | 5 | 48 | 0.209 | 0.285 | 0.351 | **0.3653** | 0 | 0 | 0 |
| _of which this tree (`p41/p2` only)_ | 3 | 29 | 0.209 | 0.260 | 0.331 | 0.3653 | 0 | 0 | 0 |
| P44 speed arms (`p44/p2`) | 14 | 139 | 0.201 | 0.276 | 0.365 | **0.3969** | 2 | 0 | 0 |
| P45 mass arms (`p45/p2`) | 10 | 99 | 0.193 | 0.273 | 0.351 | **0.3653** | 0 | 0 | 0 |
| two-line (`p46/p1` + `p44/p2`) | 6 | 60 | 0.204 | 0.308 | 0.367 | **0.3908** | 4 | 0 | 0 |
| **pooled raw rows** | 35 | **346** | 0.193 | 0.281 | 0.354 | **0.3969** | **6** | **0** | **0** |
| **pooled unique attempts** | — | **174** | 0.193 | **0.276** | **0.347** | **0.3969** | **3 (1.7 %)** | **0** | **0** |

Dedupe rule: a bit-identical replay of one attempt across arms collapses on
`(x@4dp, species, diameter)` — the P44/P45 cells replay the same seed-5 run, and
the two-line's E3 appears in four logs. 346 raw rows -> 174 unique. (A *distinct*
attempt that drew the same x to 4 dp would also collapse; at this precision none
is detectable, and the tail rows below are individually identifiable.)

Provenance note: the `shipped` corpus's two `p39/p3` logs are the **P39 tree**
(`scene.py 988985ef`, pre-P41 finger profile). `x` is a supply property (spawn
draw + per-instance release offset), so they are included for the distribution —
and the `_of which this tree_` row carries the same-tree subset alone: it moves
the p50 by 5 mm and the max not at all.

The three unique rows above 0.39:

| x | species | dia | arm | outcome | log | what it is |
| --- | --- | --- | --- | --- | --- | --- |
| **0.3969** | kiwi | 5.6 | left | no-grasp | `p44/p2/accept_s5_S2.log` att 1 | **E1** |
| **0.3966** | kiwi | 5.6 | left | no-grasp | `p44/p2/amend_F_S2.log` att 1 | **E2** (the same instance, the S2 cell re-run) |
| **0.3908** | kiwi | 5.4 | left | no-grasp | `p46/p1/twoline_s5_C.log` (+3 replays) | **E3** (two-line) |

**The tail is instance- and cell-bound.** Every corpus's max is a *different*
value at the same order (0.3653 shipped, 0.3969 P44, 0.3653 P45, 0.3908
two-line), and within P44 the tail appears in **one cell of fourteen**
(`FRUIT_SPEED_RELEASE=1`, i.e. S2: the release dwell 20 -> 0). The shipped
acceptance's own branch (C) tops out at **0.3653** — 25 mm inside the ceiling —
and its S13 union arm at the same seed also tops out at 0.3653. So a 10-attempt
arm at seed 5 carries the event only if its *timing* happens to present that
kiwi at the floor: measured incidence **2 of 29 single-arm runs in the corpus,
both the S2 cell** (the same instance drawn twice).

---

## 3. The refusal arithmetic

### 3.1 How many attempts would refuse the chosen fruit

| ceiling | full live-set corpus (n=40) | pooled unique attempts (n=174) | per corpus (unique) |
| --- | --- | --- | --- |
| **0.390** | **0** | **3 (1.7 %)** | shipped 0/33, P44 **2/73**, P45 0/33, two-line **1/35** |
| **0.400** | 0 | **0** | — |
| **0.420** | 0 | **0** | — |

The 3 are E1/E2/E3 (§2). The registered 0.39 is thus the *only* value with any
action on this corpus, and it is a ~1.7 %-of-attempts event; 0.40 and 0.42 are
both measured no-ops here (the corpus contains **no** fruit between 0.3969 and
the 0.42 cliff, so the cliff itself is never approached).

### 3.2 The next eligible fruit: availability, and the substitution's sign

Rule as registered: keep the usable set (at/above the catch floor **0.399**), drop
everything with `x > ceiling`, then let the shipped farthest-upstream rule take
the largest `along` of what remains; if nothing remains, the slot is refused.

* On the 40 full-set selections: **0 refusals**, therefore **0 substitutions**
  and **0 skips**. The ceiling is inert on the shipped acceptance/pear at these
  seeds — not "measured harmless", *unexercised*.
* The structural bound that a binding ceiling would meet: the usable set has
  **1** candidate in 25/40 selections (62.5 %) — there is then **no substitute at
  all, so the slot is a skip** — and **2** in 14/40 (35 %), where a substitute
  exists only if the *other* fruit is inside the ceiling. **No selection in the
  corpus had 3+ candidates**, so "try the next eligible fruit" can never be more
  than one deep on this line.
* The substitution's cost, measured on the 7 two-candidate blocks that the
  shipped rule selected (and the 7 the nearest rule selected): the substitute is
  the *nearer* fruit under the shipped rule (d_along **+0.105 to +0.250 m = +0.88
  to +2.08 s** of belt travel), i.e. **a substitution saves time**, it does not
  cost it. Under the nearest rule the sign flips (-0.88 to -2.03 s), which is
  what makes that rule a different lever (P43 L1) and not this one.
* Sanity on the substitute's legality: it is still above the 0.399 floor by
  construction, so the catch's setup (1.5 s of belt travel) still fits — the
  substitution does not spend the floor's margin, it spends the *chosen fruit's*
  extra lead.

### 3.3 The skip cost

The driver's loop (`scripts/20_pick_place.py`) advances **60 ticks (0.5 s =
60 mm of belt travel) before every selection**, then selects; a `no eligible
fruit` result `continue`s to the next attempt index. Therefore:

| quantity | value |
| --- | --- |
| a refused slot's direct cost | **1 of the `ATTEMPTS` budget** and **0.5 s of sim** (not a 15 s cycle) |
| selection -> `wait step=0` offset (measured) | 0.185-0.211 m, **p50 0.197 m = 1.64 s** |
| selection-time `along` of the chosen fruit | 0.415-0.678 m, **p50 0.527** against the 0.399 floor |
| slots a refused fruit stays *selectable* (above the floor) | **0.3-4.7, p50 2.1** — but it never becomes legal again (its x is a constant) |
| what ends the skip | a **different** fruit crossing the floor: supply gaps 0.10-0.35 m = 0.8-2.9 s = **2-6 slots** |
| realised skip (E1's instant, `queue=2`) | 1 other fruit in the band -> **1-3 slots** |

So a binding refusal with no substitute burns **~1-5 of ten attempts** (a lost
placement opportunity at the line's 0.6 rate = 0.6-3 placements) and leaves the
refused fruit to ride past — while **the refused fruit was 0-for-6 in P48's
population**, i.e. it was going to be a failure anyway. That asymmetry is the
whole economics of the lever: it re-allocates an attempt that would have failed,
and it pays for the re-allocation in waiting. (The refused instance is **not**
permanently excluded: `FruitSpawner.respawn` draws a fresh `x` from
`[x_min, x_max]` for the scatter schedule on every recycle, so the same body can
return at a legal x.)

---

## 4. The tail events — and what the record does *not* hold

| | **E1** | **E2** | **E3** | **E4** |
| --- | --- | --- | --- | --- |
| log | `p44/p2/accept_s5_S2` | `p44/p2/amend_F_S2` | `p46/p1/twoline_s5_C` | `p46/p1/twoline_s6_C` |
| attempt | 1 | 1 | left, 1st | right, 1st |
| species / dia / arm | kiwi 5.6 / left | kiwi 5.6 / left | kiwi 5.4 / left | kiwi / right |
| **chosen x** | **+0.3969** | **+0.3966** | **+0.3908** | +0.2730 |
| `dy0` at wait step 0 | +0.3849 | +0.4420 | +0.4486 | +0.3902 |
| `queue` at hand-over | **2** | **2** | **3** | 4 |
| catch-up residual | 219.6 mm | 245.8 mm | 251.0 mm | 480.6 mm |
| `approach ... end=` | 15.3 mm | 14.8 mm | 10.1 mm | 10.6 mm |
| outcome | no-grasp | no-grasp | no-grasp | no-grasp |

**What `queue` can and cannot say.** `_queue_depth()` counts fruit with
`along ∈ [pick_y - 0.05, pick_y + 0.45]` — **not** the floored set: it includes
candidates below the 0.399 catch floor, and at the hand-over instant the selected
fruit itself is inside it. So `queue=2` says "one other fruit in a 0.50 m band,
1.64 s after the selection (0.197 m of belt travel)", and says nothing about that
fruit's x. The census therefore **cannot** answer the question the lever turns on
(would a substitute have existed at E1's instant?) from these logs: no arm that
carries E1/E2/E3 ran `FRUIT_BED_DIAG`, and `FRUIT_SUPPLY_DIAG` prints counts, not
positions. That is a measured instrumentation gap, and it is a phase-2 condition
(§PREREG C1): the event-bearing arm runs **with** the bed census on **both**
sides, which turns the refusal's substitute into a read value instead of an
inference.

**Correction to P48 §2 (recorded, not a re-run).** P48's event table reads
`queue = 5` for E3. The two-line prints one hand-over row per arm per window and
they are **not** ordered right-then-left (`twoline_s6`'s second window prints the
left row first), so a global-order read lands on the *other* arm. Each hand-over
row carries its own station (`station = fruit_y - dy`, 0.10 m apart): the left
kiwi's row is `fruit_y = 0.1849 -> station 0.000, queue = 3`; the `5` belongs to
the right arm's row of the same window (`fruit_y = 0.0874 -> station -0.100`).
E1/E2 (`2`) and E4 (`4`, and E4 *is* the right arm) stand unchanged. The
correction does not move P48's conclusions — `queue` was quoted as a bound, not a
mechanism — but the value of record is **3**.

**What the ceiling can reach.** E1 and E2 are the *same instance* in the S2 cell;
E3 is the two-line, whose selector returns before the rule (§5) — so the knob has
exactly **one** opportunity in 174 unique attempts of this corpus, and it lives
in a cell the primary battery does not otherwise run. That is why the
pre-registration adds an **event-bearing arm** rather than trusting the
acceptance's own branch.

---

## 5. The 0.42 cliff, and why the two-line keeps its own rule

The shipped selector's return order (`tasks.py select_target`, from `:5797`):

1. `_reach_anywhere_active()` -> `_reach_anywhere_select` (opt-in; off);
2. `floor = pick_y + _dynamic_select_floor()`; `usable = along >= floor`;
3. `lane is not None` -> `usable[0]` — **the shared-station worker**;
4. `prefer_lane is not None` -> the lane/grade rule — **the two-line**;
5. `FRUIT_SELECT_NEAREST_ABOVE_FLOOR` (off) / `_balance_arm` -> the
   **farthest-upstream pick** — the scripted single-arm line.

A ceiling in step 5 is **unreachable from steps 3 and 4**: the two-line returns
earlier, and so does the opt-in shared-station worker. That is not an accident of
placement — it is the correct scope:

* the two-line's per-arm **station separation is its clearance mechanism** (W2:
  left y = 0.00, right y = -0.10), and its eligibility is the **per-arm grade**
  (W3 pure routing). A global x-ceiling is a *belt* predicate: it would refuse a
  whole arm's stream off its own delivered-x tail, which is the R5/V1
  lane-starvation repeat, not a grip fix;
* its own reference `configs/motion_reference_twoline.json` (`2246f83c`) would
  move for a lever with no measured mechanism on that path;
* and the two-line's selection is **nearest-in-lane**, not farthest-upstream, so
  the "next eligible" semantics registered here do not even apply to it.

Its delivered x, for the record: left n=30 p50 0.315 max **0.3908**; right n=30
p50 0.273 max 0.3674 — the left lane carries the same tail, and E3 is on the left
arm.

**The 0.42 cliff** is the measured outer edge of the clean reach band
(0.18-0.39 clean, cliff at 0.42). The corpus's largest chosen x (0.3969) and
largest usable candidate (0.369) both sit **inside** it, so 0.42 — and 0.40 —
are unexercised no-ops on this corpus: the only ceiling with any action is the
registered 0.39, and its action is a 0.390-0.397 window.

---

## 6. What this settles, and what it does not claim

**Settled.**

1. The chosen x (**delivered**, at the wait loop) is p50 0.276 / p90 0.347 / max
   0.3969 over 174 unique attempts; **> 0.39 is 3 rows = 1.7 %, > 0.40 and
   > 0.42 are 0**. The tail is **instance- and cell-bound** (2 of 29 single-arm
   runs, both S2; the shipped C branch tops out at 0.3653).
2. **The shipped acceptance/pear line presents no fruit a 0.39 ceiling would
   refuse at the selection instant** (0/40 full-set selections; the chosen x at
   selection maxes at 0.3650, the usable population at 0.369). So a ceiling arm
   on that branch is an *inertness* test, predicted byte-identical, not a
   conversion test.
3. **The selection x and the delivered x differ by -0.1 mm median, but not
   always**: 34/39 selections agree to <= 2.7 mm and **5/39 move 5.3-19.2 mm
   outward** between the selection and the wait loop (post-selection belt
   motion; P38's pair-depenetration residual, transport itself is 0.000 mm). A
   tail *delivered* value therefore bounds its selection value from below: E1's
   0.3969 -> a selection x in **[0.378, 0.397]**, above 0.39 iff the move was
   < 6.9 mm (true in 34/39 of the measured population). **The census cannot
   settle E1's selection x** — the event arm reads it directly.
4. **A binding refusal is a skip with ~60 % probability** (one eligible fruit),
   one substitute deep at most (never 3 candidates in 40 selections), and the
   substitute *saves* 0.9-2.1 s of belt travel. The skip burns 1-5 of the ten
   attempts at 0.5 s each.
5. **The events' alternatives are not in the record.** No arm that carries a tail
   instance ran the bed census, and `queue` is not the floored set. Phase 2 must
   measure the substitute, not infer it.
6. **The two-line and the shared-station worker cannot reach the rule** (the
   selector returns at `lane`/`prefer_lane` before it), and must not.

**What it does not claim.** No rate: every count is a deterministic branch's
count (AGENTS §2), and the tail rows are instance-bound, so a battery on a branch
that does not draw them **cannot** re-measure them. No claim about the direct or
policy interfaces (they pass `direct=True`, and §PREREG scopes the knob off
there). No claim that the 0.39 ceiling is the *right* value — the corpus only
says 0.40 and 0.42 are empty and 0.39 is a 1.7 % tail; the clean-band edge (0.39)
is P34's measurement, not this census's. And **no claim that the lever is inert
by construction**: it refuses nothing on the *shipped C branch* (0/40), but the
population contains 3 tail presentations and 1.3 of them (by the 34/39 frequency)
would be refused at the selection instant — which is a measurement the event arm
owes, not an inference either way.

**Corrections carried here.** (i) P48 §2's `queue = 5` for E3 -> **3** (§4). (ii)
`queue` is a 0.50 m along-band depth, not a floored-window count — P48 used it as
a bound, which is what it is. (iii) The substitution's sign depends on the
selection rule; the shipped rule's is a *saving*. (iv) The `wait step=0` value is
the **delivered** x and only an upper bound on the selection x (§1.3): a
statement about "the chosen fruit's x" must say which instant it means.

Evidence: `logs/p49/select_census.py` (the reader) and
`logs/p49/select_census_out.txt` (its full output: per-block live sets, per-log
and pooled x tables with both dedupe levels, the ceiling/refusal tables, the
substitution table, the skip-cost arithmetic, the event rows, the selector return
order). Every log cited is an existing artefact of P39/P41/P43/P44/P45/P46/P48.
