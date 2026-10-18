# P12-A RESULTS (2026-10-18): the property realism batch on the two-line anchor - the falls halve, the throughput improves, the outcomes stay in the draw band

Under the owner's 2026-10-18 directive (the two-line anchor as the only re-measured reference;
the full re-baseline deferred to adoption). **Exploratory batch (no frozen prereg; the owner's
directive authorized it)** - the read below is a measurement, not a hypothesis test.

## The battery (3 runs, seeds 11/5/23, vs the anchor's A records)

| seed | A (anchor) | P12-A (`FRUIT_PHYSICS_REAL=1`) |
| --- | --- | --- |
| 11 | 10/20, interval 18.70 s, 7 falls, class 10/8/2 | **11/20, 15.29 s (-18 %), 2 falls, class 11/6/3** |
| 5 | 13/20, 15.07 s, 4 falls, class 13/4/3 | 9/20, 15.93 s (+6 %), 3 falls, class 9/4/7 |
| 23 | 16/20, 11.22 s, 3 falls, class 16/1/3 | 15/20, 11.66 s (+4 %), 2 falls, class 15/2/3 |
| pooled | 39/60, interval 14.99 s, window 4.12/min, **14 falls** | 35/60, **14.29 s (-4.7 %)**, **4.28/min (+3.9 %)**, **7 falls** |

Tree: `meshes.py` 10fa005e / `fruits.py` 7283e4bf (`tasks.py` 810658b8, `rl_env.py` 9a2c3872).

## The reading

1. **The falls halve (14 -> 7; the primary seed 7 -> 2).** This is the first intervention in
   the P10/P11/P12 arc that reduces the ejection *without* breaking another branch - the real
   masses (11-44 % heavier), the compliant fruit contact and the higher restitution change how
   the marginal grip fails: the heavier body carries more inertia against the wedge and the
   compliant contact spreads the load (the P11-B's parameter-insensitivity was measured on the
   *withdrawn* rise-and-return geometry; the corrected descent + this task-level read together
   say the pair response does matter).
2. **The throughput improves on the two-line's own primary metrics**: the pooled interval
   -4.7 % (the primary seed -18 %), the pooled window rate +3.9 %.
3. **The outcomes stay in the draw band**: pooled -4 (35 vs 39; the primary +1, the controls
   -4/-1); the class re-draws (the seed-5 carried 3 -> 7 - the heavier fruit escaping the
   carry more often). Per the one-sample discipline this is not a rate claim.
4. No blowup was observed in the three runs' summaries (the blowups counted separately from
   the falls; the record's convention).

## The next step (the refinement per the directive)

The batch's value is concentrated: the falls halve and the interval improves while the outcomes
are draw-dominated. **The component decomposition (P12-A.2)**: split the batch into
`FRUIT_PHYSICS_REAL_MASS` / `_REST` / `_COMPLIANCE` sub-knobs and run the mass-only and the
compliance-only batteries (the restitution is the least likely driver per the audit's physics)
to find which property carries the falls reduction and the interval gain - so the refinement
can keep the winners and drop the seed-5 carried-class side effect. Then P12-B (the scene-side
iteration) on the improved base.
