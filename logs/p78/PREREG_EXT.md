# P78 extension pre-registration — the scoped cap at the **P77 dose (60 N)**, seeds 101/202

**Written and pinned after the S30 3-seed read and before the S60 cells run.** It is a
**declared extension**, not a rung of `PREREG.md` §3 (`logs/p76` A2 / `logs/p77` A2's
convention): the rule below was fixed with the S30 numbers already in hand, and says so.

## Why it exists

`PREREG.md` §3 chose the **lowest passing rung** and sent it to seeds 101/202. At seed 77
both S30 and S60 satisfied D1-D5 (each 0 left escapes and 0 left pries against C's 2 and 1),
so the economical rule picked **S30** — and the three-seed read then did **not** hold the
registered bar:

| pooled, seeds 77/101/202 | C (10 N shipped) | S30 (scoped 30 N) |
|---|---|---|
| left placed | 10/18 | 12/17 |
| left escapes (legs) | 8/36 | **4/32 (50 %, not <= 33 %)** |
| left pried (legs) | 3/36 | 0/32 |
| right placed | 25/27 | 22/28 (delta -3, past the -1 margin) |

So at the 30 N dose the escape class converts at **half**, not at the third the bar asks
for, and the right pays three placements. The dose the owner's question is actually about
is **60 N** — that is where P77 measured the global win (left placed 11/21 -> 17/20,
p = 0.043). The scoped form exists to carry *that* win without moving a reference, so the
open question is: **does the scoped 60 N reproduce P77's count at three seeds?**

## The cells

`S60` at seeds **101** and **202** (the `C` control cells for both seeds already exist in
this batch), same scenario, same checkpoint, same harness, one claim each, run in that
order. `S60_77` already exists from the ladder. Combined with it: a **3-seed** scoped-60
read against the same batch's three `C` cells.

## The endpoints (identical to `PREREG.md` §3)

The `[carry]` rows, `FRUIT_CARRY_DIAG=1`: left placed / `cnp` / never-held; left escapes
(`clean_slip_max > 100 mm` with a pinch); left pried (`sep_max >= 95 mm`); the
`sep_max - dia` mode split; the strawberry legs and the two crush guards; the right
(placed, escapes, new reasons); the cycle ticks; and the per-leg `force_min` split
(`place*` vs `grasp_lift`) as the site-scoping check.

## The rule (fixed now, before the cells run)

```
G1  the scoped 60 N is EVALUABLE on all three seeds   (the §1 manipulation contract)
G2  left placed: 3-seed pooled S60 > C, and not lower in 2 of 3 seeds
G3  left escapes: 3-seed pooled S60 * 3 <= C          (P77's M1 bar)
G4  left pried:   3-seed pooled S60 * 3 <= C          (P77's M2 bar)
G5  right placed: pooled S60 >= C - 1, and no new right reason
G6  cycle: median of medians <= C * 1.05
G7  zero crush legs on every S60 cell
```

**P5 (falsifier)** - if G2 fails, the scoped 60 N does **not** reproduce P77's count win
and the phase reports that the scoped form is *containment without a win*: the win in P77
was measured on a global cap that also changed the **pick** (P77 P1: the scripted attempt-0
difference was a *grasp* one, `lift=+0.411 m / 60.05 N` against `+0.138 m / 9.98 N`), and a
place-leg-only cap cannot reproduce a grasp-side effect. That is a mechanism statement, not
a null: it would say exactly which half of P77's arms the win lived in.

**P6** - if G1 fails on any cell, that cell is not evaluable and the extension reports the
manipulation, not a count.

Nothing is adopted in either case; `configs/*` is not touched; no reference is re-recorded.
