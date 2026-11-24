# P246 results: the first-attempt excursion is not initialisation, not the diag, and not attributable

**2026-11-25, `logs/p246/` is a **reading of existing logs** - no cell was run.**

---

## 1. The hypothesis this tests

P245 left one object open: **seed 901's first catch** is an excursion in 5 of 5
cells, while the P236-P240 cells (which ran seed 901 without the catch row) show
none. The natural hypothesis was **initialisation**: the first episode primed the
belt with a fruit far upstream and the arm still parked, so the catch-up's
200-tick / 200 mm budget could not close the gap.

## 2. It is refuted by the logs already on disk

Every run's **episode 0** line prints the fruit, the arm and the arrival position:

| log | episode 0 |
|---|---|
| P245 s901 (**excursion**) | `lychee grade=A d=2.8cm arm=left y=+0.596` |
| P245 s902 (**clean**) | `strawberry grade=A d=3.1cm arm=left y=+0.610` |
| P236 s901 (**clean**) | `lychee grade=A d=2.8cm arm=left y=+0.596` |
| P233 s901 (0.18) | `kiwi grade=A d=6.4cm arm=left y=+0.652` |

**The same fruit, the same arm and the same `y` appear in a cell that is clean
(P236) and in one that is not (P245)**; and seed 902's first fruit is *further*
upstream (+0.610) and clean. So the "first fruit is far and the arm is parked"
story does not decide it.

**The mechanisms named in P245 are refuted too**:

* **not the catch-row diagnostic**: P239/P240 ran it and are clean (18 attempts,
  none), and P245 ran *only* it and is not;
* **not the cycle report**: P241-P244 all had it and all show an excursion; P245
  did not have it and shows one too;
* **not the per-tick component subtraction**: P245 removed it (P244's own control)
  and the excursion stays;
* **not the command offset**: it appears with the shipped command (P243/P245).

**No measured variable separates the clean cells from the excursion cells.**

## 3. What that means, stated plainly

The excursion is **real, reproducible in some runs, and unattributed**. Its cost
is bounded and small: **at most one episode per run** (the first), **0-1
placement**, and it never recurs in the five later episodes of the same run. The
record's rule applies: **an unexplained class is not a lever and must not be
narrated as one** - so it is closed here as **open, with its bounds measured**, and
**no rate is quoted** for it (the earlier "7 %" was withdrawn in P244 and this
phase removes the last mechanism that could have supported a variant of it).

## 4. What is established for the objective (unchanged by any of this)

| | |
|---|---|
| **0.08 m/s** | **11/12 = 91.7 %**, cycle ~13.3 s |
| the catch-up's exit is a **6.6 mm vertical steady-state error** | P241 |
| the shipped loop therefore exits on its **200-tick budget** | P239, 1.67 s |
| the **axis-aware exit recovers 1.44 s on 11 of 12**, command untouched | P243 → cycle **~11.9 s (-11 %)** |
| the excursion is none of: the field, the offset, the diag, the first fruit, the cycle report | P243-P246 |

**So the speed arc is complete on its own terms**: a measured mechanism, a
zero-quality-price recovery, and one **bounded unexplained class** that costs at
most one placement per run and is documented with its instrument rather than
explained away.

## 5. Pins

No `src/` change; `tasks.py` **`9ce34845`**, `rl_env.py` unchanged by this phase;
references **`61fb5202` / `61fb5202` / `18b101bf`** untouched; checkpoint
`p227_panda156`. Evidence: the logs cited in §2 (`logs/p245/diag12/`,
`logs/p236/blocks/`, `logs/p233/A_stale/`).
