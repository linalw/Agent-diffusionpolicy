# P1c RESULTS: the composition-controlled test **refutes** the density lever on the single-arm line

Branch `p-supply`. Pre-registration: `logs/p1c/PREREGISTRATION.md`. This is the test the Oracle
review named as the decisive one (`logs/p3/ORACLE_REVIEW.md`).

## 1. What was run

The presented class multiset is held fixed **by construction**: a **one-species pool**
(`FRUIT_SUPPLY_SPECIES=apple`, added for this test - neither mix knob could express one, because
`_mix_env` rejects a weight of 0, so the first attempt with `FRUIT_SUPPLY_GRADES=apple:1` was
silently rejected with its own warning and ran the *mixed* pool; that attempt is void and is not
used). Single arm, patch sheet, SEED=5.

| config | slots | real attempts | placed | success | empty slots | sim | s/attempt | placed/min |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **D=1.00** | 20 | 20 | 13 | **65 %** | **0** | 307.3 s | 15.4 | **2.54** |
| **D=1.60** | 20 | 6 | 1 | **17 %** | **14 (70 %)** | 95.7 s | 15.9 | 0.63 |
| D=1.60 (double) | 20 | 6 | 1 | 17 % | 14 | 95.7 s | 15.9 | 0.63 |
| D=1.60, 40 slots | 40 | 10 | 3 | 30 % | **30 (75 %)** | 159.6 s | 16.0 | 1.13 |

Determinism: the D=1.60 double is **physics-identical** to its first run (the `[fruit]` stream
minus the startup banners; `logs/p1c/81_d160_diff.txt` is empty).

## 2. The verdict

**With the fruit held constant, the density is strongly negative on the single-arm line**: the
per-attempt success falls 65 % -> 17-30 %, **70-75 % of the attempt slots find no eligible fruit**
(the control never has one), and the placements/minute falls 2.54 -> 0.63-1.13. The pre-registered
primary fails both of its clauses: the starved-slot count does not fall (it explodes), and the
placements per real attempt do not rise.

**Therefore the P1/P2 ladder's positive results are not attributable to the density.** They are
the presented-mix shift the Oracle identified, class-standardised flat
(`logs/p2d/82_standardised.txt`), and this composition-free test shows the underlying effect going
the other way on the line where the mix is pinned. The adoption recommendation stays **withdrawn**.

## 3. The mechanism (measured, not inferred)

The empty-slot messages carry the live pool. At D=1.60 the active apples at attempt 3 sit at
y = +0.147, +0.153, +0.240, +0.235, **+0.375, +0.372** - **abreast pairs** (the density's pair
probability at 0.84) marching downstream, with the most-upstream fruit at **+0.375**, just below
the selection floor (`_dynamic_select_floor()` ~ +0.40 m at 0.12 m/s: the pick lead 0.189 + the
1.5 s setup + 0.03). At attempt 0 the whole pool is already downstream (+0.063 at best).

So the density converts the **steady trickle** into a **single burst**: the 16-fruit pool is
released almost at once, the belt is momentarily overstocked, and the pool then drains. The
single arm's cycle is 15.4-16.0 s - slower than the burst's transit - so for most of the run the
arm polls a floor it cannot satisfy. The two-line hides this because its worker **parks and
waits** (the W7-A park-gate lever) and two arms consume the pool; the single arm's selector
**polls and gives up**. That asymmetry is now measured on both sides: 0/20 empty slots at D=1.00,
14/20 and 30/40 at D=1.60.

The 40-slot run confirms the small sample: 10 real attempts, 3 placed (30 %), still 75 % empty -
the direction is the D=1.60 pair's, not a fluke of n=6.

## 4. What this closes, and what survives

- **Closed as a positive lever.** The density does not raise throughput on a composition-free
  single-arm supply, and the ladder's apparent gain is mix. Nothing to adopt; the knob stays
  default-off and is documented as a **measurement instrument**, not a candidate default.
- **Two real effects survive**, both negative, and both are now measured rather than inferred:
  1. **D=2.0's collapse** (the crowding breaking the acquisition; -7.3 slots class-adjusted,
     `logs/p/RESULTS.md`) - a genuine density effect at the top of the range;
  2. **the starvation at D>=1.5-1.6 on the single-arm line** (this test; and the Oracle's
     D=1.5 reading of 10 empty slots) - a genuine availability cost that the two-line's park
     conceals.
- **The binding term is unchanged and independent of all of this**: the per-attempt arm span
  (~15 s, flat across the whole ladder), of which the place block is closed by geometry
  (`logs/p3/RESULTS.md`) and the descent's documented boundary shortfall is the next target.

## 5. The no-harm

`fruits.py` changed for the species lock (+ the `WAVE+PATCH` warning), so this tree's acceptance
must be re-run before the branch merges - recorded as open, not claimed. `172` is now **63 checks**
(52 at the phase's start): it covers the density knob on both schedules (D=1.0 byte-identity, the
D=1.5 wave scaling, the 0.085 m separation floor, the D=2.0 patch floor, the env removal) and the
species lock (the one-species pool, the unknown-name fallback, and both `FRUIT_SUPPLY_GRADES`
branches) - the knob had **no** coverage before this review.

`tasks.py` `bcb1fb72d80511a35f8b89cad0ca0a23` (the P3 place knob), `rl_env.py` `TASKS_MD5` follows
it; `fruits.py` is not part of the pin.