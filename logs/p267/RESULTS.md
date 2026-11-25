# P267 results: the catch tolerance's real effect is on the **true-stall rate**, not on the count

**2026-11-25, `logs/p267/`.** One env knob, two cells, and the first **attributable** number
in the 0.12 acquisition arc. **No `src/` change.**

---

## 1. The cells

0.12, `FRUIT_TRACK_DIAG=1`, 20 picks x 2 seeds per arm, the control from P266:

| arm | placed | catches | median ticks | >= 100 ticks | **true stalls** | slow-converged | cycle |
|---|---|---|---|---|---|---|---|
| C, 6 mm (shipped) | **24/40** | 34 | 24 | 11 | **10 (29 %)** | 1 | 9.65 s |
| **T, 7 mm** | **32/40** | 36 | 23 | 11 | **3 (8 %)** | 6 | 9.71 s |

**The count is a branch and is not claimed** (the arms' sequences are identical for the
first 6 picks and then re-draw - P266's own caveat). **What is attributable is the class**:
a *true stall* is a physical state (residual **> 20 mm** at the exit), not a scored outcome,
so **10 of 34 catches against 3 of 36** is a catch-level statement (p ~ 0.03) with the
attempts being different instances.

## 2. And it is the *same number* as P266's guard, by a different route

| lever | how it shortens the chase | true stalls |
|---|---|---|
| P266 guard (`STALL_TICKS=60`) | breaks when the residual plateaus | **10 -> 3** |
| **P267 tolerance (6 -> 7 mm)** | exits the axis window 1 mm earlier | **10 -> 3** |

**Two different truncations, the same 3.** That is the mechanism: **the long chase is itself
the damage.** The pads spend the budget **in contact** with a fruit they are not converging
on, and the acquisition degrades; stop the chase earlier either way and most of the stalls
never happen. (P266 could not adopt its route because it also truncated chases that were
*converging* - the tolerance does not have that defect, because it truncates only inside the
window it declares as success.)

## 3. Why it is still **not adopted**: the boundary it crosses is a measured one

* **P48 measured 6 mm as the grasp/no-grasp boundary** (`8/8 no-grasp above 6 mm`) - but on
  the **pre-axis-exit** loop, where the norm was the whole test; the axis exit (P243) already
  allows `|z| <= 10`, so the "6 mm" of the shipped cell is now a **y-only** bound.
* At 7 mm the close starts with **|y| <= 7**, i.e. at worst 1 mm further off than today.
  The measured count went the right way (+8, a branch) and **no place-side loss appeared**,
  but **one draw per arm cannot certify a 1 mm change against a boundary P48 measured on a
  different loop**.

**So the tolerance stays at 6 mm, and the phase records the class statistic instead.** A
promotion owes P93's powered shape (>= 40 per arm at two seeds) with the **catch-level
true-stall rate** as the primary and the count as the report - the same shape the axis exit
itself used (P248).

## 4. The mechanism-based form of the same lever, named

The two truncations agree that *driving the chase hurts*. The honest form is therefore not a
clock and not a tolerance - it is a **force** criterion: during the catch-up the pads are
already reading the tactile force every tick (`follow_centre` runs), so the loop can exit
when **the contact force is high while the residual is not falling** - "we are pushing the
fruit, not closing on it". That distinguishes a converging chase from a shoving one
*physically*, which is exactly the distinction P266 could not make with a clock.

**Not built**: it is a new exit condition on the shared catch path, so it owes a
pre-registration with the catch-level stall rate as its endpoint and P103's interval price
registered in advance.

## 5. No-harm

No `src/` or `configs/` change (the tree is P266's: `tasks.py` `835ce78f`, references
**`61fb5202` / `61fb5202` / `18b101bf`**, ckpt `p227_panda156`); `scripts/selfcheck.sh`
**PASS (0 failures, 1 skipped)**; `accept.sh` stands at P266's **459/459 +
`fingerprint: matches`**. Evidence `logs/p267/`.
